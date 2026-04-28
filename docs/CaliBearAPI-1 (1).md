# CaliBear Credit Union — Transaction Authorization API

**Developer:** Barrett
**Version:** 2.0
**Last Updated:** March 2026

---

## Document Overview

Welcome to the CaliBear Credit Union API. This API allows authorized clearinghouses to submit card transaction requests on behalf of merchants. You'll send us a card number and an amount, and we'll tell you whether the transaction is **APPROVED** or **DECLINED** — along with the reason if it's declined.

This API supports both **withdrawals** (money leaving an account to pay for something) and **deposits** (money going into a merchant's account as a result of a sale). It also handles both **debit** and **credit** card types.

---

## Getting Started

Before you can call the API, you need to register as an authorized clearinghouse and get your credentials.

### Step 1: Register

Go to **[www.calibear.credit](https://www.calibear.credit)** and fill out the registration form with your first name, last name, and email. You'll instantly receive:

- A **`clearinghouse_id`** (starts with `CH-`) — this goes in the request body
- An **`api_key`** (starts with `credential_token_`) — this goes in the `x-api-key` request header

**Save these immediately.** Your API key will not be shown again.

### Step 2: Send a Test Request

Use the credentials you received to send a test transaction to the API. See the [Example Requests](#example-requests) section below for copy-paste curl commands.

### Step 3: Check the Response

If everything is set up correctly, you'll get back an `APPROVED` or `DECLINED` response with details. If something's wrong, check the [Troubleshooting](#troubleshooting) section.

---

## URL

```
POST https://api.calibear.credit/transaction/
```

You must send an **HTTPS POST** request to this URL. Include your API key in the header and the transaction details as a JSON object in the body.

> **Important:** The trailing slash on the URL is required. If you get a `404`, make sure your URL ends with `/transaction/` not `/transaction`.

---

## Headers

These headers are **required** on every request:

| Header | Value | Description |
|---|---|---|
| `Content-Type` | `application/json` | Tells us you're sending JSON. |
| `x-api-key` | Your API key | Your secret credential token (starts with `credential_token_`). This authenticates your request. **This goes in the header, not the body.** |

---

## Body Parameters

Send these fields as a JSON object in the body of your POST request:

| Field | Type | Required | Description |
|---|---|---|---|
| `clearinghouse_id` | string | Yes | Your unique clearinghouse identifier (starts with `CH-`). You received this when you registered at [www.calibear.credit](https://www.calibear.credit). |
| `card_number` | string | Yes | The 16-digit card number from the customer's card. Send as a string — do not strip leading zeros. |
| `amount` | number | Yes | The dollar amount of the transaction. Must be a positive number greater than 0. Use standard decimal format (e.g., `150.75`). **Send as a number, not a string.** |
| `transaction_type` | string | Yes | Either `"withdrawal"` or `"deposit"`. A **withdrawal** takes money out of (or charges to) the account. A **deposit** adds money to the account. |
| `merchant_name` | string | Yes | The name of the merchant where the transaction is taking place (e.g., `"Walmart"`, `"Shell Gas"`). |

### Notes on Fields

- **`x-api-key` (header) + `clearinghouse_id` (body)**: Both are required on every request. If either is missing or doesn't match our records, you'll get a `401 Unauthorized`.
- **`card_number`**: Must be exactly 16 digits. This is how we look up the account. If the card number doesn't exist in our system, you'll get a `404`.
- **`amount`**: Must be a number, not a string. `42.50` is correct, `"42.50"` will be rejected. Must be greater than 0.
- **`transaction_type`**: Must be exactly `"withdrawal"` or `"deposit"` (lowercase). Anything else gets rejected.
- **`merchant_name`**: Just a string for logging purposes — we don't validate it, but it is required.

---

## Authentication and Security

Your API key goes in the **request header**, not the body. Here's how authentication works:

1. We pull the `x-api-key` from your request header and `clearinghouse_id` from the body.
2. We look up the `clearinghouse_id` in our Clearinghouses database.
3. If it doesn't exist, or the `x-api-key` doesn't match, or your account has been **Revoked** — we reject the request with a `401`.
4. If everything checks out, we proceed to process the transaction.

**Important:** Do not share your `api_key` with anyone. Do not commit it to a public GitHub repo. If you think it's been compromised, contact us to get it rotated.

---

## Transaction Processing Logic

Once authenticated, here's how we decide whether to approve or decline:

### For Withdrawals (Debit Accounts)
1. Look up the account by `card_number`
2. Check that the account status is `active` (not frozen, closed, or overdrawn)
3. Check that this transaction won't exceed the account's daily transaction limit (we sum all approved withdrawals for today + this new amount)
4. Check that the `amount` does not exceed the available balance
5. If all checks pass → **APPROVED**, and we deduct the amount from the balance

### For Withdrawals (Credit Accounts)
1. Look up the account by `card_number`
2. Check that the account status is `active`
3. Check daily transaction limit (same as above)
4. Check that the current balance + amount does not exceed the credit limit
5. If all checks pass → **APPROVED**, and we add the amount to what's owed

### For Deposits (Either Account Type)
1. Look up the account by `card_number`
2. Check that the account status is `active`
3. For debit accounts → add the amount to the available balance
4. For credit accounts → subtract the amount from what's owed (like making a payment)
5. Deposits are generally **APPROVED** as long as the account exists and is active

---

## Example Requests

### Example 1: Withdrawal (Debit Card Purchase)

A customer is buying $42.50 worth of groceries at Walmart with their debit card.

```bash
curl -X POST "https://api.calibear.credit/transaction/" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY_HERE" \
  -d '{
    "clearinghouse_id": "YOUR_CLEARINGHOUSE_ID_HERE",
    "card_number": "9594406409097439",
    "amount": 42.50,
    "transaction_type": "withdrawal",
    "merchant_name": "Walmart"
  }'
```

### Example 2: Withdrawal (Credit Card Purchase)

A customer is charging $250.00 at Best Buy on their credit card.

```bash
curl -X POST "https://api.calibear.credit/transaction/" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY_HERE" \
  -d '{
    "clearinghouse_id": "YOUR_CLEARINGHOUSE_ID_HERE",
    "card_number": "2104709521456232",
    "amount": 250.00,
    "transaction_type": "withdrawal",
    "merchant_name": "Best Buy"
  }'
```

### Example 3: Deposit (Merchant Receiving Payment)

A merchant account is receiving $150.00 from a sale.

```bash
curl -X POST "https://api.calibear.credit/transaction/" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY_HERE" \
  -d '{
    "clearinghouse_id": "YOUR_CLEARINGHOUSE_ID_HERE",
    "card_number": "9594406409097439",
    "amount": 150.00,
    "transaction_type": "deposit",
    "merchant_name": "Target"
  }'
```

> **Note:** Replace `YOUR_API_KEY_HERE` and `YOUR_CLEARINGHOUSE_ID_HERE` with the credentials you received when you registered at [www.calibear.credit](https://www.calibear.credit).

---

## Response Format

Every response comes back as JSON with this structure:

### Successful Transaction (200)

```json
{
  "message": "APPROVED",
  "transaction_id": "a3f1c2d4-5678-9abc-def0-1234567890ab",
  "card_number": "9594406409097439",
  "amount": 42.50,
  "transaction_type": "withdrawal",
  "new_balance": 48287674.50
}
```

### HTTP Status Codes

| Code | Meaning | When It Happens |
|---|---|---|
| `200` | OK — Transaction Approved | The transaction went through successfully. |
| `400` | Bad Request | Missing required fields, invalid `amount`, or unrecognized `transaction_type`. |
| `401` | Unauthorized | The `clearinghouse_id` or `x-api-key` is missing, doesn't match, or has been revoked. |
| `404` | Not Found | The `card_number` doesn't match any account in our system. |
| `403` | Forbidden — Transaction Declined | The transaction was declined for a business reason (see decline reasons below). |
| `500` | Internal Server Error | Something broke on our end. Try again or contact us. |

### Decline Reasons (403 Responses)

When a transaction is declined, the `message` field will tell you exactly why:

| Message | What It Means |
|---|---|
| `DECLINED - INSUFFICIENT_FUNDS` | Debit withdrawal amount exceeds available balance. |
| `DECLINED - CREDIT_LIMIT_EXCEEDED` | Credit withdrawal would push the balance over the credit limit. |
| `DECLINED - DAILY_LIMIT_EXCEEDED` | Today's total transactions (including this one) would exceed the daily limit. |
| `DECLINED - ACCOUNT_FROZEN` | The account is frozen and cannot process transactions. |
| `DECLINED - ACCOUNT_CLOSED` | The account has been closed. |
| `DECLINED - ACCOUNT_OVERDRAWN` | The account is in overdrawn status. |

### Example Decline Response

```json
{
  "message": "DECLINED - INSUFFICIENT_FUNDS",
  "card_number": "9594406409097439",
  "amount": 999999999.00,
  "transaction_type": "withdrawal"
}
```

### Example Unauthorized Response

```json
{
  "message": "Unauthorized - invalid api key"
}
```

### Example Bad Request Response

```json
{
  "message": "Bad Request - missing required field(s): card_number, merchant_name"
}
```

---

## Troubleshooting

| Problem | What to Check |
|---|---|
| Getting `404 Not Found` on the endpoint | Make sure your URL ends with `/transaction/` (trailing slash required). The full URL is `https://api.calibear.credit/transaction/`. |
| Getting `401 Unauthorized` | Make sure `x-api-key` is in your **header** (not the body). Make sure `clearinghouse_id` is in the **body**. Both are case-sensitive — no extra spaces. If you haven't registered yet, go to [www.calibear.credit](https://www.calibear.credit) to get your credentials. |
| Getting `400 Bad Request` | Make sure you're sending all 5 body fields. Make sure `amount` is a number (not a string like `"42.50"`). Make sure `transaction_type` is either `"withdrawal"` or `"deposit"` exactly. |
| Getting `404 Not Found` on a card | The card number doesn't exist in our system. Double-check you're using the right 16-digit number as a string. |
| Getting `403 Declined` | The transaction was rejected for a business reason. Read the `message` field — it tells you exactly why. |
| Getting `500 Internal Server Error` | Something went wrong on our side. Try the request again. If it keeps happening, let us know. |
| Request hangs or times out | Make sure you're sending a **POST** (not GET). Make sure both headers are set: `Content-Type: application/json` and `x-api-key: your-key`. |
| Body parsing error | Make sure your JSON is valid. Common mistakes: trailing commas, unquoted keys, or forgetting to stringify. |
| CORS errors in the browser | If you're calling from a frontend, our API allows cross-origin requests. Make sure you're including the right headers. |
| Don't have credentials | Go to [www.calibear.credit](https://www.calibear.credit) and register. You'll get your `clearinghouse_id` and `api_key` instantly. |

---

## Quick Reference

**Registration:** [www.calibear.credit](https://www.calibear.credit)

**Endpoint:** `POST https://api.calibear.credit/transaction/`

**Required Headers:**
```
Content-Type: application/json
x-api-key: your-credential-token-here
```

**Required Body:**
```json
{
  "clearinghouse_id": "CH-your-id-here",
  "card_number": "1234567890123456",
  "amount": 42.50,
  "transaction_type": "withdrawal",
  "merchant_name": "Store Name"
}
```

**Possible Outcomes:**
- `200` → Approved (check `new_balance` in response)
- `400` → Bad request (fix your payload)
- `401` → Auth failed (check your header `x-api-key` and body `clearinghouse_id`)
- `403` → Declined (business rule — read the `message`)
- `404` → Card not found (or wrong URL — make sure trailing slash is there)
- `500` → Server error (try again)
