import json
import boto3
import logging
from typing import Any, Dict
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class S3Interface:
    def __init__(self, bucket: str) -> None:
        self.bucket: str = bucket
        self.s3: Any = boto3.client('s3')

    def load_json(self, filename: str) -> Dict[str, Any]:
        try:
            response: Any = self.s3.get_object(Bucket=self.bucket, Key=filename)
            data: Dict[str, Any] = json.loads(response['Body'].read().decode('utf-8'))
            return data
        except ClientError:
            return {}

    def save_json(self, filename: str, data: Dict[str, Any]) -> None:
        try:
            self.s3.put_object(Bucket=self.bucket, Key=filename, Body=json.dumps(data, indent=4))
        except Exception as e:
            logger.error(f"S3 Save Error: {e}")
