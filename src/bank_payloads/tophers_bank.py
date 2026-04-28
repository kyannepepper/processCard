"""Tophers Bank payload builder."""

from ...lambda_handler import _get_cc_raw, _clean_card_number, _safe_float_amount


def build_tophers_bank_payload(body):
    """Build payload for Tophers Bank API."""
    url = "https://lp4uqktsqg.execute-api.us-west-2.amazonaws.com/default/doRequest"

    card_type = body.get("card_type", "").lower()

    if card_type == "deposit":
        txn_type = "debit"
        withdrawal = False
    elif card_type == "credit":
        txn_type = "credit"
        withdrawal = False
    else:
        txn_type = "debit"
        withdrawal = True

    payload = {
        "cch_name": "kklein_cch",
        "cch_token": "P2fY6tNk",
        "card_number": _clean_card_number(_get_cc_raw(body)),
        "cvv": body.get("cvv", ""),
        "exp_date": body.get("exp_date", ""),
        "amount": _safe_float_amount(body),
        "transaction_type": txn_type,
        "merchant_name": body.get("merchant_name", ""),
        "withdrawal": withdrawal,
    }
    return payload, url, {}