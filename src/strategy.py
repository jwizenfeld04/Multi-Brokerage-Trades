import logging
import asyncio
import yfinance as yf
from typing import List, Tuple, Dict
from trading_clients.base_client import BaseClient
from trading_clients.schwab_client import SchwabClient
from trading_clients.fennel_client import FennelClient
from trading_clients.tradier_client import TradierClient
from trading_clients.public_client import PublicClient
from trading_clients.first_trade_client import FirstTradeClient
from trading_clients.robinhood_client import RobinhoodClient
from trading_clients.dspac_client import DspacClient
from trading_clients.bbae_client import BbaeClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("TradingBot")


class TradingApp:
    def __init__(self):
        self.clients = [
            RobinhoodClient(),
            SchwabClient(),
            PublicClient(),
            FirstTradeClient(),
            FennelClient(),
            TradierClient(),
            DspacClient(),
            BbaeClient(),
        ]
        self.initialized = False
        self.authenticated_clients = []

    async def initialize(self):
        """
        Initialize trading clients sequentially with proper error handling
        """
        logger.info("---------STARTING PROGRAM-------")

        if self.initialized:
            logger.warning("TradingApp is already initialized")
            return True

        self.authenticated_clients = []  # Reset authenticated clients list

        for client in self.clients:
            try:
                logger.info(f"Attempting to authenticate {client.brokerage_name}...")

                # Try authentication with timeout
                try:
                    async with asyncio.timeout(30):  # 30 second timeout per client
                        authenticated = await client.authenticate()

                        if authenticated:
                            logger.info(
                                f"Successfully authenticated {client.brokerage_name}"
                            )
                            self.authenticated_clients.append(client)
                        else:
                            logger.error(
                                f"Authentication failed for {client.brokerage_name}"
                            )
                            continue

                except asyncio.TimeoutError:
                    logger.error(f"Authentication timeout for {client.brokerage_name}")
                    continue

                # Verify account access after authentication
                if not await self._verify_account_access(client):
                    logger.error(
                        f"Account access verification failed for {client.brokerage_name}"
                    )
                    self.authenticated_clients.remove(client)
                    continue

            except Exception as e:
                logger.error(
                    f"Unexpected error authenticating {client.brokerage_name}: {str(e)}"
                )
                continue

        # Check if we have any authenticated clients
        if not self.authenticated_clients:
            logger.error("No clients were successfully authenticated. Exiting.")
            return False

        # Log summary of authentication results
        total_clients = len(self.clients)
        successful_clients = len(self.authenticated_clients)
        logger.info(
            f"Authentication complete: {successful_clients}/{total_clients} clients authenticated"
        )

        if successful_clients < total_clients:
            failed_clients = [
                c.brokerage_name
                for c in self.clients
                if c not in self.authenticated_clients
            ]
            logger.warning(
                f"Failed to authenticate the following clients: {', '.join(failed_clients)}"
            )

            # Prompt user whether to continue with partial authentication
            response = input(
                "Some clients failed to authenticate. Continue with authenticated clients only? (yes/no): "
            )
            if response.lower() != "yes":
                logger.info("User chose to exit due to partial authentication")
                return False

        self.initialized = True
        return True

    async def _verify_account_access(self, client: BaseClient) -> bool:
        """
        Verify that the authenticated client can access its accounts
        """
        try:
            async with asyncio.timeout(15):  # 15 second timeout for verification
                if not client.accounts:
                    logger.error(f"No accounts found for {client.brokerage_name}")
                    return False

                # Try to get balance for first account to verify access
                first_account = list(client.accounts.values())[0]
                balance = await client.get_account_balance(first_account)
                if balance is None:
                    logger.error(
                        f"Could not verify account access for {client.brokerage_name}"
                    )
                    return False

                return True

        except asyncio.TimeoutError:
            logger.error(f"Account verification timeout for {client.brokerage_name}")
            return False
        except Exception as e:
            logger.error(
                f"Account verification error for {client.brokerage_name}: {str(e)}"
            )
            return False

    async def confirm_ticker(
        self, client: BaseClient, ticker: str
    ) -> Tuple[str, float]:
        if await client.is_tradable(ticker):
            price = await client.get_stock_price(ticker)
            print(f"Current price for {ticker}: ${price:.2f}")

            while True:
                confirm = input(
                    f"Confirm that you want to trade {ticker} for ${price:.2f}? (yes/no): "
                ).lower()
                if confirm == "yes":
                    return ticker, price
                elif confirm == "no":
                    print("Trade cancelled for this ticker.")
                    return None, None
                else:
                    print("Invalid input. Please enter 'yes' or 'no'.")
        else:
            print(f"{ticker} is not tradable on {client.brokerage_name}.")
            return None, None

    async def execute_client_trades(
        self, client: BaseClient, action: str, ticker: str, price: float
    ) -> Tuple[int, int]:
        logger.info(
            f"Initiating {action} trade for {ticker} at ${price:.2f} on {client.brokerage_name}."
        )
        accounts = client.accounts
        if not accounts:
            logger.warning(f"No accounts found on {client.brokerage_name}")
            return 0, 0

        semaphore = asyncio.Semaphore(client.concur_trades)

        async def place_trade(account_id):
            async with semaphore:
                if action == "buy":
                    return await client.place_buy_orders(account_id, ticker, price)
                else:
                    return await client.place_sell_orders(account_id, ticker, price)

        tasks = [place_trade(account_id) for account_id in accounts.values()]
        results = await asyncio.gather(*tasks)

        success_count = sum(results)
        total_trades = len(accounts)

        logger.info(
            f"{success_count}/{total_trades} {action} orders placed on {client.brokerage_name} for {ticker}."
        )
        return success_count, total_trades

    async def execute_trades(
        self, selected_clients: List[BaseClient], tickers: List[str]
    ):
        confirmed_trades = []

        for ticker in tickers:
            confirmed_ticker, price = await self.confirm_ticker(
                selected_clients[0], ticker
            )
            if confirmed_ticker is None:
                logger.warning(f"Skipping {ticker}")
                continue

            action = self.get_trade_action()

            logger.info(f"You've chosen to {action} {confirmed_ticker} at ${price:.2f}")
            confirmed_trades.append((confirmed_ticker, price, action))

        if not confirmed_trades:
            logger.info("No trades confirmed. Exiting.")
            return

        logger.info("\nHere are the trades you've confirmed:")
        for i, (ticker, price, action) in enumerate(confirmed_trades, 1):
            logger.info(f"{i}. {action.capitalize()} {ticker} at ${price:.2f}")

        final_confirm = input(
            "\nDo you want to execute all these trades? (yes/no): "
        ).lower()

        if final_confirm == "yes":
            tasks = []
            for ticker, price, action in confirmed_trades:
                for client in selected_clients:
                    tasks.append(
                        self.execute_client_trades(client, action, ticker, price)
                    )

            results = await asyncio.gather(*tasks)

            total_successful_trades = sum(success for success, _ in results)
            total_trades_attempted = sum(total for _, total in results)

            if total_successful_trades != total_trades_attempted:
                logger.warning(
                    f"Some trades failed: {total_trades_attempted - total_successful_trades} trades had issues."
                )
            else:
                logger.info("All trades were successful.")

            logger.info(
                f"Total successful trades: {total_successful_trades}/{total_trades_attempted}"
            )
        else:
            logger.info("Trade execution cancelled. No trades were placed.")

    async def get_all_account_balances(self) -> Dict[str, float]:
        brokerage_totals = {}
        grand_total = 0.0

        for client in self.clients:
            brokerage_name = client.brokerage_name
            brokerage_total = 0.0
            accounts = client.accounts

            if not accounts:
                print(f"No accounts found on {brokerage_name}")
                continue

            print(f"\nAccounts for {brokerage_name}:")

            balance_tasks = [
                client.get_account_balance(account_number)
                for account_number in accounts.values()
            ]
            balances = await asyncio.gather(*balance_tasks)

            for idx, balance in enumerate(balances):
                account_number = list(accounts.values())[idx]
                balance = balance if balance else 0.0
                brokerage_total += balance
                account_idx = client.get_account_number_from_id(account_number)
                print(
                    f"{brokerage_name} Account {account_idx} balance: ${balance:,.2f}"
                )
            print(f"Total for {brokerage_name}: ${brokerage_total:,.2f}")
            brokerage_totals[brokerage_name] = brokerage_total
            grand_total += brokerage_total

        logger.info("\nBrokerage Totals:")
        for brokerage, total in brokerage_totals.items():
            logger.info(f"  {brokerage}: ${total:,.2f}")

        total_accnts = sum(len(client.accounts) for client in self.clients)

        logger.info(
            f"\nGrand Total Across All {total_accnts} Accounts: ${grand_total:,.2f}"
        )

        return brokerage_totals

    def get_profit_projection(self, ticker: str, split_multiple: int) -> float:
        total_accounts = sum(len(client.accounts) for client in self.clients)

        stock = yf.Ticker(ticker)
        current_price = stock.history(period="1d")["Close"].iloc[-1]
        print(
            f"Current price of {ticker}: ${current_price:,.2f} @ 1:{int(split_multiple)} split."
        )
        projected_price = current_price * split_multiple
        profit_per_account = projected_price - current_price
        print(f"Projected profit per account: ${profit_per_account:,.2f}")
        total_profit = profit_per_account * total_accounts
        return total_profit

    async def get_account_holdings(self, client: BaseClient):
        accounts = client.accounts
        if not accounts:
            logger.warning(f"No accounts found on {client.brokerage_name}")
            return

        logger.info(f"\nAccount Holdings for {client.brokerage_name}:")
        for account_id, account_number in accounts.items():
            holdings = await client.get_stock_holdings(account_number)
            logger.info(f"Account {account_id}:")
            if holdings:
                for ticker, quantity in holdings.items():
                    logger.info(f"  {ticker}: {quantity:.2f} shares")
            else:
                logger.info("No holdings found for this account.")

    def get_action(self):
        print("\nSelect an action:")
        print("[1] Execute trades")
        print("[2] Get account balances")
        print("[3] Get profit projection")
        print("[4] Get account holdings")
        print("[0] Exit")

        while True:
            choice = input("Enter your choice (0-4): ")
            if choice in ["0", "1", "2", "3", "4"]:
                return choice
            print("Invalid choice. Please enter a number between 0 and 4.")

    async def handle_execute_trades(self):
        if not await BaseClient.is_market_open():
            logger.error("Market is not open. Trading not allowed.")
            return

        mode = self.get_trading_mode()
        if mode == 0:
            return

        selected_clients = await self.select_clients(mode)
        tickers = self.get_tickers(mode)

        try:
            await self.execute_trades(selected_clients, tickers)
        except Exception as e:
            logger.error(f"An error occurred during trade execution: {str(e)}")

    async def handle_profit_projection(self):
        ticker = input("Enter the stock ticker symbol: ")
        split_multiple = float(input("Enter the reverse split multiple: "))
        try:
            projected_profit = self.get_profit_projection(ticker, split_multiple)
            print(f"Projected profit for {ticker}: ${projected_profit:.2f}")
        except Exception as e:
            logger.error(f"An error occurred during profit projection: {str(e)}")

    async def handle_account_holdings(self):
        holdings_mode = self.get_holdings_mode()
        selected_clients = (
            self.clients if holdings_mode == 1 else await self.select_clients(2)
        )
        try:
            for client in selected_clients:
                await self.get_account_holdings(client)
        except Exception as e:
            logger.error(f"An error occurred while fetching account holdings: {str(e)}")

    def get_trading_mode(self) -> int:
        print(
            "Select trading mode:\n"
            "[1] Single stock, all clients\n"
            "[2] Single stock, one client\n"
            "[3] Multiple stocks, all clients\n"
            "[4] Multiple stocks, one client\n"
        )
        while True:
            try:
                mode = int(input("Enter a mode (1-4) or '0' to quit: "))
                if mode in [0, 1, 2, 3, 4]:
                    if mode != 0:
                        print(f"You have selected mode {mode}:")
                        if mode == 1:
                            print("Single stock, all clients")
                        elif mode == 2:
                            print("Single stock, one client")
                        elif mode == 3:
                            print("Multiple stocks, all clients")
                        else:
                            print("Multiple stocks, one client")
                    return mode
                print("Invalid selection. Please enter a number between 0 and 4.")
            except ValueError:
                print("Invalid input. Please enter a number between 0 and 4.")

    async def select_clients(self, mode: int) -> List[BaseClient]:
        if mode in [1, 3]:
            return self.clients

        while True:
            try:
                client_prompt = "Select a client:\n"
                for i, client in enumerate(self.clients, start=1):
                    accounts = client.accounts
                    num_accounts = len(accounts) if accounts else 0
                    client_prompt += (
                        f"[{i}] {client.brokerage_name} - {num_accounts} accounts\n"
                    )
                client_prompt += "Enter a number: "

                client_choice = int(input(client_prompt))
                if 1 <= client_choice <= len(self.clients):
                    selected_client = self.clients[client_choice - 1]
                    print(f"You have selected {selected_client.brokerage_name}")
                    return [selected_client]
                print(
                    f"Invalid selection. Please enter a number between 1 and {len(self.clients)}."
                )
            except ValueError:
                print(
                    f"Invalid input. Please enter a number between 1 and {len(self.clients)}."
                )

    def get_tickers(self, mode: int) -> List[str]:
        if mode in [3, 4]:
            tickers_input = input(
                "Enter a comma-separated list of tickers (e.g., AAPL,TSLA,GOOG): "
            )
            return [ticker.strip().upper() for ticker in tickers_input.split(",")]
        return [input("Enter a single ticker: ").strip().upper()]

    def get_trade_action(self) -> str:
        while True:
            action = input("Do you want to 'buy' or 'sell'?: ").lower()
            if action in ["buy", "sell"]:
                return action
            print("Invalid input. Please enter 'buy' or 'sell'.")

    def get_holdings_mode(self) -> int:
        print(
            "Select account holdings mode:\n"
            "[1] All brokerages\n"
            "[2] Select a specific brokerage\n"
        )
        while True:
            try:
                mode = int(input("Enter a mode (1-2): "))
                if mode in [1, 2]:
                    return mode
                print("Invalid selection. Please enter a number between 1 and 2.")
            except ValueError:
                print("Invalid input. Please enter a number between 1 and 2.")

    async def run(self):
        if not await self.initialize():
            logger.error("Initialization failed. Exiting.")
            return

        while True:
            choice = self.get_action()
            if choice == "0":
                break
            elif choice == "1":
                await self.handle_execute_trades()
            elif choice == "2":
                await self.get_all_account_balances()
            elif choice == "3":
                await self.handle_profit_projection()
            elif choice == "4":
                await self.handle_account_holdings()

        await self.shutdown()

    async def shutdown(self):
        await asyncio.sleep(0.25)
        logger.info("Shutdown complete. Exiting now.")


if __name__ == "__main__":
    app = TradingApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        asyncio.run(app.shutdown())
