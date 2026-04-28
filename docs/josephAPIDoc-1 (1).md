## Document Overview:

To use the Jank Bank API to access and update our accounts remote, use the following instructions:

### URL:

Make an HTTP POST request to the following URL:

https://yt1i4wstmb.execute-api.us-west-2.amazonaws.com/default/transact

and include all of the following parameters:

### Parameters:

cch_name<br>
cch_token<br>
account_num<br>
card_num<br>
exp_date<br>
cvv<br>
amount (i.e. amount of money being transferred)<br>
type (must be either "credit", "debit", or "deposit")<br>
merchant<br>

### Authentication and Security:

A name and security token will be provided for each authorized clearinghouse; these will be submitted to the API as the parameters "cch_name" and "cch_token," respectively. No other names or tokens may be used unless they are added to our database ahead of time.

## Example:

If you were using CURL, your API request may look like this:

curl -X POST "https://yt1i4wstmb.execute-api.us-west-2.amazonaws.com/default/transact"<br>
&nbsp;&nbsp;  -H "Content-Type: application/json"<br>
&nbsp;&nbsp;  -d '{<br>
&nbsp;&nbsp;&nbsp;&nbsp;    "cch_name": "jbank",<br>
&nbsp;&nbsp;&nbsp;&nbsp;    "cch_token": "abcdefghijkABCDEFGHIJK0123456789",<br>
&nbsp;&nbsp;&nbsp;&nbsp;    "account_num": "ACCT000000",<br>
&nbsp;&nbsp;&nbsp;&nbsp;    "card_num": "4111111111110000",<br>
&nbsp;&nbsp;&nbsp;&nbsp;    "exp_date": "02/29",<br>
&nbsp;&nbsp;&nbsp;&nbsp;    "cvv": "123",<br>
&nbsp;&nbsp;&nbsp;&nbsp;    "amount": "5.23",<br>
&nbsp;&nbsp;&nbsp;&nbsp;    "type": "credit",<br>
&nbsp;&nbsp;  }'


### Response:

A JSON, which may be any of the following (accompanied by the following codes):

200 - Transaction Completed<br>
400 - Missing or malformed request body<br>
401 - Clearinghouse Authentication Failed<br>
401 - Account Authentication Failed<br>
403 - Insufficient Funds<br>
403 - Insufficient Credit<br>
