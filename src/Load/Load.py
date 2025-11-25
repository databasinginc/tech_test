"""
Load module - Loads transformed data into PostgreSQL database with relational tables
"""
import json
import os
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

load_dotenv()

def sanitize_column_name(name):
    """Sanitizes column names for PostgreSQL"""
    return name.replace(' ', '_').replace('/', '_').replace('-', '_').replace('(', '').replace(')', '').replace('.', '_').lower()

def create_related_table(cursor, parent_table, parent_id, field_name, data):
    """Creates a related table for nested structures (Table, Bids, etc.)"""
    related_table_name = f"{parent_table}_{sanitize_column_name(field_name)}"
    
    if isinstance(data, dict):
        # Case 1: Dictionary with arrays (e.g., "Table": {"Item Line Number": [1,2,3], ...})
        if all(isinstance(v, list) for v in data.values()):
            # Get number of rows
            num_rows = len(next(iter(data.values())))
            
            # Create table with columns
            columns = [
                'id SERIAL PRIMARY KEY',
                f'{parent_table}_id INTEGER NOT NULL',
                'row_index INTEGER'
            ]
            for key in data.keys():
                col_name = sanitize_column_name(key)
                # Detect type from first value
                first_val = data[key][0] if data[key] else None
                col_type = 'NUMERIC' if isinstance(first_val, (int, float)) else 'TEXT'
                columns.append(f'"{col_name}" {col_type}')
            
            cursor.execute(f'CREATE TABLE IF NOT EXISTS "{related_table_name}" ({", ".join(columns)})')
            
            # Insert rows
            for i in range(num_rows):
                fields = [sanitize_column_name(k) for k in data.keys()]
                values = [data[k][i] if i < len(data[k]) else None for k in data.keys()]
                placeholders = ','.join(['%s'] * (len(fields) + 2))
                fields_str = ','.join([f'"{c}"' for c in fields])
                
                cursor.execute(
                    f'INSERT INTO "{related_table_name}" ({parent_table}_id, row_index, {fields_str}) VALUES ({placeholders})',
                    [parent_id, i] + values
                )
        else:
            # Case 2: Dictionary with nested objects (e.g., "Bid Value": {"bid_amounts": [...], "vendor_names": [...]})
            cursor.execute(f'CREATE TABLE IF NOT EXISTS "{related_table_name}" (id SERIAL PRIMARY KEY, {parent_table}_id INTEGER NOT NULL, data JSONB)')
            cursor.execute(f'INSERT INTO "{related_table_name}" ({parent_table}_id, data) VALUES (%s, %s)', [parent_id, Json(data)])
    
    elif isinstance(data, list):
        # Case 3: Array of objects (e.g., "Bids": [{...}, {...}])
        if data and isinstance(data[0], dict):
            # Create table with all possible keys from all objects
            all_keys = set()
            for item in data:
                if isinstance(item, dict):
                    all_keys.update(item.keys())
            
            columns = [
                'id SERIAL PRIMARY KEY',
                f'{parent_table}_id INTEGER NOT NULL',
                'array_index INTEGER'
            ]
            
            # Determine column types
            for key in all_keys:
                col_name = sanitize_column_name(key)
                # Find first non-None value to determine type
                sample_val = None
                for item in data:
                    if isinstance(item, dict) and key in item and item[key] is not None:
                        sample_val = item[key]
                        break
                
                if isinstance(sample_val, (dict, list)):
                    col_type = 'JSONB'
                elif isinstance(sample_val, (int, float)):
                    col_type = 'NUMERIC'
                else:
                    col_type = 'TEXT'
                
                columns.append(f'"{col_name}" {col_type}')
            
            cursor.execute(f'CREATE TABLE IF NOT EXISTS "{related_table_name}" ({", ".join(columns)})')
            
            # Insert each item
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    fields = [sanitize_column_name(k) for k in all_keys]
                    values = []
                    for k in all_keys:
                        val = item.get(k)
                        if isinstance(val, (dict, list)):
                            values.append(Json(val))
                        else:
                            values.append(val)
                    
                    placeholders = ','.join(['%s'] * (len(fields) + 2))
                    fields_str = ','.join([f'"{c}"' for c in fields])
                    
                    cursor.execute(
                        f'INSERT INTO "{related_table_name}" ({parent_table}_id, array_index, {fields_str}) VALUES ({placeholders})',
                        [parent_id, idx] + values
                    )
        else:
            # Simple array - store as JSONB
            cursor.execute(f'CREATE TABLE IF NOT EXISTS "{related_table_name}" (id SERIAL PRIMARY KEY, {parent_table}_id INTEGER NOT NULL, data JSONB)')
            cursor.execute(f'INSERT INTO "{related_table_name}" ({parent_table}_id, data) VALUES (%s, %s)', [parent_id, Json(data)])

def load_to_database(filename, doc_type, data, db_config=None):
    """Creates main table and related tables for nested structures"""
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
    
    # Separate simple fields from complex nested structures
    simple_data = {}
    complex_data = {}
    
    for k, v in data.items():
        # Detect complex structures that should be in separate tables
        if isinstance(v, dict) and any(isinstance(sub_v, list) for sub_v in v.values()):
            # Dictionary with arrays (like "Table")
            complex_data[k] = v
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            # Array of objects (like "Bids")
            complex_data[k] = v
        elif isinstance(v, dict) and 'bid_amounts' in str(v).lower():
            # Nested bid structures
            complex_data[k] = v
        else:
            simple_data[k] = v
    
    # Build CREATE TABLE for main table with simple fields only
    columns = ['id SERIAL PRIMARY KEY', 'document_type TEXT', 'source_file TEXT', 'created_at TIMESTAMP DEFAULT NOW()']
    for k, v in simple_data.items():
        col_type = 'NUMERIC' if isinstance(v, (int, float)) else 'JSONB' if isinstance(v, (dict, list)) else 'TEXT'
        col_name = sanitize_column_name(k)
        columns.append(f'"{col_name}" {col_type}')
    
    cursor.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)})')
    
    # Insert main data
    fields = [sanitize_column_name(k) for k in simple_data.keys()]
    values = [Json(v) if isinstance(v, (dict, list)) else v for v in simple_data.values()]
    placeholders = ','.join(['%s'] * (len(fields) + 2))
    fields_str = ','.join([f'"{c}"' for c in fields])
    
    cursor.execute(f'INSERT INTO "{table_name}" (document_type, source_file, {fields_str}) VALUES ({placeholders}) RETURNING id',
                   [doc_type, filename] + values)
    
    parent_id = cursor.fetchone()[0]
    
    # Create and populate related tables
    for field_name, field_data in complex_data.items():
        create_related_table(cursor, table_name, parent_id, field_name, field_data)
    
    conn.commit()
    cursor.close()
    conn.close()
    return table_name
