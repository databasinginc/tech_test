from flask import Flask, jsonify
import boto3
import os
import json
import time
import psycopg2
import sys
import threading
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import unquote_plus

# Import ETL modules
from src.Extract.Extract import load_templates, identify_document_type, extract_fields_with_claude
from src.Transform.Transform import transform_data
from src.Load.Load import load_to_database

load_dotenv()

app = Flask(__name__)

# AWS clients configuration
s3 = boto3.client('s3', aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
bedrock = boto3.client('bedrock-runtime', aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                       aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                       region_name=os.getenv('AWS_REGION'))
sqs = boto3.client('sqs', aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                   aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                   region_name=os.getenv('AWS_REGION'))

bucket = os.getenv('S3_BUCKET_NAME')
queue_url = os.getenv('SQS_QUEUE_URL')

TEMPLATES = None
EXAMPLE_PDFS = None

def process_pdf(s3_key):
    """Processes a single PDF through Extract -> Transform -> Load pipeline"""
    global TEMPLATES, EXAMPLE_PDFS
    
    if TEMPLATES is None:
        TEMPLATES, EXAMPLE_PDFS = load_templates()
    
    filename = os.path.basename(s3_key)
    doc_type = identify_document_type(filename)
    
    if not doc_type or doc_type not in TEMPLATES:
        return {'status': 'skip', 'reason': 'document type not identified'}
    
    pdf_obj = s3.get_object(Bucket=bucket, Key=s3_key)
    pdf_bytes = pdf_obj['Body'].read()
    
    data = extract_fields_with_claude(pdf_bytes, TEMPLATES[doc_type], EXAMPLE_PDFS.get(doc_type), bedrock)
    if not data:
        return {'status': 'error', 'reason': 'extraction failed'}
    
    cleaned_data = transform_data(data)
    table = load_to_database(s3_key, doc_type, cleaned_data)
    
    return {'status': 'success', 'table': table, 'type': doc_type}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/', methods=['GET'])
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Edgevanta ETL</title>
        <style>
            body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            button { padding: 15px 30px; font-size: 16px; margin: 10px; cursor: pointer; border: none; border-radius: 5px; }
            .primary { background: #007bff; color: white; }
            .primary:hover { background: #0056b3; }
            .danger { background: #dc3545; color: white; }
            .danger:hover { background: #c82333; }
            #status { margin-top: 20px; padding: 15px; border-radius: 5px; display: none; }
            .success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
            .error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
            .info { background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }
            pre { background: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>🚀 Edgevanta ETL Pipeline</h1>
        <p>Sistema de processamento de PDFs do S3 para PostgreSQL</p>
        
        <h2>Actions:</h2>
        <button class="primary" onclick="processBatch()">📦 Process All PDFs (Batch)</button>
        <button class="primary" onclick="generateReport()">📊 Generate Executive Report</button>
        <button class="danger" onclick="clearTables()">🗑️ Clear All Tables</button>
        
        <div id="status"></div>
        
        <script>
            function showStatus(msg, type) {
                const status = document.getElementById('status');
                status.className = type;
                status.innerHTML = msg;
                status.style.display = 'block';
            }
            
            async function processBatch() {
                showStatus('⏳ Starting batch processing...', 'info');
                try {
                    const res = await fetch('/processar-batch', { method: 'POST' });
                    const data = await res.json();
                    if (data.status === 'success') {
                        showStatus(`✓ Batch started! Processing ${data.total_folders} folders in background.`, 'success');
                    } else {
                        showStatus(`✗ Error: ${data.message}`, 'error');
                    }
                } catch (e) {
                    showStatus(`✗ Error: ${e.message}`, 'error');
                }
            }
            
            async function generateReport() {
                showStatus('⏳ Generating executive report...', 'info');
                try {
                    const res = await fetch('/gerar-relatorio', { method: 'POST' });
                    const data = await res.json();
                    if (data.status === 'success') {
                        showStatus(`✓ Report generated! PDF saved at: ${data.pdf_path}`, 'success');
                    } else {
                        showStatus(`✗ Error: ${data.message}`, 'error');
                    }
                } catch (e) {
                    showStatus(`✗ Error: ${e.message}`, 'error');
                }
            }
            
            async function clearTables() {
                if (!confirm('Are you sure you want to delete ALL tables?')) return;
                showStatus('⏳ Clearing tables...', 'info');
                try {
                    const res = await fetch('/limpar-tabelas', { method: 'POST' });
                    const data = await res.json();
                    if (data.status === 'success') {
                        showStatus(`✓ ${data.total} tables removed successfully!`, 'success');
                    } else {
                        showStatus(`✗ Error: ${data.message}`, 'error');
                    }
                } catch (e) {
                    showStatus(`✗ Error: ${e.message}`, 'error');
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route('/processar-batch', methods=['POST'])
def process_batch_endpoint():
    """API endpoint to start batch ETL processing in background thread"""
    try:
        # Start processing in separate thread
        thread = threading.Thread(target=run_complete_etl, daemon=True)
        thread.start()
        
        # Count folders
        folders = s3.list_objects_v2(Bucket=bucket, Prefix='2023 nc d1/', Delimiter='/')
        total_folders = len(folders.get('CommonPrefixes', []))
        
        return jsonify({'status': 'success', 'total_folders': total_folders}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/gerar-relatorio', methods=['POST'])
def generate_report_endpoint():
    """API endpoint to generate executive PDF report from database data"""
    try:
        import subprocess
        result = subprocess.run(
            ['python', 'src/Analysis/generate_report.py'],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'pdf_path': 'output/report.pdf',
                'message': 'Report generated successfully!'
            }), 200
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            return jsonify({
                'status': 'error',
                'message': f'Error generating report: {error_msg[-300:]}'
            }), 500
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'Report generation timeout'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/limpar-tabelas', methods=['POST'])
def clear_tables_endpoint():
    """API endpoint to drop all database tables"""
    try:
        conn = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'),
                                dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                                password=os.getenv('DB_PASSWORD'))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'total': len(tables)}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/poll-sqs', methods=['GET'])
def poll_sqs():
    """Manual endpoint to poll SQS queue and process messages"""
    try:
        response = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=5)
        messages = response.get('Messages', [])
        
        results = []
        for msg in messages:
            body = json.loads(msg['Body'])
            if 'Records' in body:
                for record in body['Records']:
                    s3_key = record['s3']['object']['key']
                    if s3_key.startswith('2023 nc d1/') and s3_key.lower().endswith('.pdf'):
                        result = process_pdf(s3_key)
                        results.append({'file': s3_key, 'result': result})
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg['ReceiptHandle'])
        
        return jsonify({'status': 'ok', 'messages': len(messages), 'processed': results}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

def worker_sqs():
    """Background SQS polling worker - processes S3 event notifications automatically"""
    if not queue_url:
        print("WARNING: SQS_QUEUE_URL not configured - worker disabled")
        print("  Run: python setup/setup_sqs.py")
        return
    
    print("Worker SQS started - polling every 10s", flush=True)
    poll_count = 0
    while True:
        try:
            poll_count += 1
            print(f"Polling #{poll_count}...", flush=True)
            
            response = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=5)
            messages = response.get('Messages', [])
            
            if messages:
                print(f"\nOK {len(messages)} messages received", flush=True)
                for msg in messages:
                    body = json.loads(msg['Body'])
                    print(f"  Message body type: {type(body)}, keys: {body.keys() if isinstance(body, dict) else 'N/A'}", flush=True)
                    
                    if 'Records' in body:
                        print(f"  {len(body['Records'])} records found", flush=True)
                        for record in body['Records']:
                            s3_key = record['s3']['object']['key']
                            # URL decode (+ becomes space, %XX becomes character)
                            s3_key = unquote_plus(s3_key)
                            print(f"  S3 Key: {s3_key}", flush=True)
                            
                            if s3_key.lower().endswith('.pdf'):
                                print(f"  -> Processing {os.path.basename(s3_key)}...", flush=True)
                                result = process_pdf(s3_key)
                                print(f"    Status: {result.get('status', 'error')}", flush=True)
                            else:
                                print(f"  Skipped (not a PDF)", flush=True)
                    else:
                        print(f"  WARNING: Message without 'Records': {body}", flush=True)
                    
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg['ReceiptHandle'])
                    print(f"  OK Message deleted from queue", flush=True)
            
            time.sleep(10)
        except Exception as e:
            print(f"\nERROR: {e}")
            time.sleep(30)

def run_complete_etl():
    """Processes all PDFs from S3 in batch mode (Extract -> Transform -> Load)"""
    global TEMPLATES, EXAMPLE_PDFS
    
    if TEMPLATES is None:
        TEMPLATES, EXAMPLE_PDFS = load_templates()
    
    folders = s3.list_objects_v2(Bucket=bucket, Prefix='2023 nc d1/', Delimiter='/')
    
    total = 0
    for folder in folders.get('CommonPrefixes', []):
        print(f"\n=== {folder['Prefix']} ===")
        objs = s3.list_objects_v2(Bucket=bucket, Prefix=folder['Prefix'])
        
        for obj in objs.get('Contents', []):
            filepath = obj['Key']
            if not filepath.lower().endswith('.pdf'):
                continue
            
            filename = os.path.basename(filepath)
            print(f"\n> {filename}")
            
            try:
                doc_type = identify_document_type(filename)
                if not doc_type or doc_type not in TEMPLATES:
                    print("  WARNING: Document type not identified")
                    continue
                
                print(f"  [EXTRACT] {doc_type}")
                pdf_obj = s3.get_object(Bucket=bucket, Key=filepath)
                pdf_bytes = pdf_obj['Body'].read()
                
                print("  [EXTRACT] Extracting with Claude...")
                data = extract_fields_with_claude(pdf_bytes, TEMPLATES[doc_type], EXAMPLE_PDFS.get(doc_type), bedrock)
                
                if not data:
                    print("  ERROR: Extraction failed")
                    continue
                
                print("  [TRANSFORM] Cleaning...")
                cleaned_data = transform_data(data)
                
                print("  [LOAD] Saving...")
                table = load_to_database(filepath, doc_type, cleaned_data)
                
                print(f"  OK -> {table}")
                total += 1
            except Exception as e:
                print(f"  ERROR: {e}")
    
    print(f"\n{'='*50}")
    print(f"OK ETL completed! {total} files processed")
    
    # Generate executive report
    if total > 0:
        try:
            print(f"\n{'='*50}")
            print("Generating executive report...")
            import subprocess
            result = subprocess.run(
                ['python', 'src/Analysis/generate_report.py'],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                print("OK Report generated successfully!")
            else:
                print("WARNING: Error generating report:")
                print(result.stderr[-300:] if result.stderr else result.stdout[-300:])
        except Exception as e:
            print(f"WARNING: Error generating report: {e}")

if __name__ == '__main__':
    # Preload templates
    TEMPLATES, EXAMPLE_PDFS = load_templates()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'batch':
        run_complete_etl()
    else:
        # Start SQS worker in separate thread
        worker_thread = threading.Thread(target=worker_sqs, daemon=True)
        worker_thread.start()
        
        # Start Flask API
        print("Starting Flask API on port 5000...")
        app.run(host='0.0.0.0', port=5000, debug=False)

