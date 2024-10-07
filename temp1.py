"""Example file on how to use the Aidvantage scraper."""

from os import environ
from pprint import pprint
from aidvantage import Aidvantage, UserLogin


if __name__ == "__main__":
    with Aidvantage(
        UserLogin(
            username=environ["AIDVANTAGE_USER"],
            password=environ["AIDVANTAGE_PASS"],
            ssn=environ["AIDVANTAGE_SSN"],
            dob=environ["AIDVANTAGE_DOB"]
        )
    ) as av:
        loans = av.get_account_details()
        for loan_name, details in loans.items():
            pprint(av.get_transactions(loan_name))
