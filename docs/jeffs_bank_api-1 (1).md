# Jeffs Bank API Documentation

## Overview

This document describes the **Jeffs Bank** transaction API for the `/handleTransaction` endpoint.

The API accepts a transaction request from an authorized clearinghouse, validates the card information, attempts the transaction against the bank's account data, logs the transaction, and returns the result.

## Base Behavior

This Lambda routes requests based on the request path. For this document, only the following endpoint is relevant:

- `/handleTransaction`

The handler also accepts the API Gateway stage-prefixed path:

- `/default/handleTransaction`

## Endpoint

### `POST /handleTransaction`

Processes a debit, credit, or deposit transaction.

## Request Format

The request body must be JSON.

### Required JSON fields

| Field | Type | Description |
|---|---|---|
| `cch_name` | string | Name of the clearinghouse making the request. |
| `cch_token` | string | Clearinghouse token used for authentication. |
| `card_holder` | string | Card holder name. Must match the account record exactly. |
| `card_num` | string | Card number used to locate the account. |
| `exp_date` | string | Card expiration date. Must match the account record exactly. |
| `cvv` | string or number | Card CVV. Must match the account record exactly. |
| `card_zip` | string | Billing ZIP code. Must match the account record exactly. |
| `txn_type` | string | Transaction type. Supported values: `debit`, `credit`, `deposit`. |
| `merchant` | string | Merchant name or identifier. |
| `amount` | string or number | Transaction amount. Must be non-negative. |
| `timestamp` | string | Timestamp for the transaction. Also used when logging the transaction. |

### Example request body

```json
{
  "cch_name": "compas_cch",
  "cch_token": "abc123token",
  "card_holder": "Jeff Compas",
  "card_num": "4111111111111111",
  "exp_date": "12/27",
  "cvv": "123",
  "card_zip": "84790",
  "txn_type": "debit",
  "merchant": "Climbing Store",
  "amount": "42.50",
  "timestamp": "2026-03-26T18:45:00Z"
}
```

## Processing Flow

When a valid request is sent to `/handleTransaction`, the API performs these steps:

1. Parses the JSON request body.
2. Verifies that all required fields are present and not empty.
3. Authenticates the clearinghouse against the `CCH` table using:
   - partition key: `Name`
   - sort key: `Token`
4. Validates the card data against the `Account` table using `card_num`.
5. Applies the transaction to the account:
   - `debit`: subtracts from `balance`
   - `credit`: adds to `credit_used`, subject to `credit_limit`
   - `deposit`: adds to `balance`
6. Logs the full request plus the returned transaction status/message to the `Transaction` table.
7. Returns a JSON response describing the outcome.

## Authentication

The clearinghouse is authenticated using the `CCH` DynamoDB table.

A request is considered authorized only if a record exists with:

- `Name = cch_name`
- `Token = cch_token`

If no matching record exists, the API returns:

- HTTP status: `401`
- Message: `Clearinghouse Not Authorized.`

## Card Validation

The API retrieves the account record from the `Account` table using:

- `card_num`

The following fields must match the stored account record exactly:

- `cvv`
- `exp_date`
- `card_zip`
- `card_holder`

If one of these checks fails, the API returns:

- HTTP status: `403`
- Message format: `Invalid account info - bad or missing <field>`

Examples:

- `Invalid account info - bad or missing cvv`
- `Invalid account info - bad or missing exp_date`

## Supported Transaction Types

### `debit`

A debit transaction withdraws money from the account `balance`.

Behavior:
- If `amount` is negative, the request is rejected.
- If `balance < amount`, the transaction is declined.
- Otherwise, the amount is subtracted from `balance`.

Possible messages:
- `Accepted.`
- `Declined - Insufficient Funds.`
- `Negative amount not allowed.`

### `credit`

A credit transaction charges against the account's credit line.

Behavior:
- If `amount` is negative, the request is rejected.
- If `credit_used + amount > credit_limit`, the transaction is declined.
- Otherwise, `credit_used` is increased.

Possible messages:
- `Accepted.`
- `Declined - Insufficient Funds.`
- `Negative amount not allowed.`

### `deposit`

A deposit transaction adds money to the account `balance`.

Behavior:
- If `amount` is negative, the request is rejected.
- Otherwise, the amount is added to `balance`.

Possible messages:
- `Accepted.`
- `Negative amount not allowed.`

### Unsupported transaction type

If `txn_type` is not one of the supported values, the API returns:

- HTTP status: `200`
- Message: `Transaction Type: <txn_type> not supported.`

## Response Format

All responses are JSON and include:

```json
{
  "message": "..."
}
```

The HTTP header is:

```http
Content-Type: application/json
```

## Status Codes and Meanings

| HTTP Status | Meaning |
|---|---|
| `200` | Request processed. This may mean accepted, declined, or unsupported transaction type. |
| `400` | Missing or malformed request body, or missing required parameters. |
| `401` | Clearinghouse authentication failed. |
| `403` | Invalid account information or negative amount. |
| `500` | Internal server error while accessing or updating bank data. |

## Example Responses

### Accepted debit

```json
{
  "message": "Accepted."
}
```

### Declined for insufficient funds

```json
{
  "message": "Declined - Insufficient Funds."
}
```

### Unauthorized clearinghouse

```json
{
  "message": "Clearinghouse Not Authorized."
}
```

### Missing request fields

```json
{
  "message": "Missing required parameters."
}
```

### Malformed JSON body

```json
{
  "message": "Missing or malformed body."
}
```

### Invalid card info

```json
{
  "message": "Invalid account info - bad or missing cvv"
}
```

## cURL Example

```bash
curl -X POST "https://your-api-url/handleTransaction" \
  -H "Content-Type: application/json" \
  -d '{
    "cch_name": "compas_cch",
    "cch_token": "abc123token",
    "card_holder": "Jeff Compas",
    "card_num": "4111111111111111",
    "exp_date": "12/27",
    "cvv": "123",
    "card_zip": "84790",
    "txn_type": "debit",
    "merchant": "Climbing Store",
    "amount": "42.50",
    "timestamp": "2026-03-26T18:45:00Z"
  }'
```

## Notes and Implementation Details

### Transaction logging

After the transaction result is determined, the API appends these fields to the original request body before logging to the `Transaction` table:

- `statusCode`
- `message`

This means the logged transaction record contains both the incoming request fields and the final outcome.

### Amount handling

The API converts `amount` with `parseFloat(amount)`. Numeric strings such as `"42.50"` are acceptable.

### Balance formatting

For balance updates, the new balance is rounded with `toFixed(2)` before being stored.

### Important behavior note

A declined transaction for insufficient funds still returns HTTP `200`. The actual outcome must be determined from the response message, not the HTTP status code alone.

## DynamoDB Tables Used

### `CCH`
Used for clearinghouse authentication.

Expected key usage in code:
- `Name`
- `Token`

### `Account`
Used to validate card information and update balances/credit usage.

Expected fields used in code:
- `card_num`
- `card_holder`
- `exp_date`
- `cvv`
- `card_zip`
- `balance`
- `credit_limit`
- `credit_used`

### `Transaction`
Used to log transaction attempts and outcomes.

The API writes the full request body plus:
- `statusCode`
- `message`

## Error Cases to Expect

Clients integrating with this API should be prepared for these cases:

1. Missing body or malformed JSON
2. Missing required fields
3. Bad clearinghouse credentials
4. Card validation failure
5. Negative amounts
6. Insufficient balance or credit
7. Unsupported transaction type
8. Internal server errors

## Recommended Client-Side Handling

Clients should:

- Always inspect the JSON `message`
- Not assume HTTP `200` means the transaction succeeded
- Send all required fields on every request
- Use exact card-holder and billing values expected by the bank
- Treat `Accepted.` as the success indicator for approved transactions
