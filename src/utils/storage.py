import json
import logging

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def upload_file_to_s3(bucket_name, file, filename):
    logger.info(f"upload file {filename} to s3 bucket {bucket_name}")
    try:
        s3 = boto3.resource("s3")
        s3object = s3.Object(bucket_name, filename)
        s3object.put(
            Body=file,
        )
        return True

    except Exception:
        logger.exception(
            f"An exception occurred when uploading file {filename} to s3 bucket {bucket_name}"
        )
        return False


def upload_json_to_s3(bucket_name, json_data, filename):
    logger.info(f"upload json {filename} to s3 bucket {bucket_name}")
    try:
        s3 = boto3.resource("s3")
        s3object = s3.Object(bucket_name, filename)
        s3object.put(
            Body=(bytes(json.dumps(json_data).encode("UTF-8"))),
            ContentType="application/json",
        )
        return True

    except Exception:
        logger.exception(
            f"An exception occurred when uploading json {filename} to s3 bucket {bucket_name}"
        )
        return False
