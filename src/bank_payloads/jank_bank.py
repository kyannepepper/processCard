"""Jank Bank payload builder."""

from ...lambda_handler import _get_cc_raw, _clean_card_number


def build_jank_bank_payload(body):
    """Build payload for Jank Bank API."""
    url = "https://yt1i4wstmb.execute-api.us-west-2.amazonaws.com/default/transact"
    card_type = body.get("card_type", "").lower()
    acct = (
        (body.get("account_num") or body.get("jank_account_num") or "").strip()
        or _clean_card_number(_get_cc_raw(body))
    )
    payload = {
        "cch_name": "kklein",
        "cch_token": "ce0F9hxhySlOVIfEUYP693Cd7pdXgpl7",
        "account_num": acct,
        "card_num": _clean_card_number(_get_cc_raw(body)),
        "exp_date": body.get("exp_date", ""),
        "cvv": body.get("cvv", ""),
        "amount": str(body.get("amount", "")),
        "type": card_type,
        "merchant": body.get("merchant_name", ""),
    }
    return payload, url, {}