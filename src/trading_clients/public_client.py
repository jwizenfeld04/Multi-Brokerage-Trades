import os
import asyncio
from dotenv import load_dotenv
from typing import Dict, Optional

from public_invest_api import Public

from .base_client import BaseClient


class PublicClient(BaseClient):
    def __init__(self):
        super().__init__(brokerage_name="Public")
        load_dotenv()
        self.public = Public(path="creds")
        self.email = os.getenv("PUBLIC_EMAIL")
        self.password = os.getenv("PUBLIC_PASSWORD")

    async def authenticate(self) -> bool:
        """Log in to Public API using the provided email and password."""
        try:
            # Run blocking code in a separate thread to avoid blocking the event loop
            await asyncio.to_thread(
                self.public.login,
                username=self.email,
                password=self.password,
                wait_for_2fa=True,
            )
            self.authenticated = True
            await self.get_accounts()
            return True
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            return False

    async def get_accounts(self) -> Optional[Dict[int, str]]:
        """Retrieve all available account IDs from Public API."""
        try:
            # Run blocking code in a separate thread
            account_number = await asyncio.to_thread(self.public.get_account_number)
            accounts = {1: account_number}
            self.logger.info(
                f"Retrieved {len(accounts)} {self.brokerage_name} accounts"
            )
            self.accounts = accounts
            return self.accounts
        except Exception as e:
            self.logger.error(f"Failed to get accounts: {str(e)}")
            raise

    async def get_account_balance(self, account_id: str) -> float:
        """Checks balance for Public account ID"""
        try:
            balance = await asyncio.to_thread(self.public.get_account_cash)
            return float(balance)
        except Exception as e:
            self.logger.error(
                f"Failed to check balance for account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return None

    async def get_stock_holdings(self, account_id: str) -> Dict[str, float]:
        """Gets current positions in the account asynchronously."""
        try:
            positions = await asyncio.to_thread(self.public.get_positions)
            stocks = {}
            for position in positions:
                ticker = position["instrument"]["symbol"].upper()
                quantity = float(position["quantity"])
                stocks[ticker] = quantity
            return stocks if stocks else None
        except Exception as e:
            self.logger.error(
                f"Error checking positions for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {e}"
            )
            return None

    async def is_tradable(self, ticker: str) -> bool:
        """Checks whether the ticker can be traded on Public"""
        return await asyncio.to_thread(self.public.get_symbol_price, ticker) is not None

    async def get_stock_price(self, ticker: str) -> float:
        price = await asyncio.to_thread(self.public.get_symbol_price, ticker)
        if price:
            return float(price)
        return None

    async def _place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        """Places a buy order for Public account ID"""
        try:
            response = await asyncio.to_thread(
                self.public.place_order,
                symbol=ticker,
                quantity=1,
                side="BUY",
                order_type=order_type.upper(),
                time_in_force="DAY",
                limit_price=price if order_type.upper() == "LIMIT" else None,
                is_dry_run=False,
            )
            if not response["success"]:
                raise Exception(f"Order failed: {response}")
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False

    async def _place_sell_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        """Places a sell order for Public account ID"""
        try:
            response = await asyncio.to_thread(
                self.public.place_order,
                symbol=ticker,
                quantity=1,
                side="SELL",
                order_type=order_type.upper(),
                time_in_force="DAY",
                limit_price=price if order_type.upper() == "LIMIT" else None,
                is_dry_run=False,
            )
            if not response["success"]:
                raise Exception(f"Order failed: {response}")
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False
