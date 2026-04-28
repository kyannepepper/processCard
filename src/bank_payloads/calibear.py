"""CaliBear payload builder."""

import os
from ...lambda_handler import _get_cc_raw, _clean_card_number, _safe_float_amount


def build_calibear_payload(body):
    """Build payload for CaliBear API."""
    url = "https://api.calibear.credit/transaction/"

    card_type = body.get("card_type", "").lower()
    txn_type = "deposit" if card_type == "deposit" else "withdrawal"

    ch_id = os.environ.get("CALIBEAR_CLEARINGHOUSE_ID", "klein_k_cch").strip()
    payload = {
        "clearinghouse_id": ch_id,
        "card_number": _clean_card_number(_get_cc_raw(body)),
        "amount": _safe_float_amount(body),
        "transaction_type": txn_type,
        "merchant_name": body.get("merchant_name", ""),
    }
    extra_headers = {
        "x-api-key": "credential_token_fy6452h2zqu7eeqtul1p36p",
    }
    return payload, url, extra_headers