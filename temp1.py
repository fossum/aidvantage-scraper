
from os import environ
from aidvantage import Aidvantage


if __name__ == "__main__":
    av = Aidvantage(
        username=environ["AIDVANTAGE_USER"],
        password=environ["AIDVANTAGE_PASS"],
        ssn=environ["AIDVANTAGE_SSN"],
        dob=environ["AIDVANTAGE_DOB"])
    loans = av.get_account_details()
    for loan_name, details in loans.items():
        av.get_transactions(loan_name)
