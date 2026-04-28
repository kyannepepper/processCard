"""Jeffs Bank payload builder."""

from ...lambda_handler import _get_cc_raw, _get_card_holder, _clean_card_number


def build_jeffs_bank_payload(body):
    """Build payload for Jeffs Bank API."""
    url = "https://9q350g4063.execute-api.us-west-2.amazonaws.com/default/handleTransaction"
    payload = {
        "cch_name": "klein_cch",
        "cch_token": "Wt2lITD0",
        "card_holder": _get_card_holder(body),
        "card_num": _clean_card_number(_get_cc_raw(body)),
        "exp_date": body.get("exp_date", ""),
        "cvv": body.get("cvv", ""),
        "card_zip": body.get("card_zip", ""),
        "txn_type": body.get("card_type", "").lower(),
        "merchant": body.get("merchant_name", ""),
        "amount": body.get("amount", ""),
        "timestamp": body.get("timestamp", ""),
    }
    return payload, url, {}