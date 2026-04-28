# Topher's Bank — API Documentation

## Document Overview

Welcome to the Topher's Bank API. This document is your complete guide to submitting transaction requests to our bank on behalf of cardholders. This API is intended **only** for authorized Credit Card Clearinghouses (CCH). Your clearinghouse credentials will be provided to you before you begin testing. Without valid credentials, all requests will be rejected.


## URL

Send all requests as an **HTTPS POST** to:

```
https://lp4uqktsqg.execute-api.us-west-2.amazonaws.com/default/doRequest
```

## Parameters

All parameters must be sent in the body of the POST request.

| Field | Type | Required | Description |
|---|---|---|---|
| `cch_name` | String | Yes | Your clearinghouse's registered name (provided to you) |
| `cch_token` | String | Yes | Your clearinghouse's authentication token (provided to you) |
| `card_number` | String | Yes | The 16-digit card number as a string (no spaces or dashes) |
| `cvv` | String | Yes | The 3-digit CVV from the card |
| `exp_date` | String | Yes | Card expiration date — accepted in `MM/YY` (e.g. `"09/27"`) or `YYYY-MM` (e.g. `"2027-09"`) format |
| `amount` | Number | Yes | Transaction amount as a positive decimal (e.g., `52.75`) |
| `transaction_type` | String | Yes | Either `"debit"` or `"credit"` |
| `merchant_name` | String | Yes | Name of the merchant where the purchase is taking place |
| `withdrawal` | Boolean | Yes | `True` for withdrawal, `False` for Deposit |

### Field Notes

- `card_number` must be sent as a **string**, not a number. Leading zeros must be preserved.
- `amount` must be **greater than zero**. Zero or negative amounts will be rejected.
- `transaction_type` + `withdrawal` work together to determine the direction of the transaction:

| `transaction_type` | `withdrawal` | Effect |
|---|---|---|
| `"debit"` | `true` | Deduct `amount` from the account's `AvailableBalance` (purchase or ATM withdrawal) |
| `"debit"` | `false` | Add `amount` to the account's `AvailableBalance` (deposit) |
| `"credit"` | `false` | Add `amount` to the account's `CreditBalance` (credit card charge) |
| `"credit"` | `true` | Reduce the account's `CreditBalance` by `amount` (credit card payment or refund) |

- `exp_date` must match exactly what is stored on the account — we validate it as part of fraud prevention.
- `cvv` is required but is currently passed through for logging purposes only; hash validation is not yet enforced.

---

## Authentication and Security

Every request **must** include your `cch_name` and `cch_token` in the request body. These credentials identify your clearinghouse and authorize you to submit transactions on behalf of cardholders.

- Your credentials will be issued to you before testing begins.
- Credentials are specific to your clearinghouse — do not share them.
- If your token is compromised, contact us immediately to have it rotated.
- Requests from clearinghouses that are not in our registry, that supply an incorrect token, or whose account is marked inactive will receive a `401 Unauthorized` response and the transaction will not be processed.
- All data is transmitted over HTTPS. Never send requests over plain HTTP.
- CVV values submitted in requests are never returned in any response.

---

## Example Request

Here is a complete example of a debit transaction submitted using `curl`:

```bash
curl -X POST "https://lp4uqktsqg.execute-api.us-west-2.amazonaws.com/default/doRequest" \
  -H "Content-Type: application/json" \
  -d '{
    "cch_name": "your_cch_name",
    "cch_token": "your_cch_token",
    "card_number": "4111111111111111",
    "cvv": "456",
    "exp_date": "09/27",
    "amount": 78.50,
    "transaction_type": "debit",
    "merchant_name": "Campus Bookstore",
    "withdrawal": true
  }'
```

## Response

All responses are returned as a JSON object with the following structure:

```json
{
  "statusCode": 200,
  "outcome": "accepted",
  "message": "Transaction approved.",
  "transaction_id": "txn_a3f92b10c4"
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `statusCode` | Integer | HTTP status code reflecting the result |
| `outcome` | String | Either `"accepted"` or `"declined"` (only present when card/account was found) |
| `message` | String | A human-readable description of the result |
| `transaction_id` | String | Unique ID for the transaction (present on accepted or declined transactions) |

### HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Request was successfully processed (check `outcome` for accepted/declined) |
| `400` | Bad Request — a required field is missing or malformed |
| `401` | Unauthorized — your `cch_name` or `cch_token` is invalid or your clearinghouse is inactive |
| `404` | Account not found — no account exists for the provided card number |
| `422` | Unprocessable — the card is expired, the CVV does not match, or the amount is invalid |
| `500` | Server error — something went wrong on our end; try again |

### Outcome Messages

When the status code is `200`, the `outcome` will be either `"accepted"` or `"declined"`. Here are the possible `message` values:

| Outcome | Message | Explanation |
|---|---|---|
| `accepted` | `"Transaction approved."` | Everything checked out; funds have been moved |
| `declined` | `"Insufficient funds."` | Debit amount exceeds the available balance |
| `declined` | `"Credit limit exceeded."` | Credit would push the balance past the credit limit |
| `declined` | `"Account is frozen."` | The account has been frozen and cannot be used |
| `declined` | `"Account is closed."` | The account has been closed |
| `declined` | `"Account is on hold."` | The account is temporarily restricted |
| `declined` | `"Account is overdrawn."` | The account is currently overdrawn |

---

## Troubleshooting Guide

Having trouble? Work through this list before reaching out.

**Getting a `401`?**
- Double-check that `cch_name` and `cch_token` are both present and spelled correctly.
- Both fields are case-sensitive.
- Make sure you are using the credentials assigned to your clearinghouse.
- Your clearinghouse account may have been deactivated — contact us to verify your status.

**Getting a `400`?**
- Check that all required fields are included in the body.
- Make sure `amount` is a number (not a string like `"52.75"`).
- Confirm `transaction_type` is exactly `"debit"` or `"credit"` — no other values are accepted.
- Confirm `exp_date` is in `MM/YY` (e.g., `"09/27"`) or `YYYY-MM` (e.g., `"2027-09"`) format.

**Getting a `404`?**
- The card number you submitted does not match any account in our system.
- Confirm you are sending `card_number` as a string with no spaces or dashes.

**Getting a `422`?**
- The `exp_date` you sent may not match what is on file — it must be an exact match (in whichever format the account was created with: `MM/YY` or `YYYY-MM`).
- `amount` must be greater than 0.

**Not sure what went wrong?**
- Log the full response body including `statusCode`, `outcome`, and `message`.
- Having that information ready will make troubleshooting much faster.

---

## Test Accounts

Before testing begins, you will be provided with a set of test card numbers and their associated details (CVV, expiration date, balance). Use these accounts during your development and testing phase.

### Sample Request JSON

Replace `cch_name` and `cch_token` with your issued clearinghouse credentials. The card details below correspond to a test account in our system:

```json
{
  "cch_name": "your_cch_name",
  "cch_token": "your_cch_token",
  "card_number": "4111111111111111",
  "cvv": "456",
  "exp_date": "09/27",
  "amount": 52.75,
  "transaction_type": "debit",
  "merchant_name": "Campus Bookstore",
  "withdrawal": true
}
```

**Notes on the sample:**
- `amount` is a **number**, not a string — do not quote it.
- `withdrawal` is a **boolean** — do not quote it.
- For a credit card charge, use `"transaction_type": "credit"` and `"withdrawal": false`.
- For a deposit, use `"transaction_type": "debit"` and `"withdrawal": false`.

---

*Questions or issues during testing? Contact Topher Stubbs.*
