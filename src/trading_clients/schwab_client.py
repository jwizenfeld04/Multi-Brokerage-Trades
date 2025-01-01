import os
import json
import asyncio
from typing import Dict, Optional
from dotenv import load_dotenv

import schwabdev

from .base_client import BaseClient


class SchwabClient(BaseClient):
    def __init__(self):
        super().__init__(brokerage_name="Schwab")
        load_dotenv()
        schwab_key = os.getenv("SCHWAB_API_KEY")
        schwab_secret = os.getenv("SCHWAB_API_SECRET")
        self.schwab = schwabdev.Client(
            schwab_key, schwab_secret, tokens_file="creds/schwab_tokens.json"
        )
        self.accounts_hash = {}

    async def authenticate(self) -> bool:
        if self.schwab.access_token:
            self.authenticated = True
            await self.get_accounts()
            return True
        return False

    async def get_accounts(self) -> Optional[Dict[int, str]]:
        if not self.authenticated:
            return None

        try:
            response = await asyncio.to_thread(self.schwab.account_linked)
            content = json.loads(response.content)
            self.accounts = {
                idx: account["accountNumber"] for idx, account in enumerate(content, 1)
            }
            self.accounts_hash = {
                idx: account["hashValue"] for idx, account in enumerate(content, 1)
            }
            self.logger.info(
                f"Retrieved {len(self.accounts)} {self.brokerage_name} accounts"
            )
            return self.accounts
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            self.logger.error(f"Error parsing account details: {e}")
            return None

    async def get_account_hash(self, account_id: str) -> Optional[str]:
        if not self.accounts:
            return None
        account_idx = self.get_account_number_from_id(account_id)
        return self.accounts_hash.get(account_idx)

    async def get_account_balance(self, account_id: str) -> Optional[float]:
        account_hash = await self.get_account_hash(account_id)
        if not account_hash:
            return None

        try:
            response = await asyncio.to_thread(
                self.schwab.account_details, account_hash
            )
            content = json.loads(response.content)
            return float(content["securitiesAccount"]["currentBalances"]["cashBalance"])
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            self.logger.error(f"Error parsing account balance: {e}")
            return None

    async def get_stock_holdings(self, account_id: str) -> Dict[str, float]:
        account_hash = await self.get_account_hash(account_id)
        if not account_hash:
            return {}

        try:
            response = await asyncio.to_thread(
                self.schwab.account_details, account_hash, fields="positions"
            )
            content = json.loads(response.content)
            positions = content.get("securitiesAccount", {}).get("positions", [])
            return {
                position["instrument"]["symbol"]: float(position["longQuantity"])
                for position in positions
                if position.get("instrument", {}).get("symbol")
                and position.get("longQuantity")
            }
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            self.logger.error(
                f"Error checking positions for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {e}"
            )
            return {}

    async def is_tradable(self, ticker: str) -> bool:
        return await self.get_stock_price(ticker) is not None

    async def get_stock_price(self, ticker: str) -> Optional[float]:
        try:
            response = await asyncio.to_thread(self.schwab.quote, ticker)
            if response.status_code == 404:
                return None
            content = json.loads(response.content)
            return float(content[ticker.upper()]["quote"]["lastPrice"])
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Error getting price for ticker {ticker}: {e}")
            return None

    async def _place_order(
        self,
        account_id: str,
        ticker: str,
        side: str,
        price: float,
        order_type: str = "market",
    ) -> bool:
        account_hash = await self.get_account_hash(account_id)
        if not account_hash:
            return False

        try:
            order = self._get_order(side, ticker)
            response = await asyncio.to_thread(
                self.schwab.order_place, account_hash, order
            )
            if response.status_code != 201:
                raise Exception(response.content)
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place {side} order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False

    async def _place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        return await self._place_order(account_id, ticker, "BUY", price, order_type)

    async def _place_sell_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        return await self._place_order(account_id, ticker, "SELL", price, order_type)

    def _get_order(self, side: str, ticker: str):
        return {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": side.upper(),
                    "quantity": 1,
                    "instrument": {"symbol": ticker.upper(), "assetType": "EQUITY"},
                }
            ],
        }
