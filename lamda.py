import json
import boto3

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))

        merchant_name = body.get("merchant_name", "").strip()
        merchant_token = body.get("merchant_token", "").strip()

        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        table = dynamodb.Table("Merchant")  # <-- FIXED

        if authMerchant(table, merchant_name, merchant_token):
            return format_response(200, f"Merchant: {merchant_name} authenticated successfully.")

        return format_response(401, f"Unauthorized: Invalid merchant credentials. Merchant: {merchant_name}")

    except Exception as e:
        print("ERROR:", str(e))
        return format_response(500, str(e))


def authMerchant(table, name, token):
    if not name or not token:
        return False

    try:
        result = table.get_item(
            Key={
                "Name": name,
                "Token": token
            }
        )
        print("RESULT:", result)
        return "Item" in result

    except Exception as e:
        print("DynamoDB get_item error:", repr(e))
        return False


def format_response(status_code, message):
    return {
        "statusCode": status_code,
        "body": json.dumps({
            "message": message
        })
    }