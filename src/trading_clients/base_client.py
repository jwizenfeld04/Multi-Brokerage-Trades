import asyncio
import random
import logging
import pytz
from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime

import pandas_market_calendars as mcal


class BaseClient(ABC):
    def __init__(
        self,
        brokerage_name: str,
        transaction_fee: float = 0,
        delay: bool = True,
        concur_trades: int = 1,
    ):
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.authenticated = False
        self.accounts: Dict[int, str] = {}
        self.brokerage_name = brokerage_name
        self.transaction_fee = transaction_fee
        self.delay = delay
        self.concur_trades = concur_trades
        self._market_calendar = mcal.get_calendar("NYSE")

    @staticmethod
    async def is_market_open() -> bool:
        nyse = mcal.get_calendar("NYSE")
        current_time = datetime.now(pytz.timezone("US/Eastern"))
        schedule = nyse.schedule(
            start_date=current_time.date(), end_date=current_time.date()
        )

        if schedule.empty:
            return False

        market_open_time = schedule.iloc[0]["market_open"].tz_convert("US/Eastern")
        market_close_time = schedule.iloc[0]["market_close"].tz_convert("US/Eastern")

        return market_open_time <= current_time <= market_close_time

    async def check_preconditions(
        self, account_id: str, ticker: str, price: float, side: str
    ) -> bool:
        if not self.authenticated:
            self.logger.warning("Not authenticated. Cannot place orders.")
            return False

        if not await self.is_tradable(ticker):
            self.logger.warning(f"{ticker} not tradable on {self.brokerage_name}.")
            return False

        if not await self.is_market_open():
            self.logger.warning("Market is closed. Cannot place orders.")
            return False

        has_position = await self.has_position(account_id, ticker)
        if has_position is not None:
            if side == "buy" and has_position:
                self.logger.warning(
                    f"{self.brokerage_name} Account {self.get_account_number_from_id(account_id)} already has a share of {ticker}."
                )
                return False
            elif side == "sell" and not has_position:
                self.logger.warning(
                    f"{self.brokerage_name} Account {self.get_account_number_from_id(account_id)} does not have a share of {ticker}."
                )
                return False

        if side == "buy":
            account_balance = await self.get_account_balance(account_id)
            if (
                account_balance is None
                or account_balance < price + self.transaction_fee + 0.2
            ):
                self.logger.warning(
                    f"{self.brokerage_name} Account {self.get_account_number_from_id(account_id)} has insufficient funds to purchase {ticker}."
                )
                return False
        return True

    async def get_trade_delay(self) -> None:
        delay_time = random.uniform(4, 6) if self.delay else 1
        await asyncio.sleep(delay_time)

    def get_account_number_from_id(self, account_id: str) -> Optional[int]:
        return next(
            (num for num, acc_id in self.accounts.items() if acc_id == account_id), None
        )

    @abstractmethod
    async def authenticate(self) -> bool:
        """Each brokerage should implement its own authentication logic."""

    @abstractmethod
    async def get_accounts(self) -> Optional[Dict[int, str]]:
        """Retrieve all accounts associated with the brokerage."""

    @abstractmethod
    async def get_account_balance(self, account_id: str) -> Optional[float]:
        """Retrieves current balance for the account"""

    async def has_position(self, account_id: str, ticker: str) -> bool:
        holdings = await self.get_stock_holdings(account_id)
        return ticker in holdings if holdings else False

    @abstractmethod
    async def get_stock_holdings(self, account_id: str) -> Optional[Dict[str, float]]:
        """Gets current stock holdings from an account"""

    @abstractmethod
    async def is_tradable(self, ticker: str) -> bool:
        """Checks if ticker is tradable on brokerage"""

    @abstractmethod
    async def get_stock_price(self, ticker: str) -> Optional[float]:
        """Gets current stock price on brokerage"""

    @abstractmethod
    async def _place_sell_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        """Subclass-specific logic for placing a sell order."""

    @abstractmethod
    async def _place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        """Subclass-specific logic for placing a buy order."""

    async def place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        if not await self.check_preconditions(account_id, ticker, price, "buy"):
            return False

        if await self._place_buy_orders(account_id, ticker, price, order_type):
            self.logger.info(
                f"{self.brokerage_name} buy order placed for account {self.get_account_number_from_id(account_id)}: 1 {ticker} @ ${price}"
            )
            await self.get_trade_delay()
            return True
        await self.get_trade_delay()
        return False

    async def place_sell_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        if not await self.check_preconditions(account_id, ticker, price, "sell"):
            return False

        if await self._place_sell_orders(account_id, ticker, price, order_type):
            self.logger.info(
                f"{self.brokerage_name} sell order placed for account {self.get_account_number_from_id(account_id)}: 1 {ticker} @ ${price}"
            )
            await self.get_trade_delay()
            return True
        await self.get_trade_delay()
        return False
