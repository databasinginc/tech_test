import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# AWS S3 client
s3 = boto3.client('s3', 
                  aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))

bucket = os.getenv('S3_BUCKET_NAME')
local_folder = r'C:\Users\anderson\Documents\edgevanta\2023 nc d1\2023-02-01_nc_d1'
s3_base_path = '2023 nc d1'

print(f"Uploading recursively from {local_folder} to s3://{bucket}/{s3_base_path}\n")

total = 0
for root, dirs, files in os.walk(local_folder):
    for filename in files:
        if filename.endswith('.pdf'):
            full_path = os.path.join(root, filename)
            
            # Calculate relative path
            relative_path = os.path.relpath(full_path, os.path.dirname(local_folder))
            s3_key = f"{s3_base_path}/{relative_path}".replace('\\', '/')
            
            print(f"Upload: {s3_key}")
            s3.upload_file(full_path, bucket, s3_key)
            total += 1

print(f"\nOK Upload completed! {total} file(s) sent")
