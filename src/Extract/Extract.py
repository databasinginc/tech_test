"""
Extract module - Handles data extraction from PDFs using Claude multimodal vision
"""
import boto3
import os
import json
import base64
import time
from dotenv import load_dotenv
from pdf2image import convert_from_bytes
from io import BytesIO

load_dotenv()

def load_templates():
    """Loads JSON templates and converts example PDFs to PNG base64"""
    templates = {}
    example_pdfs = {}
    
    context_dir = 'intermediario/contexto'
    print("Loading templates...")
    for filename in os.listdir(context_dir):
        if filename.endswith('.json'):
            doc_type = filename.replace(' - Mapped.json', '')
            with open(os.path.join(context_dir, filename), 'r', encoding='utf-8') as f:
                templates[doc_type] = json.load(f)
            
            # Load example PDF if exists
            pdf_path = os.path.join(context_dir, filename.replace('.json', '.pdf'))
            if os.path.exists(pdf_path):
                try:
                    with open(pdf_path, 'rb') as pdf:
                        images = convert_from_bytes(pdf.read(), dpi=150)
                        buffer = BytesIO()
                        images[0].save(buffer, format='PNG')
                        example_pdfs[doc_type] = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        print(f"  OK {doc_type} - {len(example_pdfs[doc_type])} bytes")
                except Exception as e:
                    print(f"  ERROR {doc_type}: {e}")
    
    print(f"OK {len(templates)} templates loaded\n")
    return templates, example_pdfs

def identify_document_type(filename):
    """Identifies document type from filename"""
    n = filename.lower().replace('.docx', '')  # Remove .docx from name
    if 'award letter' in n or 'award_letter' in n: return 'NC D1 Award Letter'
    if 'bid summary' in n: return 'NC D1 Bid Summary'
    if 'bid tabs' in n or 'bid_tabs' in n:
        return 'NC D1 Bid Tabs (IDIQ_Upon Request_On Call)' if 'idiq' in n or 'upon request' in n else 'NC D1 Bid Tabs (Standard)'
    if 'bids as read' in n: return 'NC D1 Bids as Read'
    if 'invitation to bid' in n or 'invitation_to_bid' in n:
        return 'NC D1 Invitation to Bid (SBE)' if 'sbe' in n else 'NC D1 Invitation to Bid (Standard)'
    if 'item c' in n or 'item_c' in n: return 'NC Item C (Adjusted)' if 'adjusted' in n else 'NC  Item C (Standard)'
    return None

def extract_fields_with_claude(pdf_bytes, template, example_pdf_base64, bedrock_client):
    """Extracts structured fields from PDF using Claude multimodal vision"""
    if not example_pdf_base64:
        print("  WARNING: Example PDF not found")
        return {}
    
    # Convert PDF to PNG
    images = convert_from_bytes(pdf_bytes, dpi=150)
    buffer = BytesIO()
    images[0].save(buffer, format='PNG')
    pdf_png = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # Call Bedrock Claude with both example and target PDFs
    response = bedrock_client.invoke_model(
        modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": example_pdf_base64}},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": pdf_png}},
                    {"type": "text", "text": f"Extract data following this template:\n{json.dumps(template, indent=2)}\n\nReturn ONLY JSON."}
                ]
            }]
        })
    )
    result = json.loads(response['body'].read())
    text = result['content'][0]['text']
    start = text.find('{')
    end = text.rfind('}') + 1
    time.sleep(30)  # Rate limiting
    return json.loads(text[start:end]) if start != -1 and end > start else {}

