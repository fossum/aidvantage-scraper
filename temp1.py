
from os import environ
from aidvantage import Aidvantage


if __name__ == "__main__":
    av = Aidvantage(username=environ["AIDVANTAGE_USER"], password=environ["AIDVANTAGE_PASS"], ssn=environ["AIDVANTAGE_SSN"], dob=environ["AIDVANTAGE_DOB"])
    av.get_account_balances()
