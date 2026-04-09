import json
import os
import uuid
import boto3
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone
from decimal import Decimal


def lambda_handler(event, context):
    dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
    merchant_table = dynamodb.Table("Merchant")

    body = {}
    try:
        body = json.loads(event.get("body", "{}") or "{}")
    except Exception as e:
        print("Invalid JSON body:", repr(e))
        return _respond_and_log(dynamodb, body, format_response(400, "Declined"))

    try:
        merchant_name  = body.get("merchant_name",  "").strip()
        merchant_token = body.get("merchant_token", "").strip()

        if not authMerchant(merchant_table, merchant_name, merchant_token):
            return _respond_and_log(
                dynamodb, body, format_response(401, "Declined")
            )

        bank = body.get("bank", "").strip()
        resolved_bank = resolve_bank_name(bank)
        payload, url, extra_headers = make_payload(body, resolved_bank)

        if payload is None:
            return _respond_and_log(
                dynamodb, body, format_response(400, "Declined")
            )

        response = call_bank_api(url, payload, extra_headers)
        return _respond_and_log(dynamodb, body, response)

    except KeyError:
        return _respond_and_log(
            dynamodb, body, format_response(400, "Declined")
        )
    except Exception as e:
        print("Unhandled exception:", repr(e))
        return _respond_and_log(
            dynamodb, body, format_response(500, "Internal Server Error")
        )


def _respond_and_log(dynamodb, body, response):
    write_transaction_log(dynamodb, body, response)
    return response


def write_transaction_log(dynamodb, body, api_response):
    try:
        table_name = os.environ.get("TRANSACTION_TABLE", "Transaction")
        log_table = dynamodb.Table(table_name)
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
    code = api_response.get("statusCode", 500)
    message = ""
    try:
        inner = json.loads(api_response.get("body", "{}") or "{}")
        message = (inner.get("message") or "").strip()
    except Exception:
        pass

    if code >= 500:
        return "Error"
    if message == "Accepted":
        return "Approved"
    return "Declined"


def _amount_for_log(body):
    raw = body.get("amount", "")
    if raw is None or raw == "":
        return "0"
    try:
        return str(Decimal(str(raw)))
    except Exception:
        return str(raw)


def _last_four_card_or_account(body):
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


def authMerchant(table, name, token):
    if not name or not token:
        return False
    try:
        result = table.get_item(Key={"Name": name, "Token": token})
        return "Item" in result
    except Exception as e:
        print("DynamoDB error:", repr(e))
        return False


def resolve_bank_name(bank):
    key = (bank or "").strip().lower().replace("'", "")
    aliases = {
        "jeffs bank": "Jeffs Bank",
        "jeff bank": "Jeffs Bank",
        "corbin bank": "Corbin Bank",
        "calibear": "CaliBear",
        "calibear credit union": "CaliBear",
        "jank bank": "Jank Bank",
        "tophers bank": "Tophers Bank",
        "wild west bank": "Wild West Bank",
    }
    return aliases.get(key, bank.strip())


def make_payload(body, bank):
    builders = {
        "Jeffs Bank":    _payload_jeffs_bank,
        "Corbin Bank":   _payload_corbin_bank,
        "CaliBear":      _payload_calibear,
        "Jank Bank":     _payload_jank_bank,
        "Tophers Bank":  _payload_tophers_bank,
        "Wild West Bank": _payload_wild_west_bank,
    }

    builder = builders.get(bank)
    if builder is None:
        print(f"Unsupported bank: {bank}")
        return None, None, None

    return builder(body)


def _payload_jeffs_bank(body):
    url = "https://9q350g4063.execute-api.us-west-2.amazonaws.com/default/handleTransaction"
    payload = {
        "cch_name":    "klein_cch",
        "cch_token":   "Wt2lITD0",
        "card_holder": _get_card_holder(body),
        "card_num":    _clean_card_number(_get_cc_raw(body)),
        "exp_date":    body.get("exp_date", ""),
        "cvv":         body.get("cvv", ""),
        "card_zip":    body.get("card_zip", ""),
        "txn_type":    body.get("card_type", "").lower(),
        "merchant":    body.get("merchant_name", ""),
        "amount":      body.get("amount", ""),
        "timestamp":   body.get("timestamp", ""),
    }
    return payload, url, {}


def _payload_corbin_bank(body):
    url = "https://xbu6ixwga4.execute-api.us-west-2.amazonaws.com/default/handleTransaction"

    card_type = body.get("card_type", "").lower()
    if card_type == "deposit":
        txn_type  = "deposit"
        card_type = "debit"
    else:
        txn_type = "withdrawal"

    payload = {
        "account_num":      _clean_card_number(_get_cc_raw(body)),
        "cvv":              body.get("cvv", ""),
        "exp_date":         body.get("exp_date", ""),
        "amount":           str(body.get("amount", "")),
        "transaction_type": txn_type,
        "card_type":        card_type,
    }
    user = os.environ.get("CORBIN_USERNAME", "").strip()
    pwd = os.environ.get("CORBIN_PASSWORD", "").strip()
    if not user or not pwd:
        print("Corbin Bank: set CORBIN_USERNAME and CORBIN_PASSWORD on the Lambda function.")
    extra_headers = {
        "username": user,
        "password": pwd,
    }
    return payload, url, extra_headers


def _payload_calibear(body):
    url = "https://api.calibear.credit/transaction/"

    card_type = body.get("card_type", "").lower()
    txn_type  = "deposit" if card_type == "deposit" else "withdrawal"

    ch_id = os.environ.get("CALIBEAR_CLEARINGHOUSE_ID", "klein_k_cch").strip()
    payload = {
        "clearinghouse_id": ch_id,
        "card_number":      _clean_card_number(_get_cc_raw(body)),
        "amount":           _safe_float_amount(body),
        "transaction_type": txn_type,
        "merchant_name":    body.get("merchant_name", ""),
    }
    extra_headers = {
        "x-api-key": "credential_token_fy6452h2zqu7eeqtul1p36p",
    }
    return payload, url, extra_headers


def _payload_jank_bank(body):
    url = "https://yt1i4wstmb.execute-api.us-west-2.amazonaws.com/default/transact"
    card_type = body.get("card_type", "").lower()
    acct = (
        (body.get("account_num") or body.get("jank_account_num") or "").strip()
        or _clean_card_number(_get_cc_raw(body))
    )
    payload = {
        "cch_name":    "kklein",
        "cch_token":   "ce0F9hxhySlOVIfEUYP693Cd7pdXgpl7",
        "account_num": acct,
        "card_num":    _clean_card_number(_get_cc_raw(body)),
        "exp_date":    body.get("exp_date", ""),
        "cvv":         body.get("cvv", ""),
        "amount":      str(body.get("amount", "")),
        "type":        card_type,
        "merchant":    body.get("merchant_name", ""),
    }
    return payload, url, {}


def _payload_tophers_bank(body):
    url = "https://lp4uqktsqg.execute-api.us-west-2.amazonaws.com/default/doRequest"

    card_type = body.get("card_type", "").lower()

    if card_type == "deposit":
        txn_type   = "debit"
        withdrawal = False
    elif card_type == "credit":
        txn_type   = "credit"
        withdrawal = False
    else:
        txn_type   = "debit"
        withdrawal = True

    payload = {
        "cch_name":         "kklein_cch",
        "cch_token":        "P2fY6tNk",
        "card_number":      _clean_card_number(_get_cc_raw(body)),
        "cvv":              body.get("cvv", ""),
        "exp_date":         body.get("exp_date", ""),
        "amount":           _safe_float_amount(body),
        "transaction_type": txn_type,
        "merchant_name":    body.get("merchant_name", ""),
        "withdrawal":       withdrawal,
    }
    return payload, url, {}


def _payload_wild_west_bank(body):
    url = "https://l25ft7pzu5wpwm3xtskoiks6rm0javto.lambda-url.us-west-2.on.aws/"

    card_type = body.get("card_type", "").lower()
    if card_type == "deposit":
        txn_type  = "deposit"
        card_type = "debit"
    else:
        txn_type = "withdrawal"

    payload = {
        "cch_name":             "klein_cch",
        "cch_token":            "b3V7nQ4L",
        "account_holder_name":  _get_card_holder(body),
        "account_number":       _clean_card_number(_get_cc_raw(body)),
        "transaction_type":     txn_type,
        "card_type":            card_type,
        "amount":               str(body.get("amount", "")),
    }
    return payload, url, {}


def call_bank_api(url, payload, extra_headers):
    wait_times        = [0, 2, 4, 8]
    timeout_per_attempt = 3

    for attempt in range(4):
        wait = wait_times[attempt]
        if wait > 0:
            print(f"Attempt {attempt + 1}: waiting {wait}s before retry...")
            time.sleep(wait)

        print(f"Attempt {attempt + 1} of 4 → {url}")

        try:
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            headers.update(extra_headers)

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=timeout_per_attempt) as response:
                response_body = response.read().decode("utf-8")
                print(f"Success on attempt {attempt + 1}: {response_body}")
                return interpret_bank_response(response_body, response.status)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            print(f"Attempt {attempt + 1} HTTP {e.code}: {body}")
            return interpret_bank_response(body, e.code)

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {repr(e)}")

    print("All 4 attempts timed out.")
    return format_response(504, "Internal Server Error - timed out")


def interpret_bank_response(response_body, http_status):
    try:
        outer = json.loads(response_body)
    except Exception:
        return format_response(200, "Declined")

    embedded_status = None
    if isinstance(outer.get("statusCode"), int):
        embedded_status = outer["statusCode"]

    data = outer
    if "body" in outer and isinstance(outer["body"], str):
        try:
            data = json.loads(outer["body"])
        except Exception:
            data = outer

    message = (
        data.get("message")
        or data.get("Message")
        or data.get("outcome")
        or data.get("Outcome")
        or outer.get("message")
        or outer.get("Message")
        or ""
    )
    message_l = message.strip().lower()

    status_field = str(data.get("status", "") or "").strip().lower()
    if status_field in ("success", "completed", "ok"):
        return format_response(200, "Accepted")

    if _response_indicates_accepted(message_l):
        return format_response(200, "Accepted")

    funds_phrases = [
        "insufficient",
        "credit limit",
        "insufficient funds",
        "insufficient credit",
        "credit limit exceeded",
        "insufficient_funds",
        "credit_limit_exceeded",
        "daily_limit_exceeded",
    ]
    if any(p in message_l for p in funds_phrases):
        return format_response(200, "Insufficient Funds")

    effective = embedded_status if embedded_status is not None else http_status
    if effective in (401, 400, 402, 403, 404, 422, 502):
        return format_response(effective, "Declined")

    return format_response(200, "Declined")


def _response_indicates_accepted(message_l: str) -> bool:
    if not message_l:
        return False
    if "declined" in message_l or "not authorized" in message_l:
        return False
    phrases = (
        "transaction accepted",
        "transaction approved",
        "transaction completed",
        "deposit successful",
        "withdrawal successful",
    )
    if any(p in message_l for p in phrases):
        return True
    if message_l == "approved":
        return True
    if message_l.rstrip(".") == "accepted":
        return True
    if message_l == "accepted":
        return True
    return False


def format_response(status_code, message):
    return {
        "statusCode": status_code,
        "body": json.dumps({"message": message})
    }


def _clean_card_number(raw):
    if raw is None:
        return ""
    return str(raw).replace(" ", "").replace("-", "")


def _get_cc_raw(body):
    return (
        body.get("cc_number")
        or body.get("cc_num")
        or body.get("card_num")
        or ""
    )


def _get_card_holder(body):
    return str(
        body.get("card_holder")
        or body.get("customer_name")
        or ""
    ).strip()


def _safe_float_amount(body):
    try:
        return float(body.get("amount", 0))
    except (TypeError, ValueError):
        return 0.0

