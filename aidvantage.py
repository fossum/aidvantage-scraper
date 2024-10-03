"""Aidvantage scraper.

This module provides a class for scraping data from the Aidvantage website.
It uses Selenium to interact with the website and Pandas to store the data.

Usage:
    av = Aidvantage(username, password, ssn, dob)
    loans = av.get_account_details()
    transactions = av.get_transactions(loans[list(loans.keys())[0]].name)
    print(transactions)

Requirements:
    - selenium
    - pandas
    - requests
    - attrs
    - chromedriver (installed and in your PATH)

Example:
    from aidvantage import Aidvantage
    from os import environ

    av = Aidvantage(
        username=environ["AIDVANTAGE_USER"],
        password=environ["AIDVANTAGE_PASS"],
        ssn=environ["AIDVANTAGE_SSN"],
        dob=environ["AIDVANTAGE_DOB"]
    )
    loans = av.get_account_details()
    transactions = av.get_transactions(loans[list(loans.keys())[0]].name)
    print(transactions)
"""

from contextlib import suppress
from decimal import Decimal
from enum import Enum

from attrs import define, field

from pandas import DataFrame

import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions


def balance_to_float(balance: str) -> Decimal:
    """Converts the Aidvantage balance to a decimal."""
    return Decimal(balance.lstrip("$").replace(',', ''))


def apr_to_float(apr: str) -> Decimal:
    """Converts the Aidvantage interest rate to a decimal."""
    return Decimal(float(apr.rstrip("%")) / 100)


@define
class LoanDetails:
    """Data class representing a loan's detail summary."""
    name: str = field(alias='Loan')
    balance: Decimal = field(alias="CurrentBalance", converter=balance_to_float)
    apr: Decimal = field(alias='InterestRate', converter=apr_to_float)
    due_date: str = field(alias='DueDate')


@define
class PageDetail:
    """Data class representing a page within the website."""
    matching_text: str
    link_text: str | None


@define
class UserLogin:
    """Data class representing a user's login."""
    username: str
    password: str
    ssn: str
    dob: str


class Aidvantage:
    """Web scraper for the Aidvantage website."""

    class CurrentPage(Enum):
        """Various pages within the website."""
        HOME_PAGE = PageDetail("Welcome to Aidvantage!", "")
        GOV_DISCLAIMER = PageDetail(
            "You are accessing a U.S. Federal Government computer system", None)
        LOGIN_PAGE = PageDetail("Forgot User ID Forgot Password", "Log in")
        ADDITIONAL_INFO = PageDetail(
            "Please provide the information below so we can verify your account", None)
        ACCOUNT_SUMMARY = PageDetail(
            (
                "This is an attempt to collect a debt and any information obtained will "
                "be used for that purpose"
            ),
            "Account Summary")
        ACCOUNT_HISTORY = PageDetail(
            (
                "The information contained on this page is current as of the day "
                "the information is requested"
            ),
            "Account History"
        )
        LOAN_DETAILS = PageDetail("All Loan Details", "Loan Details")
        UNKNOWN = PageDetail("Not a known page type.", None)
        EXPIRED = PageDetail("Your session has expired.", None)

        @staticmethod
        def get_current_page(driver: WebDriver) -> "Aidvantage.CurrentPage":
            """Gets the current page from the driver."""
            page_text = driver.find_element(By.TAG_NAME, 'body').text

            for page_choice in Aidvantage.CurrentPage:
                assert isinstance(page_choice.value, PageDetail)
                if page_choice.value.matching_text in page_text:
                    return page_choice

            return Aidvantage.CurrentPage.UNKNOWN

        @staticmethod
        def go_to_page(driver: WebDriver, page: "Aidvantage.CurrentPage") -> None:
            """Navigates to the specified page."""
            if Aidvantage.CurrentPage.get_current_page(driver) == page:
                return
            if page.value.link_text is None:
                raise ValueError(f"{page} has no link text.")
            driver.find_element(By.PARTIAL_LINK_TEXT, page.value.link_text).click()

    def __init__(
        self, login: UserLogin, driver: WebDriver | None = None
    ) -> None:
        self.__username: str = login.username
        self.__password: str = login.password
        self.__ssn: str = login.ssn
        self.__dob: str = login.dob
        self.home_page = "https://aidvantage.studentaid.gov"
        if driver is None:
            driver = webdriver.Chrome()
        self.driver: WebDriver = driver
        # Manual call to get things going.
        self.driver.get(self.home_page)
        self.driver.implicitly_wait(5)

    def __del__(self) -> None:
        """Cleans up the driver."""
        self.driver.quit()

    def go_to_page(self, page: "Aidvantage.CurrentPage") -> None:
        """Navigates to the specified page."""
        Aidvantage.CurrentPage.go_to_page(self.driver, page)
        self._do_filler_steps()

    def get_account_balances(self) -> dict[str, Decimal]:
        """Gets the account balances for all loans."""
        loans = self.get_account_details()
        return {name: loan.balance for name, loan in loans.items()}

    def get_transactions(self, loan: str) -> DataFrame:
        """Gets the transaction history for a given loan.

        Args:
            loan (str): The name of the loan to get transactions for.

        Returns:
            DataFrame: A DataFrame containing the transaction history.
        """
        wait = WebDriverWait(self.driver, 10)  # Wait up to 10 seconds

        # Get to the right page.
        if (
            Aidvantage.CurrentPage.get_current_page(self.driver)
            is not Aidvantage.CurrentPage.ACCOUNT_HISTORY
        ):
            self._require_login()
            self.go_to_page(Aidvantage.CurrentPage.ACCOUNT_SUMMARY)

            # Find recent payments section, then account history.
            elem = self.driver.find_element(By.ID, "divRecentPayments")
            elem.find_element(By.PARTIAL_LINK_TEXT, "Account History").click()

        # Display history by Loan.
        for elem_id, visible_text in [
            ("SelctedHistType", "By Loan"),
            ("ddl_Loan", loan),
            ("SelectedDateRange", "Life of Loan"),
        ]:
            elem = self.driver.find_element(By.ID, elem_id)
            wait.until(expected_conditions.visibility_of_element_located((By.ID, elem_id)))
            Select(elem).select_by_visible_text(visible_text)

        # Parse unpaid principle column from table.
        return self._get_table_from_page("tblByLoans")

    def get_account_details(self) -> dict[str, LoanDetails]:
        """Get the loan details of every loan."""
        self._require_login()
        if (
            Aidvantage.CurrentPage.get_current_page(self.driver)
            is not Aidvantage.CurrentPage.LOAN_DETAILS
        ):
            elem = self.driver.find_element(By.LINK_TEXT, "Loan Details")
            elem.click()

        # Get account table.
        table = self.driver.find_element(By.ID, "tblAllLoanDetails")

        # Get table header.
        header_list = []
        header_elem = table.find_element(By.TAG_NAME, "thead").find_elements(By.TAG_NAME, "th")
        for item in header_elem:
            header_list.append(item.text.replace(' ', ''))

        # Rows
        loans = {}
        rows = table.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
        for row in rows:
            # Align headers to columns.
            data_list = [td.text for td in row.find_elements(By.TAG_NAME, 'td')]
            data_dict = dict(zip(header_list, data_list))
            loans[data_dict['Loan']] = LoanDetails(**data_dict)

        return loans

    def _is_logged_in(self) -> bool:
        """Checks if the user is logged in."""
        current_page = Aidvantage.CurrentPage.get_current_page(self.driver)
        if current_page in [
            Aidvantage.CurrentPage.EXPIRED,
            Aidvantage.CurrentPage.LOGIN_PAGE,
            Aidvantage.CurrentPage.HOME_PAGE,
        ]:
            return False

        if current_page in [
            Aidvantage.CurrentPage.ACCOUNT_HISTORY,
            Aidvantage.CurrentPage.ACCOUNT_SUMMARY,
            Aidvantage.CurrentPage.ADDITIONAL_INFO,
            Aidvantage.CurrentPage.LOAN_DETAILS,
        ]:
            return True

        if current_page in [
            Aidvantage.CurrentPage.GOV_DISCLAIMER,
            Aidvantage.CurrentPage.ADDITIONAL_INFO,
        ]:
            self._do_filler_steps()
            return True

        # Normal page without login
        with suppress(NoSuchElementException):
            if self.driver.find_element(By.LINK_TEXT, 'Log in'):
                return False

        # Login expired.

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
        if self._is_logged_in():
            return

        # Go to login page. Link exists on most pages.
        self.go_to_page(Aidvantage.CurrentPage.LOGIN_PAGE)

        # Fill-in user/pass.
        elem = self.driver.find_element(By.ID, 'user-id')
        elem.send_keys(self.__username)
        elem = self.driver.find_element(By.ID, 'password')
        elem.send_keys(self.__password)

        # Click login.
        elem = self.driver.find_element(By.ID, 'Submit')
        elem.click()

        if (
            Aidvantage.CurrentPage.get_current_page(self.driver)
            is Aidvantage.CurrentPage.ADDITIONAL_INFO
        ):
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
        if not self._is_logged_in():
            raise RuntimeError

    def _do_filler_steps(self) -> None:
        """If there was a filler step, do it before returning."""
        choices = {
            self.CurrentPage.GOV_DISCLAIMER: self._accept_gov_comp_access,
        }
        while (current_page := Aidvantage.CurrentPage.get_current_page(self.driver)) in choices:
            choices[current_page]()

    def _accept_gov_comp_access(self) -> None:
        accept_button = self.driver.find_element(By.ID, "Accept")
        accept_button.click()

    def _get_table_from_page(self, table_id: str) -> DataFrame:
        # Get table.
        table = self.driver.find_element(By.ID, table_id)

        # Get table header.
        header_list = []
        header_elem = table.find_element(By.TAG_NAME, "thead").find_elements(By.TAG_NAME, "th")
        for item in header_elem:
            header_list.append(item.text.replace(' ', ''))

        # Rows
        data: dict[str, list] = {header: [] for header in header_list}
        rows = table.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
        for row in rows:
            # Align headers to columns.
            data_list = [td.text for td in row.find_elements(By.TAG_NAME, 'td')]
            # Align rows to data.
            while len(data_list) > len(header_list):
                if data_list[0] == '':
                    data_list.pop(0)
                elif data_list[-1] == '':
                    data_list.pop(-1)
                else:
                    raise ValueError("Columns do not match rows.")
            if data_list == ['']:
                continue
            if len(data_list) != len(header_list):
                assert False
            data_dict = dict(zip(header_list, data_list))
            for key, value in data_dict.items():
                data[key].append(value)

        return DataFrame(data)

    @staticmethod
    def _download_as_text(url: str) -> str:
        response = requests.get(url, timeout=20)
        response.raise_for_status()  # Check for download errors

        # Process the content in memory
        return response.text
