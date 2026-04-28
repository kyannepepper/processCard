# Clearinghouse Transaction API

**Base URL**

```
https://xbu6ixwga4.execute-api.us-west-2.amazonaws.com/default
```

## POST `/handleTransaction`

Submit a transaction for processing. Requires Clearinghouse credentials.

Each accountholder has **two accounts** — one debit and one credit — each with a unique account number, CVV, expiration date, and independent balance. The `card_type` in the request body must match the account's card type.

---

### Authentication

Credentials are passed as **HTTP headers**:

| Header     | Type   | Required | Description                    |
|------------|--------|----------|--------------------------------|
| `username` | String | Yes      | Your Clearinghouse username    |
| `password` | String | Yes      | Your Clearinghouse password    |

Invalid or missing credentials will return `401 Unauthorized`.

---

### Request Body

Send a JSON object with **exactly** these fields — no more, no fewer:

| Field              | Type   | Required | Description                                          |
|--------------------|--------|----------|------------------------------------------------------|
| `account_num`      | String | Yes      | 16-digit bank account/card number                    |
| `cvv`              | String | Yes      | 3-digit card verification value                      |
| `exp_date`         | String | Yes      | Card expiration date (e.g. `"12/28"`)                |
| `amount`           | String | Yes      | Transaction amount (e.g. `"150.75"`)                 |
| `transaction_type` | String | Yes      | `"withdrawal"` to deduct, any other value to deposit |
| `card_type`        | String | Yes      | `"debit"` or `"credit"` — must match the account     |

---

### Processing Logic

1. **Authenticate** — Validate `username`/`password` headers against the Clearinghouse table
2. **Validate body** — Ensure all required fields are present with no extras
3. **Check card info** — Look up account by `account_num`, verify `AccountStatus` is Active, and confirm `cvv`, `exp_date`, and `card_type` all match
4. **Check balance** — For withdrawals, verify the account has sufficient funds
5. **Process** — Update the account balance, write a Transaction record, and log to SystemLog

---

### Example Requests

**Debit withdrawal:**

```bash
curl -X POST "https://xbu6ixwga4.execute-api.us-west-2.amazonaws.com/default/handleTransaction" \
  -H "Content-Type: application/json" \
  -H "username: your_username" \
  -H "password: your_password" \
  -d '{
    "account_num": "4539370182645290",
    "cvv": "673",
    "exp_date": "05/28",
    "amount": "75.00",
    "transaction_type": "withdrawal",
    "card_type": "debit"
  }'
```

**Credit withdrawal:**

```bash
curl -X POST "https://xbu6ixwga4.execute-api.us-west-2.amazonaws.com/default/handleTransaction" \
  -H "Content-Type: application/json" \
  -H "username: your_username" \
  -H "password: your_password" \
  -d '{
    "account_num": "4758532903584622",
    "cvv": "230",
    "exp_date": "01/28",
    "amount": "75.00",
    "transaction_type": "withdrawal",
    "card_type": "credit"
  }'
```

---

### Responses

#### `202 Accepted` — Transaction processed

```json
{
  "message": "Transaction accepted",
  "transaction": {
    "TransactionID": "17a77b31-7214-4619-90d8-2802b2b50f5a",
    "account_num": "4539370182645290",
    "amount": "75.00",
    "transaction_type": "withdrawal",
    "card_type": "debit",
    "new_balance": "7335.83"
  }
}
```

#### `400 Bad Request` — Missing or extra fields

```json
{ "message": "missing fields: cvv,exp_date" }
```

```json
{ "message": "extra fields: routing_num" }
```

#### `401 Unauthorized` — Missing or invalid credentials

```json
{ "message": "Check Header Credentials" }
```

```json
{ "message": "Authorization Failed" }
```

#### `402 Payment Required` — Insufficient funds

```json
{ "message": "Insufficient funds" }
```

#### `404 Not Found` — Account not found or card info mismatch

```json
{ "message": "Account not found" }
```

```json
{ "message": "Account is not active" }
```

```json
{ "message": "Card information does not match" }
```

#### `502 Bad Gateway` — Malformed or missing request body

```json
{ "message": "there was a problem with your request - missing or malformed body." }
```
