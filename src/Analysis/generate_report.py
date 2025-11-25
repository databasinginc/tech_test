import boto3
import psycopg2
import os
import subprocess
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# AWS Bedrock client
bedrock = boto3.client('bedrock-runtime',
                       aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                       aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                       region_name=os.getenv('AWS_REGION'))

def get_tables_data():
    """Extracts all data from RDS database tables"""
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    cursor = conn.cursor()
    
    # List all tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    data = {}
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cursor.fetchone()[0]
        
        # Get ALL data (not just samples)
        cursor.execute(f'SELECT * FROM "{table}"')
        rows = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        
        # Convert to list of dicts
        records = []
        for row in rows:
            record = {}
            for i, col in enumerate(colnames):
                value = row[i]
                # Serialize complex values
                if isinstance(value, (dict, list)):
                    record[col] = str(value)
                else:
                    record[col] = value
            records.append(record)
        
        data[table] = {
            'count': count,
            'columns': colnames,
            'records': records  # All data
        }
    
    cursor.close()
    conn.close()
    return data

def generate_latex_with_bedrock(data):
    """Uses Bedrock Claude to generate LaTeX report with AI-powered insights"""
    
    import json
    
    # Prepare complete data for analysis
    data_for_analysis = {}
    for table, info in data.items():
        data_for_analysis[table] = {
            'total_records': info['count'],
            'columns': info['columns'],
            'data': info['records']  # Complete data
        }
    
    # Serialize to JSON (more structured for LLM)
    data_json = json.dumps(data_for_analysis, indent=2, default=str)
    
    prompt = f"""You are a data analyst specialized in construction contracts.

Analyze the NC DOT contracts data below and create an executive report in LaTeX with real insights:

COMPLETE DATA:
{data_json}

Create a 2-3 page LaTeX report with:

1. Title: "Executive Report - NC DOT Contracts"
2. Date: {datetime.now().strftime('%m/%d/%Y')}
3. Executive Summary: Total contracts, total estimated value
4. Analysis by Document Type: How many awards, bids, item reports
5. Financial Statistics: Minimum, maximum, average values (if value fields exist)
6. Main Vendors: List the most frequent vendors (if available)
7. Temporal Distribution: Analyze contract dates (if available)
8. Insights and Observations: Patterns found in the data

Use LaTeX tables to present numbers. Be objective and base your analysis on the REAL DATA provided.

Return ONLY the complete LaTeX code (from \\documentclass to \\end{{document}}), without explanations."""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 6000,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    })
    
    response = bedrock.invoke_model(
        modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
        body=body
    )
    
    result = json.loads(response['body'].read())
    latex_code = result['content'][0]['text']
    
    # Clean markdown if present
    if '```latex' in latex_code:
        latex_code = latex_code.split('```latex')[1].split('```')[0].strip()
    elif '```' in latex_code:
        latex_code = latex_code.split('```')[1].split('```')[0].strip()
    
    return latex_code

def format_data_for_prompt(data):
    """Formats data for LLM prompt (legacy function, not currently used)"""
    text = []
    for table, info in data.items():
        text.append(f"\nTable: {table}")
        text.append(f"  Total records: {info['count']}")
        text.append(f"  Columns: {', '.join(info['columns'][:5])}")  # First 5 columns
    return '\n'.join(text)

def compile_latex(latex_code, output_dir=None):
    """Compiles LaTeX to PDF using MiKTeX"""
    if output_dir is None:
        # Absolute path to project output folder
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, '..', '..', 'output')
    
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    tex_file = os.path.join(output_dir, 'report.tex')
    with open(tex_file, 'w', encoding='utf-8') as f:
        f.write(latex_code)
    
    print(f"OK - LaTeX saved to: {tex_file}")
    
    # Compile with pdflatex
    try:
        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory=' + output_dir, tex_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        pdf_file = os.path.join(output_dir, 'report.pdf')
        if os.path.exists(pdf_file):
            print(f"OK - PDF generated: {pdf_file}")
            return pdf_file
        else:
            print(f"WARNING - Compilation executed but PDF not found")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return None
    except Exception as e:
        print(f"ERROR compiling: {e}")
        return None

if __name__ == '__main__':
    print("Analyzing RDS database tables...", flush=True)
    data = get_tables_data()
    
    if not data:
        print("No tables found in database")
        exit(1)
    
    print(f"OK - {len(data)} tables found\n", flush=True)
    
    print("Generating report with Bedrock Claude...", flush=True)
    latex_code = generate_latex_with_bedrock(data)
    print("OK - LaTeX generated\n", flush=True)
    
    print("Compiling PDF...", flush=True)
    pdf_path = compile_latex(latex_code)
    
    if pdf_path:
        print(f"\nSUCCESS - Report completed: {pdf_path}", flush=True)
    else:
        print("\nERROR - LaTeX report generated but compilation failed", flush=True)
        print("Run manually: pdflatex output/report.tex", flush=True)
        exit(1)
