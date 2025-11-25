"""
Transform module - Cleans and transforms extracted data
"""
import json
import os
from datetime import datetime

def clean_monetary_value(value):
    """Removes symbols and converts to float"""
    if not value: return None
    try: return float(str(value).replace('$', '').replace(',', ''))
    except: return None

def clean_date(value):
    """Normalizes date formats to YYYY-MM-DD"""
    if not value: return None
    try:
        for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%B %d, %Y', '%b %d, %Y']:
            try: return datetime.strptime(str(value).strip(), fmt).strftime('%Y-%m-%d')
            except: continue
    except: pass
    return str(value)

def transform_data(data):
    """Cleans and transforms extracted data (monetary, dates, etc.)"""
    cleaned_data = {}
    for k, v in data.items():
        if any(p in k.lower() for p in ['bid value', 'amount', 'cost', 'price', 'total']):
            cleaned_data[k] = clean_monetary_value(v) if not isinstance(v, (dict, list)) else v
        elif any(p in k.lower() for p in ['date', 'letting', 'completion']):
            cleaned_data[k] = clean_date(v)
        elif any(p in k.lower() for p in ['miles']):
            cleaned_data[k] = clean_monetary_value(v)
        elif k.lower() == 'state_and_owner':
            cleaned_data[k] = f"{v.get('state','')} {v.get('owner','')}".strip() if isinstance(v, dict) else str(v)
        elif k.lower() == 'vendor_names':
            cleaned_data[k] = list(v.values()) if isinstance(v, dict) else ([v] if not isinstance(v, list) else v)
        else:
            cleaned_data[k] = v
    return cleaned_data

def transform_data():
    # Load extracted data
    with open('intermediario/extracao.json', 'r', encoding='utf-8') as f:
        extractions = json.load(f)
    
    transformed_data = {}
    
    for filepath, item in extractions.items():
        if 'error' in item:
            continue
        
        print(f"Transforming: {os.path.basename(filepath)}")
        
        data = item.get('data', {})
        doc_type = item.get('type', '')
        
        # Apply cleaning based on field type
        cleaned_data = {}
        
        for key, value in data.items():
            # Monetary fields
            if any(word in key.lower() for word in ['bid value', 'amount', 'cost estimate', 'price']):
                if isinstance(value, dict):
                    # For structures like bid_amounts
                    cleaned_data[key] = {
                        k: [clean_monetary_value(v) for v in val] if isinstance(val, list) else clean_monetary_value(val)
                        for k, val in value.items()
                    }
                elif isinstance(value, list):
                    cleaned_data[key] = [clean_monetary_value(v) for v in value]
                else:
                    cleaned_data[key] = clean_monetary_value(value)
            
            # Date fields
            elif any(word in key.lower() for word in ['date', 'letting']):
                cleaned_data[key] = clean_date(value)
            
            # Lists of names, counties, etc
            elif any(word in key.lower() for word in ['vendor', 'counties', 'county', 'project number']):
                if isinstance(value, (list, str)):
                    cleaned_data[key] = normalize_list(value)
                else:
                    cleaned_data[key] = value
            
            # Complex arrays/objects (tables, bids)
            elif isinstance(value, (dict, list)):
                cleaned_data[key] = value
            
            # Simple text
            else:
                cleaned_data[key] = clean_text(value)
        
        transformed_data[filepath] = {
            'type': doc_type,
            'data': cleaned_data
        }
        
        print(f"  OK {len(cleaned_data)} fields processed")
    
    # Save transformed data
    with open('intermediario/transformado.json', 'w', encoding='utf-8') as f:
        json.dump(transformed_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nOK Transformation completed! {len(transformed_data)} files processed.")
    return transformed_data

if __name__ == '__main__':
    transform_data()

