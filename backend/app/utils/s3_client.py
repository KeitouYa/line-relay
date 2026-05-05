import boto3
from app.config import settings

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )

def upload_video(file_path: str, object_key: str) -> str:
    client = get_s3_client()
    client.upload_file(file_path, settings.s3_bucket, object_key)
    return f"{settings.s3_endpoint}/{settings.s3_bucket}/{object_key}"

def get_download_url(object_key: str, expires_in: int = 3600) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": object_key},
        ExpiresIn=expires_in,
    )