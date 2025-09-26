# Pumpkin Stats - Personal Finance Dashboard

Streamlit dashboard for household finance tracking and analysis. Automatically processes bank and credit card CSV exports, categorizes transactions, and provides spending insights.

## Setup

```bash
make setup    # Bootstrap environment, install dependencies
make dev      # Run dashboard locally
make test     # Run test suite
make fmt      # Format code
```

## Usage

1. Run `make dev` to start the dashboard
2. Upload CSV files from your bank/credit card accounts via the sidebar
3. Select a month to view spending analysis and transaction details
4. Review and edit transaction categories as needed

## Supported CSV Formats

- **TD Bank**: Separate debit/credit columns
- **Credit Cards**: Single amount column with transaction dates
- **Generic Bank**: Various formats auto-detected

## Features

- **Duplicate Detection**: Prevents double-counting transactions
- **Auto-Categorization**: Intelligently categorizes transactions
- **Transfer Detection**: Excludes credit card payments and account transfers from spending
- **Manual Overrides**: Edit categories and exclude transactions from budget calculations
- **Monthly Analysis**: Spending breakdown by category with visual charts