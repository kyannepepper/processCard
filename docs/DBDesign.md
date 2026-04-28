Data Organization:

Merchant Table – stores merchant identity and authentication info. I chose to include email and phone number just for more contact information but it can be null. I'm not sure if this is the right way to do this but I included a column for bankaccounts that will link to the merchantBankAccount table. That is if they have more than one bank account.

Partition Key – MerchantName (String)  
Sort Key – MerchantToken (String)

Other Attributes:
- ContactEmail
- Phone
- MerchantBankAccounts

Bank Table – stores bank API information. I know we will need the ApiEndpoint and the ApiKey. I feel like there will also be other steps for each bank but I'm not sure how to store that so I decided to just have an additional details to explain any thing that bank specifically needs.

Partition Key – BankName (String)

Other Attributes:
- ApiEndpoint
- ApiKey
- AdditionalDetails

MerchantBankAccount Table – stores which bank account belongs to each merchant. The Partition Key is the MerchantName which is how it matches up with the merchant in the Merchant table. I added Pin, CVV, and Expiration Date because they will need a way to check it but I'm not sure if how we will get this information and I'm also not sure if it's even supposed to be stored haha. 

Partition Key – MerchantName (String)

Other Attributes:
- BankName
- AccountNumber
- RoutingNumber
- Pin
- CVV
- ExpirationDate


Transaction Table – stores all payment attempts and results.

Partition Key – MerchantName (String)  
Sort Key – TransactionTime (String or Number)

Other Attributes:
- CardNumber
- BankName
- MerchantToken
- Amount
- Status (approved / declined)
- TransactionDate
- SystemErrors
