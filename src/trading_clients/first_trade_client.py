import os
import dotenv
import asyncio
from typing import Dict, Optional

from firstrade import account, order, symbols

from .base_client import BaseClient


class FirstTradeClient(BaseClient):
    def __init__(self):
        super().__init__(brokerage_name="FirstTrade")
        dotenv.load_dotenv()
        username = os.getenv("FIRST_TRADE_USERNAME")
        password = os.getenv("FIRST_TRADE_PASSWORD")
        email = os.getenv("FIRST_TRADE_EMAIL")
        self.first_trade = account.FTSession(
            username=username,
            password=password,
            email=email,
            profile_path="creds",
        )
        self.authenticated = False
        self.account_data = None
        self.accounts = {}

    async def authenticate(self) -> bool:
        """Authenticate asynchronously."""
        try:
            # Run the blocking login operation in a separate thread
            need_code = await asyncio.to_thread(self.first_trade.login)
            if need_code:
                code = input("Please enter the pin sent to your email/phone: ")
                await asyncio.to_thread(self.first_trade.login_two, code)
                self.authenticated = True
                await self.get_accounts()
                return True
            self.authenticated = True
            await self.get_accounts()
            return True
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            return False

    async def get_accounts(self) -> Optional[Dict[int, str]]:
        """Retrieve accounts asynchronously after ensuring authentication."""
        if not self.authenticated:
            self.logger.error("Failed to authenticate. Cannot retrieve accounts.")
            return None

        # Now that we are authenticated, retrieve the accounts
        try:
            self.account_data = account.FTAccountData(self.first_trade)
            account_ids = await asyncio.to_thread(
                lambda: self.account_data.account_numbers
            )
            for idx, account_id in enumerate(account_ids):
                self.accounts[idx + 1] = account_id
            self.logger.info(
                f"Retrieved {len(self.accounts)} {self.brokerage_name} accounts"
            )
            return self.accounts
        except Exception as e:
            self.logger.error(f"Failed to get accounts: {str(e)}")
            return None

    async def get_account_balance(self, account_id: str) -> Optional[float]:
        """Check account balance asynchronously."""
        try:
            balance = await asyncio.to_thread(
                self.account_data.get_account_balances, account_id
            )
            return float(balance["result"]["total_account_value"])
        except Exception as e:
            self.logger.error(
                f"Failed to get account balance for account {account_id}: {str(e)}"
            )
            return None

    async def get_stock_holdings(self, account_id: str) -> Dict[str, float]:
        """Gets current positions in the account asynchronously."""
        try:
            positions_data = await asyncio.to_thread(
                self.account_data.get_positions, account_id
            )
            if positions_data["statusCode"] == 200 and "items" in positions_data:
                stocks = {}
                for position in positions_data["items"]:
                    ticker = position["symbol"]
                    quantity = float(position["quantity"])
                    stocks[ticker] = quantity
                return stocks
            return None
        except Exception as e:
            self.logger.error(
                f"Error checking positions for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {e}"
            )
            return None

    async def is_tradable(self, ticker: str) -> bool:
        """Check if the ticker is tradable asynchronously."""
        price = await self.get_stock_price(ticker)
        return price is not None

    async def get_stock_price(self, ticker: str) -> Optional[float]:
        """Retrieve the stock price asynchronously."""
        try:
            # Run the blocking quote retrieval operation in a separate thread
            quote = await asyncio.to_thread(
                symbols.SymbolQuote, self.first_trade, self.accounts.get(1), ticker
            )
            if hasattr(quote, "last") and quote.last is not None:
                return float(quote.last)
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error retrieving stock price for {ticker}: {str(e)}")
            return None

    async def _place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        """Place buy orders asynchronously."""
        ft_order = order.Order(self.first_trade)
        try:
            # Run the blocking order placement operation in a separate thread
            response = await asyncio.to_thread(
                ft_order.place_order,
                account_id,
                symbol=ticker,
                price_type=order.PriceType.LIMIT,
                price=price + 0.01,
                order_type=order.OrderType.BUY,
                duration=order.Duration.DAY,
                quantity=1,
                dry_run=False,
            )
            if "order_id" not in response["result"]:
                self.logger.error(
                    f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {response}"
                )
                return False
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False

    async def _place_sell_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        """Place sell orders asynchronously."""
        ft_order = order.Order(self.first_trade)
        try:
            # Run the blocking order placement operation in a separate thread
            response = await asyncio.to_thread(
                ft_order.place_order,
                account_id,
                symbol=ticker,
                price_type=order.PriceType.MARKET,
                order_type=order.OrderType.SELL,
                duration=order.Duration.DAY,
                quantity=1,
                dry_run=False,
            )
            if "order_id" not in response["result"]:
                self.logger.error(
                    f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {response}"
                )
                return False
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False
