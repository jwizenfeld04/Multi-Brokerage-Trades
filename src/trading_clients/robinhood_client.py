import os
import asyncio
import pyotp
import traceback
from typing import Dict, Optional
from dotenv import load_dotenv

import robin_stocks.robinhood as rh

from .base_client import BaseClient


class RobinhoodClient(BaseClient):
    def __init__(self):
        super().__init__("Robinhood")
        load_dotenv()
        self.username = os.getenv("ROBINHOOD_USERNAME")
        self.password = os.getenv("ROBINHOOD_PASSWORD")
        self.mfa_secret = os.getenv("ROBINHOOD_TOTP", "NA")
        self.pickle_name = "robinhood_session"

    async def authenticate(self) -> bool:
        try:
            mfa_code = pyotp.TOTP(self.mfa_secret).now()

            login_response = await asyncio.to_thread(
                rh.login,
                username=self.username,
                password=self.password,
                expiresIn=86400 * 30,
                store_session=True,
                mfa_code=mfa_code,
                pickle_name=self.pickle_name,
            )

            if "access_token" in login_response:
                self.authenticated = True
                await self.get_accounts()
                return True
            elif "challenge" in login_response:
                challenge_id = login_response["challenge"]["id"]
                sms_code = await asyncio.to_thread(
                    input, "Enter Robinhood code for validation: "
                )
                challenge_response = await self._respond_to_challenge(
                    challenge_id, sms_code
                )
                if "access_token" in challenge_response:
                    self.logger.info("Challenge passed. Login successful.")
                    self.authenticated = True
                    await self.get_accounts()
                    return True
            self.logger.error(
                f"Login failed: {login_response.get('detail', 'Unknown error')}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Error during Robinhood authentication: {e}")
            traceback.print_exc()
            return False

    async def _respond_to_challenge(self, challenge_id: str, sms_code: str) -> dict:
        try:
            return await asyncio.to_thread(
                rh.authentication.respond_to_challenge, challenge_id, sms_code
            )
        except Exception as e:
            self.logger.error(f"Error responding to challenge: {e}")
            traceback.print_exc()
            return {}

    async def get_accounts(self) -> Optional[Dict[int, str]]:
        try:
            all_accounts = rh.account.load_account_profile(dataType="results")
            self.accounts = {
                idx + 1: account.get("account_number", "Unknown")
                for idx, account in enumerate(all_accounts)
            }
            self.logger.info(
                f"Retrieved {len(self.accounts)} {self.brokerage_name} accounts"
            )
            return self.accounts
        except Exception as e:
            self.logger.error(f"Error fetching accounts: {e}")
            traceback.print_exc()
            return None

    async def get_account_balance(self, account_id: str) -> float:
        try:
            profile = rh.profiles.load_account_profile(account_id)
            return float(profile["cash"])
        except Exception as e:
            self.logger.error(f"Error fetching account balance: {e}")
            traceback.print_exc()
            return 0.0

    async def get_stock_holdings(self, account_id: str) -> Dict[str, float]:
        try:
            positions = rh.account.get_open_stock_positions(account_id)
            stocks = {}
            for position in positions:
                ticker = position["symbol"]
                quantity = float(position["quantity"])
                stocks[ticker] = quantity
            return stocks if stocks else None
        except Exception as e:
            self.logger.error(
                f"Error checking positions for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {e}"
            )
            return None

    async def is_tradable(self, ticker: str) -> bool:
        try:
            instrument = rh.stocks.get_instruments_by_symbols(ticker)[0]
            return instrument["tradeable"]
        except Exception as e:
            self.logger.error(f"Error checking if {ticker} is tradable: {e}")
            return False

    async def get_stock_price(self, ticker: str) -> float:
        try:
            price = rh.stocks.get_latest_price(ticker)[0]
            return float(price)
        except Exception as e:
            self.logger.error(f"Error fetching stock price for {ticker}: {e}")
            return 0.0

    async def _place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        try:
            order = rh.orders.order_buy_limit(ticker, 1, price + 0.01, account_id)
            if "id" not in order:
                print(order)
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
        try:
            order = rh.orders.order_sell_market(ticker, 1, account_id)
            if "id" not in order:
                print(order)
                raise Exception
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False
