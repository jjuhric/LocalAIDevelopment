import os
import boto3
import logging
import time
from fastapi import FastAPI
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MEMORY_BUCKET_NAME = os.getenv("MEMORY_BUCKET_NAME", "default-memory-bucket")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local").lower()

# --- NEW HELPER FUNCTION ---
def get_s3_client():
    """Returns a LocalStack client if local, or a real AWS client if in prod."""
    if ENVIRONMENT == "local":
        return boto3.client(
            "s3",
            endpoint_url="http://localstack:4566", # Point to the local Docker container
            aws_access_key_id="test",              # Dummy credentials required by boto3
            aws_secret_access_key="test",
            region_name="us-east-1"
        )
    return boto3.client("s3")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API booting up. Checking AWS Infrastructure...")
    
    s3_client = get_s3_client() # Use the helper function here!
    
    max_retries = 5
    retry_delay = 3
    
    for attempt in range(max_retries):
        try:
            response = s3_client.list_buckets()
            existing_buckets = [bucket['Name'] for bucket in response.get('Buckets', [])]
            if MEMORY_BUCKET_NAME not in existing_buckets:
                s3_client.create_bucket(Bucket=MEMORY_BUCKET_NAME)
                logger.info(f"Bucket '{MEMORY_BUCKET_NAME}' created.")
            break 
        except Exception as e:
            logger.warning(f"AWS not ready (Attempt {attempt + 1}/{max_retries}). Waiting {retry_delay}s...")
            time.sleep(retry_delay)
    else:
        logger.error("CRITICAL: Failed to connect to AWS/LocalStack.")
        
    yield 
    
    logger.info("API shutting down gracefully.")