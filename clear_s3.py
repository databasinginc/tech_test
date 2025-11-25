import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# Configure S3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

bucket = os.getenv('S3_BUCKET_NAME')
prefix = '2023 nc d1/'

print(f"Listing objects in s3://{bucket}/{prefix}...")

# List all objects
paginator = s3.get_paginator('list_objects_v2')
pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

objects_to_delete = []
for page in pages:
    if 'Contents' in page:
        for obj in page['Contents']:
            objects_to_delete.append({'Key': obj['Key']})

print(f"Found {len(objects_to_delete)} objects to delete")

if objects_to_delete:
    # Delete in batches of 1000 (API limit)
    for i in range(0, len(objects_to_delete), 1000):
        batch = objects_to_delete[i:i+1000]
        response = s3.delete_objects(
            Bucket=bucket,
            Delete={'Objects': batch}
        )
        print(f"Deleted {len(batch)} objects (batch {i//1000 + 1})")
    
    print(f"\nOK All {len(objects_to_delete)} objects deleted from s3://{bucket}/{prefix}")
else:
    print("No objects found to delete")
