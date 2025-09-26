# Architecture Overview

## Project Structure

```
├── app.py                    # Main Streamlit application
├── modules/
│   ├── data_ingestion.py     # CSV parsing and transaction processing
│   ├── database.py           # SQLite operations and data persistence
│   ├── finance_calculations.py  # Core financial logic and accounting
│   └── charts.py             # Plotly chart generation
├── data/
│   ├── finance.db            # SQLite database (auto-created)
│   └── *.csv                 # Bank/credit card export files
└── tests/                    # Test suite
```

## Data Flow

1. **CSV Upload** → CSV files uploaded via Streamlit sidebar
2. **Format Detection** → `TransactionParser.detect_format()` identifies bank vs credit card format
3. **Transaction Parsing** → Format-specific parsers extract date, amount, description, account
4. **Auto-Categorization** → Rules-based categorization assigns spending categories
5. **Duplicate Prevention** → MD5 hash of `date|description|amount|account` prevents duplicates
6. **Database Storage** → Transactions stored in SQLite with `INSERT OR IGNORE`
7. **Financial Analysis** → `finance_calculations.py` computes spending/income following accounting principles

## Transaction Processing Details

### Duplicate Detection Strategy

The system prevents double-counting through transaction ID generation:

```python
def generate_transaction_id(date, description, amount, account):
    content = f"{date}|{description}|{amount}|{account}"
    return hashlib.md5(content.encode()).hexdigest()
```

This ensures:
- Same transaction from multiple file uploads = single database entry
- Identical amounts on same day = different IDs if descriptions differ
- Cross-account transfers = separate entries (intended behavior)

### Income vs Spending Classification

**Income Detection (Whitelist Approach)**:
- Only positive amounts matching specific patterns count as income
- Patterns: `PAYROLL`, `DIRECT DEP`, `REIMBURS`, `REFUND`, `CASHBACK`, `BONUS`, `INTEREST`
- Small credit card positive amounts (<$100) assumed to be cashback
- Excludes transfers between accounts and credit card payments

**Spending Detection**:
- Negative amounts from actual purchases (groceries, gas, restaurants)
- Excludes transfers (`Transfers` category) and credit card payments
- Excludes manually marked transactions (`exclude_from_budget = True`)

### Transfer Detection and Exclusion

**Credit Card Payments** (excluded from spending):
- Keywords: `CARD SERV`, `CREDIT CRD`, `EPAY`, `E-PAYMENT`, `ONLINE PMT`, `AUTO PMT`
- Rationale: Paying credit card is moving money between accounts, not spending

**Account Transfers** (excluded from spending):
- Keywords: `ONLINE TRANSFER`, `XFER TRANSFER`, `RECURRING TRANSFER`
- Rationale: Moving money between your own accounts isn't spending

**Key Principle**: Only count actual purchases as spending. Money movements between accounts are transfers.

### Category Auto-Assignment

**Bank Transactions**:
```python
def _auto_categorize_bank(txn_type, description, amount):
    if txn_type in ["DIRECTDEP", "CREDIT"] or "PAYROLL" in description:
        return "Income"
    elif amount > 0:
        return "Income"  # Other positive amounts
    elif "GROCERY" in description:
        return "Groceries"
    elif "GAS" in description or "SHELL" in description:
        return "Automotive"
    elif "VET" in description or "PETCO" in description:
        return "Pumpkin"
    # ... more rules
```

**Credit Card Transactions**:
- Uses institution-provided categories when available
- Overrides with description-based rules for pet stores
- Skips credit card payment transactions entirely

### Data Integrity Safeguards

1. **Boolean Column Normalization**: Handles corrupted `exclude_from_budget` data safely
2. **Null Handling**: Graceful handling of missing/malformed CSV fields
3. **Type Coercion**: Robust amount parsing with fallbacks
4. **Transaction Validation**: Skips rows with missing critical data (date, amount)

### Monthly Calculations

For each month, the system:

1. **Loads all transactions** for the specified month
2. **Normalizes boolean flags** to handle database inconsistencies
3. **Calculates spending**: `SUM(ABS(amount))` where `amount < 0` AND `category NOT IN ('Transfers', 'Credit Card Payment')` AND `exclude_from_budget = FALSE`
4. **Calculates income**: `SUM(amount)` where `amount > 0` AND matches income patterns AND not excluded
5. **Computes net**: `income - spending`

This ensures:
- No double-counting of transfers
- Credit card purchases counted as spending (when you bought something)
- Credit card payments excluded (just moving money to pay the bill)
- Manual exclusions respected (for one-off corrections)

## Database Schema

```sql
CREATE TABLE transactions (
    id TEXT PRIMARY KEY,              -- MD5 hash for deduplication
    date DATE NOT NULL,               -- Transaction date (YYYY-MM-DD)
    description TEXT NOT NULL,        -- Cleaned transaction description
    amount REAL NOT NULL,             -- Amount (negative = spending, positive = income)
    account TEXT NOT NULL,            -- Account name (parsed from filename)
    category TEXT,                    -- Spending category
    category_source TEXT DEFAULT 'auto', -- 'auto' or 'manual'
    raw_description TEXT,             -- Original description from CSV
    exclude_from_budget BOOLEAN DEFAULT 0, -- Manual override flag
    manual_notes TEXT,                -- User notes for manual edits
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The schema supports:
- **Duplicate prevention** via unique ID primary key
- **Manual overrides** for category and budget inclusion
- **Audit trail** with created/updated timestamps
- **Source tracking** to distinguish auto vs manual categorization