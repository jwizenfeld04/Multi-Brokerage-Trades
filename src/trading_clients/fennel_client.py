import os
import asyncio
from typing import Dict, Optional
from dotenv import load_dotenv

from fennel_invest_api import Fennel

from .base_client import BaseClient


class FennelClient(BaseClient):
    def __init__(self):
        super().__init__(brokerage_name="Fennel", delay=False, concur_trades=2)
        load_dotenv()
        self.fennel = Fennel(path="creds")
        self.email = os.getenv("FENNEL_EMAIL")

    async def authenticate(self) -> bool:
        try:
            await asyncio.to_thread(
                self.fennel.login, email=self.email, wait_for_code=True
            )
            self.authenticated = True
            await self.get_accounts()
            return True
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            return False

    async def get_accounts(self) -> Optional[Dict[int, str]]:
        try:
            account_ids = await asyncio.to_thread(self.fennel.get_account_ids)
            self.accounts = {
                idx + 1: account_id for idx, account_id in enumerate(account_ids)
            }
            self.logger.info(
                f"Retrieved {len(self.accounts)} {self.brokerage_name} accounts"
            )
            return self.accounts
        except Exception as e:
            self.logger.error(f"Failed to get accounts: {str(e)}")
            raise

    async def get_account_balance(self, account_id: str) -> float:
        try:
            portfolio_summary = await asyncio.to_thread(
                self.fennel.get_portfolio_summary, account_id
            )
            return float(portfolio_summary["cash"]["balance"]["canTrade"])
        except Exception as e:
            self.logger.error(
                f"Failed to check balance for account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return None

    async def get_stock_holdings(self, account_id: str) -> Dict[str, float]:
        try:
            holdings = await asyncio.to_thread(
                self.fennel.get_stock_holdings, account_id
            )
            return {
                holding["security"]["ticker"]: float(
                    holding["investment"]["ownedShares"]
                )
                for holding in holdings
            }
        except Exception as e:
            self.logger.error(
                f"Error checking positions for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {e}"
            )
            return None

    async def is_tradable(self, ticker: str) -> bool:
        quote = await asyncio.to_thread(self.fennel.get_stock_quote, ticker)
        return quote is not None

    async def get_stock_price(self, ticker: str) -> float:
        price = await asyncio.to_thread(self.fennel.get_stock_price, ticker)
        return float(price) if price else None

    async def _place_order(
        self,
        account_id: str,
        ticker: str,
        side: str,
        price: float,
        order_type: str = "market",
    ) -> bool:
        try:
            response = await asyncio.to_thread(
                self.fennel.place_order,
                account_id=account_id,
                ticker=ticker,
                quantity=1,
                side=side,
                price=order_type,
                dry_run=False,
            )
            if "errors" in response:
                raise Exception(str(response["errors"]))
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place {side} order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False

    async def _place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        return await self._place_order(account_id, ticker, "buy", price, order_type)

    async def _place_sell_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        return await self._place_order(account_id, ticker, "sell", price, order_type)
