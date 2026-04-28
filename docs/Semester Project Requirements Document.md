Semester Project Requirements Document

Project Title: The Ulitmate Credit Card Processor 

Developer Name: Kyanne Myler

# Business Context:

The main goal of this product is to help businesses accept credit card payments in a secure and reliable way. Many merchants want an easy way to process payments without dealing with complicated systems. This system will provide a standard way to handle payments quickly while keeping them accurate and secure.

# Problem Statement:

People need a secure and reliable way to make credit card transactions. These transactions need to reach a specific bank to process their credit card payments. Without a good system, it would be very difficult and time consuming to make credit card transactions correctly and securly.

# Scope:

## In Scope

* Accepting credit card payment requests
* Validating credit card information
* Making API call to correct bank
* Accepting transaction results from the bank
* Recording transaction details

## Out of Scope / Future Enhancements

* Fraud detection
* GUI for credit card payments
* Refunds

# Functional Requirements:

1. It will allow merchants to submit a credit card payment requests.
2. It will accept a credit card number, expiration date, CVV, and transaction amount.
3. It should verify that all required payment fields are filled out.
4. It will validate that the credit card number is in a valid format.
5. It will deny it if the credit card expiration date is expired.
6. It will return a clear message indicating whether a transaction was declined because of missing data or invalid format.
7. It will make sure that the transaction amount is greater than zero otherwise it will deny it.
8. It will make an API call to a bank with the transaction details.
9. It will accept an API call from the bank with an approval or decline response.
10. It will return a success response for approved transactions.
11. It should return an error response for declined transactions.
12. It will record transaction details for completed transactions in a database.
13. It will hash the credit card number when storing details in the database.
14. It should also record failed transaction attempts.
15. It will allow merchants to check for past payment history by querying the database.
16. It will return their query with only the data that is needed. No secure credit card information.

# Non-Functional Requirements:

1. It should have an uptime of at least 90%.
2. It should process transactions with an average response time of under 2 seconds.
3. It should be able to scale to support more or less merchants at a time.
4. It should be able to handle at least 1,000 transactions per minute.
5. It should encrypt certain data to keep it safe.
6. Sensitive information should never be displayed.
7. It should log any system errors that are on our end.
8. It should not lose transaction data if an error occurs.
9. It should return any response in a consistent and easy to read format.
10. The code should be easy to read making it easy to update if needed.
