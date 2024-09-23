
from contextlib import suppress
from decimal import Decimal
from enum import Enum
from typing import Sequence

from attrs import define, field

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver


def balance_to_float(balance: str) -> Decimal:
    return Decimal(balance.lstrip("$"))


def apr_to_float(apr: str) -> Decimal:
    return Decimal(float(apr.rstrip("%")) / 100)


@define
class LoanDetails:
    name: str# = field(alias='Loan')
    balance: Decimal# = field(alias='Current Balance', converter=balance_to_float)
    apr: Decimal# = field(alias='Interest Rate', converter=apr_to_float)
    due_date: str# = field(alias='Due Date')


class Aidvantage:

    class CurrentPage(Enum):
        HOME_PAGE = "Welcome to Aidvantage!"
        GOV_DISCLAIMER = "You are accessing a U.S. Federal Government computer system"
        ACCOUNT_SUMMARY = "asd"
        LOGIN_PAGE = "Forgot User ID Forgot Password"
        ADDITIONAL_INFO = "Please provide the information below so we can verify your account"
        LOAN_DETAILS = "All Loan Details"

    def __init__(self, username: str, password: str, ssn: str, dob: str, driver: None = None) -> None:
        self.__username = username
        self.__password = password
        self.__ssn = ssn
        self.__dob = dob
        self.home_page = "https://aidvantage.studentaid.gov"
        if driver is None:
            driver = webdriver.Chrome()
        self.driver: WebDriver = driver
        # Manual call to get things going.
        self.driver.get(self.home_page)
        self.driver.implicitly_wait(5)

    def __del__(self) -> None:
        self.driver.quit()

    def current_page(self) -> "Aidvantage.CurrentPage":
        page_text = self.driver.find_element(By.TAG_NAME, 'body').text

        for page_choice in Aidvantage.CurrentPage:
            if page_choice.value in page_text:
                return page_choice

        raise ValueError('Unknown page')

    def is_logged_in(self) -> bool:
        # Normal page without login
        with suppress(NoSuchElementException):
            if self.driver.find_element(By.LINK_TEXT, 'Log in'):
                return False

        with suppress(NoSuchElementException):
            if self.driver.find_element(By.LINK_TEXT, "Account Summary"):
                return True

        for id_string in [
            "user-id",          # On the login page.
            "account-number"    # Additional info page.
        ]:
            with suppress(NoSuchElementException):
                if self.driver.find_elements(By.ID, id_string):
                    return False
        # No rules match.
        raise ValueError("Unknown login state.")

    def _require_login(self):
        # Go to login page. Link exists on most pages.
        if (login_button := self.driver.find_element(By.LINK_TEXT, 'Log in')) is not None:
            login_button.click()
            self._do_filler_steps()

            # Fill-in user/pass.
            elem = self.driver.find_element(By.ID, 'user-id')
            elem.send_keys(self.__username)
            elem = self.driver.find_element(By.ID, 'password')
            elem.send_keys(self.__password)

            # Click login.
            elem = self.driver.find_element(By.ID, 'Submit')
            elem.click()

        if self.current_page() is Aidvantage.CurrentPage.ADDITIONAL_INFO:
            # Fill-in social-security number.
            elem = self.driver.find_element(By.ID, "lblSSN1")
            elem.send_keys(self.__ssn)
            # Fill-in date of birth.
            elem = self.driver.find_element(By.ID, 'dob1')
            elem.send_keys(self.__dob)
            # Submit
            elem = self.driver.find_element(By.ID, 'Submit')
            elem.click()

        # Must be logged in by this point.
        if not self.is_logged_in():
            raise RuntimeError

    def go_to_page(self, url: str) -> bool:
        self.driver.get(url)
        self._do_filler_steps()
        return True

    def _do_filler_steps(self) -> None:
        """If there was a filler step, do it before returning."""
        choices = {
            self.CurrentPage.GOV_DISCLAIMER: self._accept_gov_comp_access,
        }
        while (current_page := self.current_page()) in choices:
            choices[current_page]()

    def _accept_gov_comp_access(self) -> None:
        accept_button = self.driver.find_element(By.ID, "Accept")
        accept_button.click()

    def get_account_balances(self) -> Sequence[tuple[str, float]]:
        self._require_login()
        if self.current_page is not Aidvantage.CurrentPage.LOAN_DETAILS:
            elem = self.driver.find_element(By.LINK_TEXT, "Loan Details")
            elem.click()

        # Get account table.
        table = self.driver.find_element(By.ID, "tblAllLoanDetails")

        # Get table header.
        header_list = []
        header_elem = table.find_element(By.TAG_NAME, "thead").find_elements(By.TAG_NAME, "th")
        for item in header_elem:
            header_list.append(item.text)

        # Rows
        rows = table.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
        for itr, row in enumerate(rows):
            # Align headers to columns.
            data_list = [td.text for td in row.find_elements(By.TAG_NAME, 'td')]
            dict(zip(data_list, header_list))


