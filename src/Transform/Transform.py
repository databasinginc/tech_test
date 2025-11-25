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

