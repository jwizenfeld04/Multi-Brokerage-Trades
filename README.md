# Multi-Brokerage-Trades

**Multi-Brokerage-Trades** is a Python-based, CLI-driven application that enables you to authenticate and place trades asynchronously across **8 different brokerages** within a single unified interface. It also offers basic portfolio management functionalities such as retrieving account balances, viewing holdings, and projecting potential profit from reverse split arbitrage trades across multiple brokerages.

Currently supported brokerages:

- Robinhood
- Charles Schwab
- Public
- FirstTrade
- Fennel
- Tradier
- DSPAC
- BBAE

> **Disclaimer**  
> This software is provided for **educational purposes only**. It is **not** investment advice. Trading involves substantial risk and may result in financial loss. Use at your own risk. The project maintainers and contributors do not accept liability for any losses incurred. By using this tool, you agree that you are solely responsible for all your trading decisions.

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Installation/Setup](#installationsetup)
4. [Usage](#usage)
   - [Initialization & Authentication](#initialization--authentication)
   - [CLI Workflow](#cli-workflow)
5. [Contributing](#contributing)
6. [Future Plans & Roadmap](#future-plans--roadmap)
7. [License](#license)

## Features

- **Multi-Brokerage Authentication & Trading**  
  Authenticate with up to 8 brokerages (Robinhood, Schwab, Public, FirstTrade, Fennel, Tradier, DSPAC, BBAE) sequentially. Partial authentication is supported, and the app will prompt whether to proceed if any brokerages fail to authenticate.

- **Asynchronous Order Placement**  
  Place buy/sell orders (currently 1 share by default) across multiple brokerages asynchronously, with concurrency controls in place for each brokerage.

- **Portfolio Management**

  - Retrieve account balances and holdings from each brokerage.
  - Summaries of total funds across brokerages.
  - Basic profit projection for reverse stock split arbitrage.

- **CLI-Driven**
  - Interactive prompts guide you through authentication, selecting tickers, choosing brokerages, and placing trades.
  - Simply run the script from your terminal or console—no special UI required.

```
Select an action:
[1] Execute trades
[2] Get account balances
[3] Get profit projection
[4] Get account holdings
[0] Exit
```

## Project Structure

Below is a simplified view of the repository layout (focusing on the `src/` directory). The names of some files (like `*.pkl` and `__pycache__`) have been omitted for brevity:

```
src
 ┣ __init__.py
 ┣ strategy.py // Main script to run CLI
 ┗ trading_clients
   ┣ __init__.py
   ┣ base_client.py // Abstract class for all brokerage clients
   ┣ bbae_client.py
   ┣ dspac_client.py
   ┣ fennel_client.py
   ┣ first_trade_client.py
   ┣ public_client.py
   ┣ robinhood_client.py
   ┣ schwab_client.py
   ┣ tradier_client.py
   ┗ redbridge_apis
     ┣ __init__.py
     ┣ bbeae_api_new.py
     ┣ dspac_api_new.py
```

## Installation/Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/jwizenfeld04/Multi-Brokerage-Trades.git
   cd Multi-Brokerage-Trades
   ```
2. **Create & Activate Virtual Environment**
   ```bash
    python -m venv venv
    source venv/bin/activate
   ```
   (On Windows, use venv\Scripts\activate.)
3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure credentials**
   Before running the application, create a `.env` file in the root directory of this project. Include the following environment variables:

   ```
    # Robinhood Credentials
    ROBINHOOD_USERNAME=<Your_Robinhood_Login_Email>
    ROBINHOOD_PASSWORD=<Your_Robinhood_Password>
    ROBINHOOD_TOTP=<Your_2FA_Secret_Key>

   # Schwab
    SCHWAB_API_KEY=<Your_Schwab_API_Key>
    SCHWAB_API_SECRET=<Your_Schwab_API_Secret>

    # Public
    PUBLIC_EMAIL=<Your_Public_Email>
    PUBLIC_PASSWORD=<Your_Public_Password>

    # First Trade
    FIRST_TRADE_USERNAME=<Your_FirstTrade_Username>
    FIRST_TRADE_PASSWORD=<Your_FirstTrade_Password>
    FIRST_TRADE_EMAIL=<Your_FirstTrade_Email>

    # Fennel
    FENNEL_EMAIL=<Your_Fennel_Email>

    # Tradier
    TRADIER_API_KEY=<Your_Tradier_API_Key>
    TRADIER_ACCOUNT_NUMBERS=<Comma_Separated_List_Of_AccountNumbers>

    # DSPAC
    DSPAC_USERNAME=<Phone_Or_Email>
    DSPAC_PASSWORD=<Your_DSPAC_Password>

    # BBAE
    BBAE_USERNAME=<Phone_Or_Email>
    BBAE_PASSWORD=<Your_BBAE_Password>
   ```

Token / Credentials Storage:

- Local Storage:
  Credentials and tokens are primarily stored in src/creds/ (e.g., .pkl, .json files).
- Robinhood & Tradier:
  These do not rely on local .pkl storage. Must have TOTP/2FA set up with an authenticator app (ie. Microsoft Authenticator) for Robinhhood.
- Other Brokerages:
  Use local pickled token files or JSON files for authenticated sessions, so you don’t have to re-log in constantly.
- Security Note: Keep your .env file private. Never commit credentials or tokens to version control.

## Usage

### Initialization & Authentication

Run the `strategy.py` script from within your virtual environment:

```bash
cd src
python strategy.py
```

The program will sequentially attempt to authenticate each brokerage:

You may be prompted for 2FA codes, captchas, or web-based logins—follow the instructions in the console.
If any brokerage fails to authenticate, you can choose to proceed with others or abort. Running the script again will sometimes fix issues.
After authentication, the program will display a menu of possible actions:

```
Select an action:
[1] Execute trades
[2] Get account balances
[3] Get profit projection
[4] Get account holdings
[0] Exit
Enter your choice (0-4):
```

## CLI Workflow

### Execute Trades (1)

1. Checks if the market is open. If not, trading is disallowed.
2. Choose a trading mode (single vs. multiple stocks, one client vs. all clients).
3. Enter your desired ticker(s).
4. Enter “buy” or “sell.”
5. Confirm the final details and execution.

### Account Balances (2)

Retrieves the cash/portfolio balance from each authenticated brokerage and displays a grand total across all accounts.

### Profit Projection (3)

For a given ticker and a specified reverse split multiple, projects potential reverse split arbitrage profit per account and the total across all brokerages.

### Account Holdings (4)

For each selected brokerage, fetches the current holdings (tickers and share quantities).

### Note: Currently, buy/sell logic is configured to place 1 share at market price. It will only buy if the account does not already hold that ticker, and only sell if it does. Future enhancements will allow more granular quantity and price control.

## Contributing

All contributions and improvements are welcome! Follow these guidelines:

1. **Fork & Clone**

   - Fork the repository, then clone it locally.

2. **Create a New Branch**

   - Name branches according to the feature or fix.
     - Example: `feature/improve-docs` or `bugfix/timeout-issue`.

3. **Coding Standards**

   - Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines.
   - Maintain consistent formatting and clear variable naming.

4. **Pull Requests**

   - Open a PR (Pull Request) against the `main` branch (or a development branch if specified).
   - Describe your changes, rationale, and any testing performed.
   - If you’re introducing a new feature, consider updating the documentation or providing usage examples.

5. **Testing**
   - Currently, no formal test suite is included. You may add tests if relevant.
   - We recommend using mock responses for brokerage APIs to avoid hitting real accounts in tests.

## Future Plans & Roadmap

1. **More Control Over Trade Amounts**

   - Allow specifying share quantity and optional limit/stop prices.

2. **Enhanced Portfolio Insights**

   - Collect additional financial data, cost-basis calculations, and automated rebalancing features.

3. **Additional Brokerages**

   - The `base_client.py` class can be extended to support more brokerages with similar API capabilities.

4. **Automation & Scheduling**
   - Potentially schedule trades or polls for updated balances on a recurring basis.
