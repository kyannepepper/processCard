# Wild West Bank API Interface Document

## Document Overview

Welcome to Wild West Bank 🤠! We're excited to work with you. This document will help you connect with our bank so that you can submit requests of withdrawals or deposits on behalf of your customers. We are assuming that you have previously been authorized to do business with us.

## URL

https://l25ft7pzu5wpwm3xtskoiks6rm0javto.lambda-url.us-west-2.on.aws/

Request contract:

- Method: `POST`
- Header: `Content-Type: application/json`
- Field names are case-sensitive and must match exactly as documented.

## Parameters

- `cch_name`: Clearinghouse name assigned by Wild West Bank 🤠. (string, required)
- `cch_token`: Clearinghouse token assigned by Wild West Bank 🤠. (string, required)
- `account_holder_name`: Customer account holder full name (must match exactly, including spaces, for example `Pecos Bill`). (string, required)
- `account_number`: Customer account number. (string, required)
- `transaction_type`: Must be `withdrawal` or `deposit`. (string, required)
- `card_type`: Must be `credit` or `debit`. (string, required)
- `amount`: Transaction amount (for example, `150.75`). Must be numeric and greater than or equal to `0`. (string or number, required)

## Authentication and Security

Whenever you make any requests, you must include your clearinghouse name (`cch_name`) and clearinghouse token (`cch_token`) in the request body so we can authenticate the transaction.

All requests must be sent over HTTPS.

## Example

Here is an example POST using curl:

```bash
curl -X POST "https://l25ft7pzu5wpwm3xtskoiks6rm0javto.lambda-url.us-west-2.on.aws/" \
  -H "Content-Type: application/json" \
  -d '{
    "cch_name": "jeff_cch",
    "cch_token": "abcd1234",
    "account_holder_name": "Pecos Bill",
    "account_number": "1234567890",
    "transaction_type": "withdrawal",
    "card_type": "debit",
    "amount": "150.75"
  }'
```

## Response

The API will respond with a JSON structure as shown below:

```json
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json"
  },
  "body": "{\"message\":\"Deposit successful.🤠 New checking account balance: $123.45\"}"
}
```

Note: `body` is returned as a JSON string. Parse it in your client to access `message`.

The `statusCode` field contains HTTP status codes:

- `200` for OK
- `401` for Unauthorized
- `400` for Bad Request
- `500` for Server Error

The `message` field may include the following:

- Missing required fields in the request body.🤠
- Clearinghouse not authorized. Please check your credentials and try again.🤠
- Invalid request body. Please ensure all required fields are present and valid.🤠
- Amount must be a positive number.🤠
- Insufficient funds in checking account for withdrawal.🤠
- Credit limit exceeded for this withdrawal.🤠
- Withdrawal successful.🤠 New checking account balance: $$$
- Withdrawal successful.🤠 New credit card balance: $$$
- Deposit successful.🤠 New checking account balance: $$$
- Deposit successful.🤠 New credit card balance: $$$
- Invalid transaction type or card type.🤠
- An error occurred while processing the transaction.🤠
- Transaction calculated, but did not go through. Please try again.🤠

## Request Processing Order

The API processes requests in this order:

1. Parse request body.
2. Validate required fields are present.
3. Authenticate `cch_name` and `cch_token`.
4. Validate account exists and transaction inputs are valid.
5. Process transaction and update balances in the database.

## Behavior Rules

- `withdrawal + debit`: deduct from checking balance.
- `withdrawal + credit`: increase credit used.
- `deposit + debit`: add to checking balance.
- `deposit + credit`: reduce credit used.

