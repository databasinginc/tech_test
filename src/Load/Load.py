"""
Load module - Loads transformed data into PostgreSQL database
"""
import json
import os
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

load_dotenv()

def load_to_database(filename, doc_type, data, db_config=None):
    """Creates table (if needed) and inserts extracted data into PostgreSQL"""
    if db_config is None:
        db_config = {
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT'),
            'dbname': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD')
        }
    
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    table_name = os.path.basename(filename).replace(' ', '_').replace('-', '_').replace('.pdf', '')
    
    # Build CREATE TABLE with typed columns
    columns = ['id SERIAL PRIMARY KEY', 'document_type TEXT', 'source_file TEXT', 'created_at TIMESTAMP DEFAULT NOW()']
    for k, v in data.items():
        col_type = 'NUMERIC' if isinstance(v, (int, float)) else 'JSONB' if isinstance(v, (dict, list)) else 'TEXT'
        col_name = k.replace(' ', '_').replace('/', '_').replace('-', '_').replace('(', '').replace(')', '').lower()
        columns.append(f'"{col_name}" {col_type}')
    
    cursor.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)})')
    
    # Insert data
    fields = [k.replace(' ', '_').replace('/', '_').replace('-', '_').replace('(', '').replace(')', '').lower() for k in data.keys()]
    values = [Json(v) if isinstance(v, (dict, list)) else v for v in data.values()]
    placeholders = ','.join(['%s'] * (len(fields) + 2))
    fields_str = ','.join([f'"{c}"' for c in fields])
    
    cursor.execute(f'INSERT INTO "{table_name}" (document_type, source_file, {fields_str}) VALUES ({placeholders})',
                   [doc_type, filename] + values)
    
    conn.commit()
    cursor.close()
    conn.close()
    return table_name

def load_data():
    """Loads transformed data into PostgreSQL"""
    
    with open('intermediario/transformado.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    conn = connect_db()
    cursor = conn.cursor()
    
    print("Loading data into PostgreSQL...\n")
    
    for filepath, item in data.items():
        filename = os.path.basename(filepath)
        doc_type = item.get('type', '')
        data_json = item.get('data', {})
        
        print(f"Loading: {filename}")
        
        # Create table
        table_name = create_table(cursor, filename, doc_type)
        
        # Insert data
        cursor.execute(f"""
            INSERT INTO "{table_name}" (document_type, data, source_file)
            VALUES (%s, %s, %s)
        """, (doc_type, Json(data_json), filepath))
        
        print(f"  OK Inserted into table '{table_name}'")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\nOK Load completed! {len(data)} records inserted.")

if __name__ == '__main__':
    load_data()
