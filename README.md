# Edgevanta ETL Pipeline

## Overview

Automated ETL (Extract, Transform, Load) pipeline for processing North Carolina Department of Transportation (NC DOT) contract documents. The system extracts structured data from PDF files stored in AWS S3, transforms and cleans the data, and loads it into a PostgreSQL database. It uses AI-powered extraction with Amazon Bedrock Claude 3.5 Sonnet for intelligent document parsing.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ETL PIPELINE FLOW                        │
└─────────────────────────────────────────────────────────────────┘

1. UPLOAD (Manual or Automated)
   └─> Local PDFs → AWS S3 (techtest-edgevanta/2023 nc d1/)

2. NOTIFICATION (Automated)
   └─> S3 Event → AWS SQS Queue

3. WORKER (Background Thread)
   └─> SQS Polling (every 10s) → Receive PDF notification

4. EXTRACT (AI-Powered)
   ├─> Download PDF from S3
   ├─> Convert PDF to PNG images (150 DPI)
   ├─> Load template + example PDF for document type
   └─> AWS Bedrock Claude 3.5 Sonnet (Multimodal)
       └─> Structured JSON extraction

5. TRANSFORM (Data Cleaning)
   ├─> Clean monetary values ($1,234.56 → 1234.56)
   ├─> Parse dates (MM/DD/YYYY)
   ├─> Normalize vendor names
   └─> Flatten nested structures

6. LOAD (Database) - Relational Schema
   ├─> Analyze data structure (simple vs complex fields)
   ├─> Create main table with simple fields
   ├─> Create related tables for nested structures
   │   ├─> Bid items tables (_table suffix)
   │   ├─> Bid values tables (_bid_values suffix)
   │   └─> Nested arrays tables (_bids suffix)
   ├─> Maintain foreign key relationships (parent_id)
   └─> Insert into PostgreSQL RDS with proper normalization

7. ANALYSIS (Optional)
   ├─> Query all tables from RDS
   ├─> AWS Bedrock Claude generates LaTeX report
   └─> Compile PDF with MiKTeX
       └─> Save to output/report.pdf
```

## Technologies

### AWS Services
- **S3**: PDF document storage
- **SQS**: Event-driven processing queue
- **Bedrock**: Claude 3.5 Sonnet for AI extraction and report generation
- **RDS PostgreSQL**: Structured data storage

### Local Stack
- **Python 3.13**: Core application
- **Flask**: Web API and UI
- **pdf2image + Pillow**: PDF to image conversion
- **psycopg2**: PostgreSQL database driver
- **boto3**: AWS SDK
- **MiKTeX**: LaTeX to PDF compilation

## Project Structure

```
edgevanta/
├── app.py                          # Main Flask API + SQS worker
├── upload_folder.py                # S3 upload utility
├── clear_s3.py                     # S3 cleanup utility
├── clear_tables.py                 # Database cleanup utility
├── .env                            # Environment variables (gitignored)
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore rules
│
├── data/                           # Local PDF files
│   └── 2023 nc d1/                 # NC DOT contracts by date
│       ├── 2023-02-01_nc_d1/
│       ├── 2023-02-15_nc_d1/
│       └── ...
│
├── intermediario/                  # Document templates
│   └── contexto/
│       ├── NC D1 Award Letter - Mapped.json
│       ├── NC D1 Bid Tabs - Mapped.json
│       └── ... (9 document types)
│
├── output/                         # Generated reports
│   ├── report.pdf
│   └── report.tex
│
├── setup/                          # Infrastructure scripts
│   ├── setup_sqs.py               # Configure S3 → SQS notifications
│   └── create_bedrock_rag.py      # Legacy RAG setup
│
└── src/
    ├── Extract/
    │   └── Extract.py             # Legacy extraction (Textract)
    ├── Transform/
    │   └── Transform.py           # Data cleaning utilities
    ├── Load/
    │   └── Load.py               # Database insertion
    └── Analysis/
        ├── generate_report.py    # AI-powered report generator
        └── README.md             # Analysis documentation
```

## Features

### 1. Automatic Processing
- **S3 Event Notifications**: Automatically triggers processing when new PDFs are uploaded
- **SQS Worker**: Background thread polls queue every 10 seconds
- **Incremental ETL**: Processes files individually as they arrive

### 2. Multimodal AI Extraction
- **Template-Based**: 9 document types with JSON schemas
- **Visual Context**: Sends example PDFs as images to Claude
- **Structured Output**: Extracts tables, dates, amounts, vendor lists

### 3. Web Interface
Access at `http://localhost:5000`:
- **Batch Processing**: Process all PDFs in S3
- **Generate Report**: Create executive PDF report with insights
- **Clear Tables**: Drop all database tables

### 4. Data Quality
- **Type Inference**: Automatically detects NUMERIC, TEXT, or JSONB columns
- **Column Sanitization**: Removes special characters from SQL column names
- **Error Handling**: Continues batch processing even if individual files fail
- **Relational Normalization**: Automatically creates related tables for nested structures

### 5. Intelligent Database Schema
The system automatically detects complex nested structures and creates properly normalized relational tables:

**Simple Documents** (e.g., Award Letters):
- Single table with all fields
- Direct column mapping

**Complex Documents** (e.g., Bid Tabs):
- **Main table**: Header information (contract ID, date, description)
- **Related tables**: Automatically created for nested data
  - `{table_name}_table`: Line items with quantities and prices
  - `{table_name}_bids`: Individual bid submissions
  - `{table_name}_bid_values`: Vendor pricing arrays

**Benefits**:
- ✅ Proper data normalization
- ✅ Easy SQL queries with JOINs
- ✅ Maintains referential integrity via foreign keys
- ✅ Scalable for large datasets

## Setup

### 1. Prerequisites
```bash
# Install Python 3.13+
# Install MiKTeX (for LaTeX PDF generation)
# Install Poppler (for pdf2image)
```

### 2. Environment Variables
Copy `.env.example` to `.env` and fill in:
```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/.../your-queue
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=your-database
DB_USER=your-user
DB_PASSWORD=your-password
```

### 3. Install Dependencies
```bash
pip install flask boto3 psycopg2 python-dotenv pdf2image pillow
```

### 4. Configure AWS Infrastructure
```bash
# Create SQS queue and S3 event notifications
python setup/setup_sqs.py
```

### 5. Run the Application
```bash
python app.py
```

## Usage

### Upload PDFs to S3
```bash
# Edit upload_folder.py to set local folder path
python upload_folder.py
```

### Manual Batch Processing
```bash
# Via web UI: http://localhost:5000 → "Process All PDFs (Batch)"
# Or via command line:
python app.py batch
```

### Generate Executive Report
```bash
# Via web UI: http://localhost:5000 → "Generate Executive Report"
# Or via command line:
python src/Analysis/generate_report.py
```

## Document Types Supported

1. **Award Letter**: Contract award notifications
2. **Bid Tabs (Standard/IDIQ)**: Bid tabulation sheets
3. **Bid Summary**: Summary of submitted bids
4. **Bids as Read**: Bid opening records
5. **Invitation to Bid (Standard/SBE)**: Bid solicitations
6. **Item C Report**: Detailed cost breakdowns

## Data Flow Example

### Example 1: Simple Document (Award Letter)

**Input PDF**: `DA00564_Award_Letter.pdf`

**Extracted Data**:
```json
{
  "contract_number": "DA00564",
  "award_date": "2023-02-01",
  "vendor_name": "ABC Construction Co",
  "contract_amount": 1234567.89,
  "project_description": "Highway resurfacing"
}
```

**Database Schema** - Single Table:
```sql
CREATE TABLE "DA00564_Award_Letter" (
  id SERIAL PRIMARY KEY,
  document_type TEXT,
  source_file TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  "contract_number" TEXT,
  "award_date" TEXT,
  "vendor_name" TEXT,
  "contract_amount" NUMERIC,
  "project_description" TEXT
);
```

### Example 2: Complex Document (Bid Tabs)

**Input PDF**: `DA00653_Bid_Tabs.pdf`

**Extracted Data**:
```json
{
  "contract_id": "DA00653",
  "letting_date": "09/29/2025",
  "vendor_names": ["RILEY PAVING INC", "WHITEHURST PAVING CO INC"],
  "table": {
    "item_line_number": [1, 2, 3],
    "item_description": ["MOBILIZATION", "AST DOUBLE SEAL", "EMULSION"],
    "item_quantity": [1, 380471, 232657],
    "vendor_1_unit_price": [101000.00, 1.76, 2.50],
    "vendor_2_unit_price": [112000.00, 1.71, 2.44]
  },
  "bid_values": [
    {"vendor": "RILEY PAVING INC", "bid_value": 1387101.46, "rank": 1},
    {"vendor": "WHITEHURST PAVING CO INC", "bid_value": 1414798.49, "rank": 2}
  ]
}
```

**Database Schema** - Normalized Relational Tables:

**Main Table**:
```sql
CREATE TABLE "DA00653_Bid_Tabs" (
  id SERIAL PRIMARY KEY,
  document_type TEXT,
  source_file TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  "contract_id" TEXT,
  "letting_date" TEXT,
  "vendor_names" JSONB  -- Simple array kept as JSONB
);
```

**Related Table 1** - Item Breakdown:
```sql
CREATE TABLE "DA00653_Bid_Tabs_table" (
  id SERIAL PRIMARY KEY,
  da00653_bid_tabs_id INTEGER NOT NULL,  -- Foreign key
  row_index INTEGER,
  "item_line_number" NUMERIC,
  "item_description" TEXT,
  "item_quantity" NUMERIC,
  "vendor_1_unit_price" NUMERIC,
  "vendor_2_unit_price" NUMERIC
);
```

**Related Table 2** - Bid Values:
```sql
CREATE TABLE "DA00653_Bid_Tabs_bid_values" (
  id SERIAL PRIMARY KEY,
  da00653_bid_tabs_id INTEGER NOT NULL,  -- Foreign key
  array_index INTEGER,
  "vendor" TEXT,
  "bid_value" NUMERIC,
  "rank" NUMERIC
);
```

**Querying Related Data**:
```sql
-- Get all line items for a specific bid
SELECT 
  main.contract_id,
  main.letting_date,
  items.item_description,
  items.item_quantity,
  items.vendor_1_unit_price
FROM "DA00653_Bid_Tabs" main
JOIN "DA00653_Bid_Tabs_table" items 
  ON items.da00653_bid_tabs_id = main.id
WHERE main.id = 1
ORDER BY items.row_index;

-- Get winning bid information
SELECT 
  main.contract_id,
  bids.vendor,
  bids.bid_value,
  bids.rank
FROM "DA00653_Bid_Tabs" main
JOIN "DA00653_Bid_Tabs_bid_values" bids 
  ON bids.da00653_bid_tabs_id = main.id
WHERE bids.rank = 1;
```

## API Endpoints

- `GET /` - Web UI
- `GET /health` - Health check
- `POST /processar-batch` - Start batch ETL processing
- `POST /gerar-relatorio` - Generate executive report
- `POST /limpar-tabelas` - Drop all database tables
- `GET /poll-sqs` - Manual SQS polling (for debugging)

## Error Handling

- **Rate Limiting**: 30-second delay between Bedrock API calls
- **Type Detection**: Falls back to TEXT if column type cannot be inferred
- **Batch Processing**: Continues even if individual files fail
- **Logging**: Detailed console output for debugging

## Performance

- **Extraction**: ~30-45 seconds per PDF (Bedrock API)
- **Batch Processing**: Includes 30s rate limit between files
- **Report Generation**: ~30-60 seconds (depends on data volume)

## Security

- ✅ All credentials in `.env` (gitignored)
- ✅ No hardcoded secrets in code
- ✅ AWS IAM permissions for S3, SQS, Bedrock, RDS
- ✅ Database password encryption in transit

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Open a Pull Request

## License

MIT License - See LICENSE file for details

## Support

For issues or questions, please open a GitHub issue.
