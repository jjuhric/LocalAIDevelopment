import boto3
import os
from langchain_core.tools import tool
# Import our new helper function
from app.core.config import MEMORY_BUCKET_NAME, ENVIRONMENT, get_s3_client 

@tool
def save_to_long_term_memory(document_title: str, content: str) -> str:
    """
    Saves exact files, long documents, or scripts into S3 storage.
    Use this for exact files or specific documents that require a title.
    """
    s3_client = get_s3_client() # Use the helper function!
    backup_dir = "/app/backup"
    
    try:
        file_key = f"{document_title}.txt"
        s3_client.put_object(Bucket=MEMORY_BUCKET_NAME, Key=file_key, Body=content)
        
        if ENVIRONMENT != "prod":
            os.makedirs(backup_dir, exist_ok=True)
            with open(os.path.join(backup_dir, file_key), "w", encoding="utf-8") as f:
                f.write(content)
                
        return f"SUCCESS: '{document_title}' saved to memory bucket."
    except Exception as e:
        return f"ERROR: {str(e)}"

@tool
def read_from_long_term_memory(document_title: str) -> str:
    """
    Retrieves exact files from S3 by title.
    Use this to recall specific files you saved previously.
    """
    s3_client = get_s3_client() # Use the helper function!
    try:
        response = s3_client.get_object(Bucket=MEMORY_BUCKET_NAME, Key=f"{document_title}.txt")
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        return f"ERROR: {str(e)}"