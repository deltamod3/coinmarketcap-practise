import logging
import os

import boto3
from boto3.dynamodb.conditions import Key

env_stage = os.environ.get("ENV_STAGE")
if env_stage == "local":
    dynamodb = boto3.resource("dynamodb", endpoint_url="http://dynamodb:8000")
else:
    dynamodb = boto3.resource("dynamodb")

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def scan_table(table_name):
    logger.info(f"Scan table {table_name}")
    try:
        table = dynamodb.Table(table_name)
        response = table.scan()
        data = response["Items"]

        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            data.extend(response["Items"])

        return data

    except Exception:
        logger.exception(f"An exception occurred when scanning table {table_name}")
        return None


def put_item(table_name, item):
    logger.info(f"Put item to table {table_name}")
    try:
        table = dynamodb.Table(table_name)
        return table.put_item(Item=item)

    except Exception:
        logger.exception(
            f"An exception occurred when putting item to table {table_name}"
        )
        return None


# def get_item_by_id(table_name, id):
#     logger.info(f'get item from table {table_name}')
#     try:
#         table = dynamodb.Table(table_name)
#         response = table.query(
#             KeyConditionExpression=Key('id').eq(id)
#         )
#         item = response['Items'][0]
#         return item
#
#     except Exception:
#         logger.exception(f'An exception occurred when querying table {table_name}')
#         return None


def update_item(table_name, id, item):
    logger.info(f"update item for table {table_name}")
    try:
        table = dynamodb.Table(table_name)
        update_expression = "SET {}".format(",".join(f"#{p}=:{p}" for p in item))
        expression_attribute_names = {f"#{p}": p for p in item}
        expression_attribute_values = {f":{p}": v for p, v in item.items()}
        table.update_item(
            Key={"id": id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )

    except Exception:
        logger.exception(
            f"An exception occurred when updating item to table {table_name}"
        )
        return None


def batch_put_item(table_name, items):
    logger.info(f"Batch put items to table {table_name}")
    try:
        table = dynamodb.Table(table_name)
        with table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)

        return True

    except Exception:
        logger.exception(
            f"An exception occurred when batch putting items to table {table_name}"
        )
        return None


# def batch_update_item(table_name, items):
#     logger.info(f'Batch update items to table {table_name}')
#     try:
#         table = dynamodb.Table(table_name)
#         for item in items:
#             update_expression = 'SET {}'.format(','.join(f'#{p}=:{p}' for p in item))
#             expression_attribute_names = {f'#{p}': p for p in item}
#             expression_attribute_values = {f':{p}': v for p, v in item.items()}
#             table.update_item(
#                 Key={
#                     "id": item["id"]
#                 },
#                 UpdateExpression=update_expression,
#                 ExpressionAttributeNames=expression_attribute_names,
#                 ExpressionAttributeValues=expression_attribute_values,
#             )
#
#     except Exception:
#         logger.exception(f'An exception occurred when batch updating items to table {table_name}')
#         return None
