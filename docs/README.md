# ProcessCard

AWS Lambda payment processing service that integrates with multiple bank APIs.

## Project Structure

```
ProcessCard/
├── src/
│   ├── __init__.py           # Package initialization
│   ├── lambda_handler.py     # Main Lambda entry point
│   └── bank_payloads/       # Bank-specific payload builders
│       ├── __init__.py
│       ├── jeffs_bank.py
│       ├── corbin_bank.py
│       ├── calibear.py
│       ├── jank_bank.py
│       ├── tophers_bank.py
│       └── wild_west_bank.py
├── tests/                    # Test files
├── docs/                     # API documentation
├── data/                     # Data files (CSV, etc.)
├── README.md                 # This file
└── requirements.txt          # Python dependencies
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

The main Lambda handler is in `src/lambda_handler.py`:

```python
from src.lambda_handler import lambda_handler

def handler(event, context):
    return lambda_handler(event, context)
```

## Supported Banks

- **Jeffs Bank** - Standard card transactions
- **Corbin Bank** - Account-based transactions
- **CaliBear** - Credit union transactions
- **Jank Bank** - Alternative bank API
- **Tophers Bank** - Custom bank integration
- **Wild West Bank** - Lambda URL-based API

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `us-west-2` | AWS region |
| `MERCHANT_TABLE` | `Merchant` | DynamoDB table for merchants |
| `TRANSACTION_TABLE` | `Transaction` | DynamoDB table for transactions |
| `CORBIN_USERNAME` | - | Corbin Bank username |
| `CORBIN_PASSWORD` | - | Corbin Bank password |
| `CALIBEAR_CLEARINGHOUSE_ID` | `klein_k_cch` | CaliBear clearinghouse ID |

## Request Format

```json
{
  "merchant_name": "merchant_name",
  "merchant_token": "merchant_token",
  "bank": "Jeffs Bank",
  "card_num": "4111111111111111",
  "exp_date": "12/25",
  "cvv": "123",
  "card_zip": "12345",
  "card_type": "debit",
  "amount": "100.00",
  "card_holder_name": "John Doe"
}
```

## Response Format

```json
{
  "statusCode": 200,
  "body": "{\"message\": \"Approved.\"}"
}
```

## Development

The original monolithic `processCard.py` is preserved at the root for reference but is no longer used. The new modular structure is in `src/`.