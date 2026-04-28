"""
ProcessCard - Main Lambda Handler

AWS Lambda function for processing card payments across multiple bank APIs.
"""

import json
import os
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal

import boto3


# Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
MERCHANT_TABLE = os.environ.get("MERCHANT_TABLE", "Merchant")
TRANSACTION_TABLE = os.environ.get("TRANSACTION_TABLE", "Transaction")

RETRY_BACKOFF_SECONDS = (0, 2, 4, 8)
HTTP_TIMEOUT_SECONDS = 3

# Allowed response messages
ALLOWED_MESSAGES = {
    "Approved.",
    "Declined - Insufficient Funds.",
    "Declined - Invalid Merchant Credentials.",
    "Error - Bank Not Available.",
    "Error - Bank Not Supported.",
    "Declined - Invalid Bank or Card Information.",
}

# Bank resolvers and builders
from .bank_payloads import (
    build_jeffs_bank_payload,
    build_corbin_bank_payload,
    build_calibear_payload,
    build_jank_bank_payload,
    build_tophers_bank_payload,
    build_wild_west_bank_payload,
)

BANK_BUILDERS = {
    "Jeffs Bank": build_jeffs_bank_payload,
    "Corbin Bank": build_corbin_bank_payload,
    "CaliBear": build_calibear_payload,
    "Jank Bank": build_jank_bank_payload,
    "Tophers Bank": build_tophers_bank_payload,
    "Wild West Bank": build_wild_west_bank_payload,
}

BANK_ALIASES = {
    "jeffs bank": "Jeffs Bank",
    "jeff bank": "Jeffs Bank",
    "corbin bank": "Corbin Bank",
    "corbin": "Corbin Bank",
    "calibear": "CaliBear",
    "calibear credit union": "CaliBear",
    "jank bank": "Jank Bank",
    "jankbank": "Jank Bank",
    "tophers bank": "Tophers Bank",
    "wild west bank": "Wild West Bank",
}


def respond(message: str):
    """Create a standard API Gateway response."""
    return {"statusCode": 200, "body": json.dumps({"message": _normalize(message)})}


def lambda_handler(event, context):
    """Main Lambda entry point."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    merchant_table = dynamodb.Table(MERCHANT_TABLE)

    body = {}
    try:
        body = json.loads(event.get("body", "{}") or "{}")
    except Exception as e:
        print("Invalid JSON body:", repr(e))
        return _respond_and_log(dynamodb, body, respond("Declined - Invalid Bank or Card Information."))

    try:
        merchant_name = body.get("merchant_name", "").strip()
        merchant_token = body.get("merchant_token", "").strip()

        if not auth_merchant(merchant_table, merchant_name, merchant_token):
            return _respond_and_log(
                dynamodb, body, respond("Declined - Invalid Merchant Credentials.")
            )

        bank = body.get("bank", "").strip()
        resolved_bank = resolve_bank_name(bank)
        payload, url, extra_headers = make_payload(body, resolved_bank)

        if payload is None:
            if resolved_bank and resolved_bank.strip():
                return _respond_and_log(dynamodb, body, respond("Error - Bank Not Supported."))
            return _respond_and_log(dynamodb, body, respond("Declined - Invalid Bank or Card Information."))

        response = call_bank_api(url, payload, extra_headers)
        return _respond_and_log(dynamodb, body, response)

    except Exception as e:
        print("Unhandled exception:", repr(e))
        return _respond_and_log(
            dynamodb, body, respond("Error - Bank Not Available.")
        )


def _respond_and_log(dynamodb, body, response):
    """Log transaction and return response."""
    write_transaction_log(dynamodb, body, response)
    return response


def write_transaction_log(dynamodb, body, api_response):
    """Write transaction to DynamoDB."""
    try:
        log_table = dynamodb.Table(TRANSACTION_TABLE)
        bank_display = resolve_bank_name(body.get("bank", "")) or body.get("bank", "").strip() or "Unknown"
        merchant_key = body.get("merchant_name", "").strip() or "Unknown"
        when = datetime.now(timezone.utc).isoformat()
        sort_key = f"{when}#{uuid.uuid4()}"
        item = {
            "MerchantName": merchant_key,
            "TransactionTime": sort_key,
            "BankName": bank_display,
            "LastFour": _last_four_card_or_account(body),
            "Amount": _amount_for_log(body),
            "DateTime": when,
            "Status": _log_status_from_response(api_response),
        }
        log_table.put_item(Item=item)
    except Exception as e:
        print("Transaction log write failed:", repr(e))


def _log_status_from_response(api_response):
    """Extract status from API response."""
    message = ""
    try:
        inner = json.loads(api_response.get("body", "{}") or "{}")
        message = (inner.get("message") or "").strip()
    except Exception:
        pass

    if message.startswith("Error -"):
        return "Error"
    if message == "Approved.":
        return "Approved"
    return "Declined"


def _amount_for_log(body):
    """Extract and format amount for logging."""
    raw = body.get("amount", "")
    if raw is None or raw == "":
        return "0"
    try:
        return str(Decimal(str(raw)))
    except Exception:
        return str(raw)


def _last_four_card_or_account(body):
    """Get last 4 digits of card or account."""
    digits = _clean_card_number(_get_cc_raw(body))
    if len(digits) >= 4:
        return digits[-4:]
    acct = (body.get("account_num") or body.get("jank_account_num") or "").strip()
    acct_alnum = "".join(c for c in acct if c.isalnum())
    if len(acct_alnum) >= 4:
        return acct_alnum[-4:]
    if len(digits) > 0:
        return digits
    return "N/A"


def auth_merchant(table, name, token):
    """Authenticate merchant against DynamoDB."""
    if not name or not token:
        return False
    try:
        result = table.get_item(Key={"Name": name, "Token": token})
        return "Item" in result
    except Exception as e:
        print("DynamoDB error:", repr(e))
        return False


def resolve_bank_name(bank):
    """Resolve bank alias to canonical name."""
    key = (bank or "").strip().lower().replace("'", "")
    return BANK_ALIASES.get(key, bank.strip())


def make_payload(body, bank):
    """Build payload for the specified bank."""
    builder = BANK_BUILDERS.get(bank)
    if builder is None:
        print(f"Unsupported bank: {bank}")
        return None, None, None
    return builder(body)


def call_bank_api(url, payload, extra_headers):
    """Call bank API with retry logic."""
    for attempt in range(4):
        wait = RETRY_BACKOFF_SECONDS[attempt]
        if wait > 0:
            print(f"Attempt {attempt + 1}: waiting {wait}s before retry...")
            time.sleep(wait)

        print(f"Attempt {attempt + 1} of 4 → {url}")

        try:
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            headers.update(extra_headers)

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
                response_body = response.read().decode("utf-8")
                print(f"Success on attempt {attempt + 1}: {response_body}")
                return interpret_bank_response(response_body, response.status)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            print(f"Attempt {attempt + 1} HTTP {e.code}: {body}")
            return interpret_bank_response(body, e.code)

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {repr(e)}")

    return respond("Error - Bank Not Available.")


def interpret_bank_response(response_body, status_code):
    """Parse bank API response."""
    try:
        data = json.loads(response_body)
        message = data.get("message", "").strip()
        if message in ALLOWED_MESSAGES:
            return respond(message)
        if message:
            return respond(message)
    except Exception:
        pass

    if status_code == 200:
        return respond("Approved.")
    if status_code == 400:
        return respond("Declined - Invalid Bank or Card Information.")
    if status_code == 401:
        return respond("Declined - Invalid Merchant Credentials.")
    if status_code == 403:
        return respond("Declined - Invalid Merchant Credentials.")
    if status_code == 422:
        return respond("Declined - Insufficient Funds.")

    return respond("Error - Bank Not Available.")


def _normalize(message):
    """Normalize message for response."""
    return message.strip()


def _get_cc_raw(body):
    """Extract raw card number from request body."""
    return body.get("card_num", "") or body.get("card_number", "")


def _get_card_holder(body):
    """Extract card holder name."""
    return (
        body.get("card_holder_name", "") or
        body.get("card_holder", "") or
        body.get("name_on_card", "") or
        ""
    ).strip()


def _clean_card_number(card_num):
    """Remove non-digit characters from card number."""
    return "".join(c for c in (card_num or "") if c.isdigit())


def _safe_float_amount(body):
    """Convert amount to safe float string."""
    try:
        return str(float(body.get("amount", 0)))
    except (ValueError, TypeError):
        return "0"