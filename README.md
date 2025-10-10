# Pumpkin Stats - Personal Finance Dashboard

Streamlit dashboard for household finance tracking and analysis. Automatically processes bank and credit card CSV exports, categorizes transactions, and provides spending insights. The money must be optimized so that Pumpkin can be fed!

## Setup

### macOS/Linux
```bash
make setup    # Bootstrap environment, install dependencies
make dev      # Run dashboard locally
```

### Windows
```powershell
.\run.ps1 setup    # Bootstrap environment, install dependencies
.\run.ps1 dev      # Run dashboard locally
```

**Note for Windows users:** If the PowerShell script doesn't run due to execution policy restrictions, use one of these options:

**Option 1 - Run once with bypass:**
```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 setup
```

**Option 2 - Allow local scripts permanently (recommended):**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Usage

1. Run `make dev` (macOS/Linux) or `.\run.ps1 dev` (Windows) to start the dashboard
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

## Important: Handling Overlapping Data

**Duplicate detection works based on: date + description + amount + account name.**

If you upload multiple CSV files with overlapping transactions (e.g., downloading July and August separately, both containing July 31st transactions):

- **If the files have the same name pattern** (e.g., `chase-july.csv` and `chase-aug.csv`), duplicates are automatically detected ✅
- **If the files have different names** (e.g., `Chase_Download_20240701.csv` and `Chase_Statement_August.csv`), they will be treated as separate accounts and duplicates will NOT be detected ❌

**Best practice:** If you need to re-upload data for the same account:
1. Go to the sidebar "Data Management" section
2. Delete the old account
3. Upload the new CSV file with the full date range

This ensures no duplicate counting and keeps your data clean.
