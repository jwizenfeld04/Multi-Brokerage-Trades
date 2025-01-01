import os
import json
import asyncio
import dotenv
from typing import Dict, Optional

from uvatradier import Account, EquityOrder, Quotes

from .base_client import BaseClient


class TradierClient(BaseClient):
    def __init__(self):
        super().__init__(brokerage_name="Tradier", transaction_fee=0.35)
        dotenv.load_dotenv()
        self.tradier_token = os.getenv("TRADIER_API_KEY")
        self.tradier_account_ids = json.loads(os.getenv("TRADIER_ACCOUNT_NUMBERS"))
        self.authenticated = False
        self.accounts: Dict[int, str] = {}
        self.account_instances: Dict[int, Account] = {}

    async def authenticate(self) -> bool:
        """Authenticate asynchronously by validating credentials and making a test API call."""
        if not self.tradier_token or not self.tradier_account_ids:
            self.logger.error("Missing Tradier API token or account numbers.")
            return False

        # Attempt to authenticate by creating an account instance and making a test API call
        try:
            # Use the first account to make an API call as a test
            test_account_id = self.tradier_account_ids[0]

            # Run the blocking account creation call asynchronously
            account = await asyncio.to_thread(
                Account, test_account_id, self.tradier_token, live_trade=True
            )

            # Make a small test call to ensure the token works
            account_balance = await asyncio.to_thread(account.get_account_balance)

            # If the API call succeeds, mark as authenticated
            if not account_balance.empty:
                self.authenticated = True
                await self.get_accounts()
                return True
            else:
                self.logger.error("Failed to authenticate with Tradier API.")
                return False
        except Exception as e:
            self.logger.error(f"Error during authentication: {str(e)}")
            return False

    async def get_accounts(self) -> Optional[Dict[int, str]]:
        """Retrieve accounts asynchronously after ensuring authentication."""
        if not self.authenticated:
            return None

        # Now that we are authenticated, retrieve the accounts
        try:
            for idx, account_id in enumerate(self.tradier_account_ids):
                # Account creation can be blocking, so we use asyncio.to_thread
                account = await asyncio.to_thread(
                    Account, account_id, self.tradier_token, live_trade=True
                )
                self.accounts[idx + 1] = account_id
                self.account_instances[idx + 1] = account

            self.logger.info(
                f"Retrieved {len(self.accounts)} {self.brokerage_name} accounts"
            )
            return self.accounts
        except Exception as e:
            self.logger.error(f"Failed to retrieve accounts: {str(e)}")
            return None

    async def get_account_balance(self, account_id: str) -> Optional[float]:
        """Check account balance asynchronously."""
        if not self.accounts:
            return None
        account_idx = self.get_account_number_from_id(account_id)
        if account_idx is not None:
            account = self.account_instances.get(account_idx)
            # Run the blocking call in a thread using asyncio
            account_balance_df = await asyncio.to_thread(account.get_account_balance)
            return account_balance_df.loc[account_balance_df.index[0], "total_cash"]
        return None

    async def get_stock_holdings(self, account_id: str) -> Dict[str, float]:
        """Gets current positions in the account asynchronously."""
        if not self.accounts:
            return {}
        account_idx = self.get_account_number_from_id(account_id)
        if account_idx is not None:
            account = self.account_instances.get(account_idx)
            # Run the blocking call in a thread using asyncio
            stocks = {}
            account_positions_df = await asyncio.to_thread(account.get_positions)
            if not account_positions_df.empty:
                for _, row in account_positions_df.iterrows():
                    symbol = row.get("symbol")
                    quantity = float(row.get("quantity"))
                    if symbol and quantity is not None:
                        stocks[symbol] = float(quantity)
            return stocks
        self.logger.error(
            f"Error checking positions for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}"
        )
        return None

    async def is_tradable(self, ticker: str) -> bool:
        """Check if the ticker is tradable asynchronously."""
        if not self.accounts:
            return False
        quote = await self.get_stock_price(ticker)
        if quote is None:
            return False
        return True

    async def get_stock_price(self, ticker: str) -> Optional[float]:
        """Get stock price asynchronously."""
        if not self.accounts:
            return None
        # Run the blocking call in a thread using asyncio
        quotes = Quotes(
            self.tradier_account_ids[0], self.tradier_token, live_trade=True
        )
        quote_df = await asyncio.to_thread(quotes.get_quote_day, ticker)
        if quote_df.empty:
            return None
        return float(quote_df.get("last")[0])

    async def _place_buy_orders(
        self, account_id: str, ticker: str, price: float, order_type: str = "market"
    ) -> bool:
        """Place buy orders asynchronously."""
        try:
            # Run the blocking call in a thread using asyncio
            order_instance = await asyncio.to_thread(
                EquityOrder, account_id, self.tradier_token, live_trade=True
            )
            response = await asyncio.to_thread(
                order_instance.order,
                symbol=ticker,
                side="buy",
                quantity=1,
                order_type=order_type,
            )
            if "errors" in response:
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
        """Place sell orders asynchronously."""
        try:
            # Run the blocking call in a thread using asyncio
            order_instance = await asyncio.to_thread(
                EquityOrder, account_id, self.tradier_token, live_trade=True
            )
            response = await asyncio.to_thread(
                order_instance.order,
                symbol=ticker,
                side="sell",
                quantity=1,
                order_type=order_type,
            )
            if "errors" in response:
                print(response)
                raise Exception
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to place order for {self.brokerage_name} account {self.get_account_number_from_id(account_id)}: {str(e)}"
            )
            return False
