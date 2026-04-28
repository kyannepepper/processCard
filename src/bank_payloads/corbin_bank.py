"""Corbin Bank payload builder."""

import os
from ...lambda_handler import _get_cc_raw, _clean_card_number


def build_corbin_bank_payload(body):
    """Build payload for Corbin Bank API."""
    url = "https://xbu6ixwga4.execute-api.us-west-2.amazonaws.com/default/handleTransaction"

    card_type = body.get("card_type", "").lower()
    if card_type == "deposit":
        txn_type = "deposit"
        card_type = "debit"
    else:
        txn_type = "withdrawal"

    payload = {
        "account_num": _clean_card_number(_get_cc_raw(body)),
        "cvv": body.get("cvv", ""),
        "exp_date": body.get("exp_date", ""),
        "amount": str(body.get("amount", "")),
        "transaction_type": txn_type,
        "card_type": card_type,
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