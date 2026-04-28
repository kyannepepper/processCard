"""Wild West Bank payload builder."""

from ...lambda_handler import _get_cc_raw, _get_card_holder, _clean_card_number


def build_wild_west_bank_payload(body):
    """Build payload for Wild West Bank API."""
    url = "https://l25ft7pzu5wpwm3xtskoiks6rm0javto.lambda-url.us-west-2.on.aws/"

    card_type = body.get("card_type", "").lower()
    if card_type == "deposit":
        txn_type = "deposit"
        card_type = "debit"
    else:
        txn_type = "withdrawal"

    payload = {
        "cch_name": "klein_cch",
        "cch_token": "b3V7nQ4L",
        "account_holder_name": _get_card_holder(body),
        "account_number": _clean_card_number(_get_cc_raw(body)),
        "transaction_type": txn_type,
        "card_type": card_type,
        "amount": str(body.get("amount", "")),
    }
    return payload, url, {}