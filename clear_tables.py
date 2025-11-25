import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT'),
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)

cursor = conn.cursor()

# List all tables
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
""")

tables = [row[0] for row in cursor.fetchall()]

# Drop all tables
for table in tables:
    cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
    print(f"OK Removed: {table}")

conn.commit()
cursor.close()
conn.close()

print(f"\nOK {len(tables)} tables removed")
