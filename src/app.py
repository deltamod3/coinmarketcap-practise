import concurrent.futures
import logging
import os
import re
from datetime import datetime

import requests

import utils.dynamodb as dynamodb
import utils.storage as storage

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cmc_api_key = os.environ.get("CMC_API_KEY")
bucket_name = os.environ.get("BUCKET_NAME")
coin_table_name = os.environ.get("COIN_TABLE_NAME")
stage_name = os.environ.get("STAGE_NAME")

current_date = datetime.utcnow()
str_datetime = datetime.isoformat(current_date)
str_folder_key = datetime.strftime(current_date, "%Y/%m/%d/%H")

headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": cmc_api_key}


def get_listings_latest():
    logger.info("Get listings latest...")

    ranks = []

    MAX_LISTING_PAGES = 5
    cnt = 0
    while cnt < MAX_LISTING_PAGES:
        cnt += 1
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        parameters = {"start": len(ranks) + 1, "limit": 5000}
        data = requests.get(url, params=parameters, headers=headers).json()

        if data["status"]["error_code"] != 0:
            logger.error(data["status"]["error_message"])
            break

        this_batch = data["data"]

        ranks += this_batch

        if len(this_batch) == 0:
            break

    if cnt == MAX_LISTING_PAGES:
        raise Exception(
            f"Exceeded {MAX_LISTING_PAGES} pages for 'get_listings_latest()'"
        )

    return ranks


def get_metadata(ids, batch_size=500, invalid_ids=None):
    logger.info("Get metadata...")
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/info"

    all_ids = [str(i) for i in ids]

    invalid_ids = invalid_ids or set()

    metadata = {}
    ids_len = len(all_ids)
    for nx in range(0, ids_len, batch_size):
        retry = 0
        while retry < 2:
            batch = list(set(all_ids[nx : min(nx + batch_size, ids_len)]) - invalid_ids)

            parameters = {"id": ",".join(batch)}

            response = requests.get(url, params=parameters, headers=headers).json()

            error_message = response.get("status", {}).get("error_message")
            logger.info(f"cryptocurrency/info {nx} {retry} {error_message}")
            if error_message:
                groups = re.match(
                    r'Invalid value(?:s)? for "id": "([0-9,]+)"',
                    error_message,
                )
                if not groups:
                    raise Exception(
                        f"'get_metadata()' can't match error: '{error_message}'"
                    )
                invalid_ids |= set(groups[1].split(","))
                retry += 1
                continue
            else:
                metadata.update(response["data"])
                break

        if retry >= 2:
            raise Exception(f"Too many retries for 'get_metadata()'")

    return metadata, invalid_ids


def extract_prices(listing):
    for item in listing:
        yield {
            "id": item["id"],
            "symbol": item["symbol"],
            "price": item.get("quote", {}).get("USD", {}).get("price", 0),
        }


def extract_websites(update_items, metadata):
    for item in update_items:
        url = (
            metadata.get(str(item["id"]), {}).get("urls", {}).get("website", [])
            or [None]
        )[0]
        if url:
            yield {
                "id": item["id"],
                "url": url,
            }


def download_frontend_upload_to_s3(coin):
    logger.info("download_frontend_upload_to_s3")
    logger.info(coin["url"])
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36"
        }
        page = requests.get(coin["url"], verify=False, headers=headers, timeout=5)
        storage.upload_file_to_s3(
            bucket_name=bucket_name,
            file=page.text,
            filename=f'frontpages/{str_folder_key}/00/{coin["id"]}.html',
        )
        dynamodb.update_item(
            table_name=coin_table_name,
            id=coin["id"],
            item={"url": coin["url"], "last_update": str_datetime},
        )
        return True
    except Exception:
        logger.exception(
            f'An exception occurred when downloading front page {coin["url"]}'
        )
        return False


def lambda_handler(event, context):
    logger.info("Start CMC engine function")
    try:
        start = datetime.utcnow()

        # Load all coins from database
        logger.info("## coins from database")
        coins = dynamodb.scan_table(table_name=coin_table_name)

        if coins is None:
            raise Exception("Please check dynamodb table")

        logger.info("## coins_mapping")
        coins_mapping = {coin["id"]: coin for coin in coins}

        # Call the CMC get_listings_latest api
        logger.info("## listings")
        listings = get_listings_latest()

        # Get prices
        logger.info("## prices")
        prices = list(extract_prices(listings))

        # Upload listing, prices to S3 bucket
        storage.upload_json_to_s3(
            bucket_name=bucket_name,
            json_data=listings,
            filename=f"raw/{str_folder_key}/00/raw.json",
        )
        storage.upload_json_to_s3(
            bucket_name=bucket_name,
            json_data=prices,
            filename=f"prices/{str_folder_key}/00/prices.json",
        )

        # Check coin is new or existed in database
        new_coins = []
        update_items = []
        for item in listings:
            if item["id"] not in coins_mapping:
                update_items.append(item)

                # If coin is new, add item to new_coins queue
                new_item = {
                    "id": item["id"],
                    "symbol": item["symbol"],
                    "name": item["name"],
                }

                new_coins.append(new_item)
            else:
                # If coin is existed, check last_update
                coin = coins_mapping[item["id"]]
                if (
                    "last_update" not in coin
                    or (current_date - datetime.fromisoformat(coin["last_update"])).days
                    >= 10
                ):
                    update_items.append(item)

        # Put new coins to the database
        if new_coins:
            dynamodb.batch_put_item(table_name=coin_table_name, items=new_coins)

        # If there are items to update metadata
        if update_items:
            # Get all ids from update_items
            all_ids = {item["id"] for item in update_items}

            # Call the CMC get_metadata api
            logger.info("## metadata, invalid_ids")
            metadata, invalid_ids = get_metadata(ids=all_ids)

            storage.upload_json_to_s3(
                bucket_name=bucket_name,
                json_data=metadata,
                filename=f"metadata/{str_folder_key}/00/metadata.json",
            )

            # AWS lambda doesn't support multiprocessing
            # https://stackoverflow.com/questions/34005930/multiprocessing
            # -semlock-is-not-implemented-when-running-on-aws-lambda
            logger.info("execute_concurrently")
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                    executor.map(
                        download_frontend_upload_to_s3,
                        extract_websites(update_items, metadata),
                    )
            except Exception:
                logger.exception("An exception occurred when execute_concurrently")

        end = datetime.utcnow()

        logger.info(f"Total seconds: {(end - start).total_seconds()}")

    except Exception:
        logger.exception("An exception occurred")
