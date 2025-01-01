import os
import asyncio
from io import BytesIO
from typing import Dict, Optional
from dotenv import load_dotenv

from .redbridge_apis.bbae_api_new import BBAEAPI
from .base_client import BaseClient


class BbaeClient(BaseClient):
    def __init__(self):
        super().__init__(brokerage_name="BBAE")
        load_dotenv()
        username = os.getenv("BBAE_USERNAME")
        password = os.getenv("BBAE_PASSWORD")
        self.bbae = BBAEAPI(
            username, password, filename="bbae_credentials.pkl", creds_path="./creds/"
        )

    async def authenticate(self) -> bool:
        """Authenticate with the BBAE brokerage."""
        if self.bbae.cookies:
            try:
                self.accounts = await self._fetch_accounts()
                if self.accounts:
                    self.authenticated = True
                    return True
            except Exception as e:
                self.logger.warning(f"Failed to authenticate with saved cookies: {e}")

        try:
            await asyncio.to_thread(self.bbae.make_initial_request)
            use_email = "@" in self.bbae.user
            login_result = await self._login(use_email)
            if login_result:
                self.authenticated = True
                self.accounts = await self._fetch_accounts()
                return True
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
        return False

    async def _login(self, use_email: bool) -> bool:
        try:
            ticket_response = await asyncio.to_thread(
                self.bbae.generate_login_ticket_email
                if use_email
                else self.bbae.generate_login_ticket_sms
            )

            if ticket_response.get("Data") is None:
                raise Exception("Invalid response from generating login ticket")

            data = ticket_response["Data"]
            if data.get("needSmsVerifyCode", False) or data.get(
                "needCaptchaCode", False
            ):
                sms_and_captcha_response = await self._handle_captcha_and_sms(
                    data, use_email
                )
                if not sms_and_captcha_response:
                    raise Exception("Error solving SMS or Captcha")

                otp_code = input("Enter security code: ")
                if otp_code is None:
                    raise Exception("No OTP code received")

                ticket_response = await asyncio.to_thread(
                    (
                        self.bbae.generate_login_ticket_email
                        if use_email
                        else self.bbae.generate_login_ticket_sms
                    ),
                    sms_code=otp_code,
                )

                if ticket_response.get("Message") == "Incorrect verification code.":
                    raise Exception("Incorrect OTP code")

            ticket = ticket_response["Data"].get("ticket")
            if not ticket:
                raise Exception(
                    f"Login failed. No ticket generated. Response: {ticket_response}"
                )

            login_response = await asyncio.to_thread(
                self.bbae.login_with_ticket, ticket
            )
            if login_response.get("Outcome") != "Success":
                raise Exception(f"Login failed. Response: {login_response}")

            return True
        except Exception as e:
            print(f"Error in login: {e}")
            return False

    async def _handle_captcha_and_sms(self, data, use_email):
        try:
            if data.get("needCaptchaCode", False):
                sms_response = await self._solve_captcha(use_email)
                if not sms_response:
                    raise Exception("Failure solving CAPTCHA!")
            elif data.get("needSmsVerifyCode", False):
                sms_response = await self._send_sms_code(use_email)
                if not sms_response:
                    raise Exception("Unable to retrieve sms code!")
            else:
                raise Exception(
                    "Unexpected state: neither CAPTCHA nor SMS verification required"
                )
            return True
        except Exception as e:
            print(f"Error in CAPTCHA or SMS: {e}")
            return False

    async def _solve_captcha(self, use_email):
        try:
            captcha_image = await asyncio.to_thread(self.bbae.request_captcha)
            if not captcha_image:
                raise Exception("Unable to request CAPTCHA image")

            captcha_input = await self._get_captcha_input(captcha_image)
            if captcha_input is None:
                raise Exception("No CAPTCHA code found")

            sms_request_response = await asyncio.to_thread(
                (
                    self.bbae.request_email_code
                    if use_email
                    else self.bbae.request_sms_code
                ),
                captcha_input=captcha_input,
            )

            if sms_request_response.get("Message") == "Incorrect verification code.":
                raise Exception("Incorrect CAPTCHA code!")

            return sms_request_response
        except Exception as e:
            print(f"Error solving CAPTCHA code: {e}")
            return None

    def _get_captcha_input(self, captcha_image):
        file = BytesIO()
        captcha_image.save(file, format="PNG")
        file.seek(0)

        captcha_image.save("./captcha.png", format="PNG")
        captcha_input = input(
            "CAPTCHA image saved to ./captcha.png. Please open it and type in the code: "
        )
        return captcha_input

    async def _send_sms_code(self, use_email, captcha_input=None):
        sms_code_response = await asyncio.to_thread(
            self.bbae.request_email_code if use_email else self.bbae.request_sms_code,
            captcha_input=captcha_input,
        )

        if sms_code_response.get("Message") == "Incorrect verification code.":
            print("Incorrect CAPTCHA code, retrying...")
            return False
        return sms_code_response

    async def _fetch_accounts(self) -> Optional[Dict[int, str]]:
        try:
            account_info = await asyncio.to_thread(self.bbae.get_account_info)
            accounts = {}
            if account_info.get("Data") and account_info["Data"].get("accountNumber"):
                account_number = str(account_info["Data"]["accountNumber"])
                accounts[1] = account_number
                self.logger.info(
                    f"Retrieved {len(accounts)} {self.brokerage_name} accounts"
                )
                return accounts
        except Exception as e:
            print(f"Error fetching accounts: {e}")
            return None

    async def get_accounts(self) -> Optional[Dict[int, str]]:
        if not self.authenticated:
            return None
        return self.accounts

    async def get_account_balance(self, account_id: str) -> float:
        if not self.accounts:
            return None
        try:
            account_assets = await asyncio.to_thread(self.bbae.get_account_assets)
            return float(account_assets["Data"]["totalAssets"])
        except Exception as e:
            print(f"Error getting account balance: {e}")
            return None

    async def get_stock_holdings(self, account_id: str) -> Dict[str, float]:
        if not self.accounts:
            print("Please authenticate first.")
            return False
        try:
            positions = await asyncio.to_thread(self.bbae.get_account_holdings)
            stocks = {}
            if positions.get("Data"):
                for holding in positions["Data"]:
                    ticker = holding["displaySymbol"]
                    quantity = float(holding["CurrentAmount"])
                    stocks[ticker] = quantity
                return stocks
            return None
        except Exception as e:
            print(f"Error checking position: {e}")
            return None

    async def is_tradable(self, ticker: str) -> bool:
        if not self.accounts:
            return False
        quote = await self.get_stock_price(ticker)
        if quote is None:
            return False
        return True

    async def get_stock_price(self, ticker: str) -> float:
        if not self.accounts:
            return None
        try:
            response = await asyncio.to_thread(
                self.bbae.validate_buy, ticker, 1, 1, self.accounts.get(1)
            )
            if response.get("Outcome") == "STOCK":
                return None
            price = float(response["Data"]["totalWithCommission"])
            return price
        except Exception as e:
            return None

    async def _place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        if not self.accounts:
            return False
        try:
            response = await asyncio.to_thread(
                self.bbae.execute_buy, ticker, 1, account_id, False
            )
            if response.get("Outcome") != "Success":
                print(response)
                raise Exception
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False

    async def _place_sell_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        if not self.accounts:
            return False
        try:
            validation_response = await asyncio.to_thread(
                self.bbae.validate_sell,
                symbol=ticker,
                amount=1,
                account_number=account_id,
            )
            if validation_response["Outcome"] != "Success":
                raise Exception
            entrust_price = validation_response["Data"]["entrustPrice"]
            response = await asyncio.to_thread(
                self.bbae.execute_sell, ticker, 1, account_id, entrust_price, False
            )
            if response.get("Outcome") != "Success":
                print(response)
                raise Exception
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False
