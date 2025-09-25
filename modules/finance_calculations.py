"""
Proper finance calculations following standard accounting principles.

Key principles:
1. Credit card PURCHASES = expenses (categorize by what was bought)
2. Credit card PAYMENTS = transfers (exclude from spending)
3. Account transfers = transfers (exclude from spending)
4. Synthesize all accounts for household view
"""

from typing import Tuple

import pandas as pd

from . import database


def _normalize_boolean_column(series: pd.Series) -> pd.Series:
    """
    Normalize a boolean column to handle NULLs, corrupted data, and various data types.

    Returns a clean boolean series where:
    - True/1/'1'/non-zero numbers -> True
    - False/0/'0'/None/NaN/empty strings -> False
    - Corrupted binary data -> False (safe default)
    """

    def normalize_value(val):
        # Handle complex types first to avoid pd.isna errors
        if isinstance(val, (list, dict, tuple)):
            return False
        if hasattr(val, "__array__") and hasattr(val, "size"):
            # Handle numpy arrays and similar
            return False

        try:
            if pd.isna(val):
                return False
        except (ValueError, TypeError):
            # pd.isna can fail on some types, default to False
            return False

        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        if isinstance(val, bytes):
            # Handle corrupted binary data by defaulting to False
            return False
        # For any other type, default to False
        return False

    return series.apply(normalize_value)


def get_household_finances(year: int, month: int) -> Tuple[float, float, float, pd.DataFrame]:
    """
    Get household finances following proper accounting principles.

    Returns:
        spending, income, net, transactions_df
    """
    # Get all transactions for the month
    transactions_df = database.get_transactions_by_month(year, month)

    if transactions_df.empty:
        return 0.0, 0.0, 0.0, transactions_df

    # Normalize exclude_from_budget column to handle NULLs and edge cases
    transactions_df["exclude_from_budget"] = _normalize_boolean_column(transactions_df["exclude_from_budget"])

    # SPENDING = negative amounts that are NOT transfers and NOT manually excluded
    # This includes:
    # - Credit card purchases (groceries, gas, restaurants, etc.)
    # - Bank account debits for actual purchases
    # - Interest charges, fees for services
    spending_transactions = transactions_df[
        (transactions_df["amount"] < 0)
        & (~transactions_df["category"].isin(["Transfers", "Credit Card Payment"]))
        & (~transactions_df["exclude_from_budget"])
    ]
    spending = abs(spending_transactions["amount"].sum())

    # INCOME = positive amounts that are actual income
    # This includes:
    # - Paychecks, deposits
    # - Cashback, refunds
    # - Interest earned
    # Excludes transfers between accounts

    # First, exclude obvious transfers and manually excluded transactions
    income_transactions = transactions_df[
        (transactions_df["amount"] > 0)
        & (~transactions_df["category"].isin(["Transfers", "Credit Card Payment"]))
        & (~transactions_df["exclude_from_budget"])
    ]

    # Use whitelist approach: only count transactions that are clearly income
    # Based on Dara's data, legitimate income includes:
    # - Payroll (DIRECT DEP, PAYROLL)
    # - Cashback and refunds from credit cards
    # - Work reimbursements
    # - Gifts received

    income_patterns = [
        "PAYROLL",
        "DIRECT DEP",
        "DIRECTDEP",
        "REIMBURS",
        "REFUND",
        "CASHBACK",
        "CASH BACK",
        "GIFT",
        "BONUS",
        "INTEREST",
    ]

    # Filter to only include clear income patterns
    legitimate_income = income_transactions[
        income_transactions["description"].str.upper().str.contains("|".join(income_patterns), regex=True, na=False)
    ]

    # Also include small positive amounts from credit cards (likely cashback/refunds)
    credit_card_income = income_transactions[
        (income_transactions["account"].str.contains("Credit", case=False))
        & (income_transactions["amount"] < 100)  # Small amounts likely cashback
    ]

    # Combine legitimate income sources
    all_income = pd.concat([legitimate_income, credit_card_income]).drop_duplicates()

    income = all_income["amount"].sum()

    # NET = income - spending
    net = income - spending

    return spending, income, net, transactions_df


def get_spending_by_category(year: int, month: int) -> pd.DataFrame:
    """Get spending breakdown by category, excluding transfers."""
    transactions_df = database.get_transactions_by_month(year, month)

    if transactions_df.empty:
        return pd.DataFrame()

    # Normalize exclude_from_budget column to handle NULLs and edge cases
    transactions_df["exclude_from_budget"] = _normalize_boolean_column(transactions_df["exclude_from_budget"])

    # Only include actual spending (negative amounts, not transfers, not excluded)
    spending_transactions = transactions_df[
        (transactions_df["amount"] < 0)
        & (~transactions_df["category"].isin(["Transfers", "Credit Card Payment"]))
        & (~transactions_df["exclude_from_budget"])
    ]

    if spending_transactions.empty:
        return pd.DataFrame()

    # Group by category and sum
    category_spending = (
        spending_transactions.groupby("category")
        .agg({"amount": lambda x: abs(x.sum()), "description": "count"})  # Convert to positive
        .reset_index()
    )

    category_spending.columns = ["category", "total_spent", "transaction_count"]
    category_spending = category_spending.sort_values("total_spent", ascending=False)

    return category_spending


def get_account_breakdown(year: int, month: int) -> pd.DataFrame:
    """Get spending/income breakdown by account."""
    transactions_df = database.get_transactions_by_month(year, month)

    if transactions_df.empty:
        return pd.DataFrame()

    # Separate spending and income
    spending_by_account = (
        transactions_df[
            (transactions_df["amount"] < 0) & (~transactions_df["category"].isin(["Transfers", "Credit Card Payment"]))
        ]
        .groupby("account")["amount"]
        .sum()
        .abs()
    )

    income_by_account = (
        transactions_df[
            (transactions_df["amount"] > 0) & (~transactions_df["category"].isin(["Transfers", "Credit Card Payment"]))
        ]
        .groupby("account")["amount"]
        .sum()
    )

    # Combine into summary
    account_summary = pd.DataFrame({"spending": spending_by_account, "income": income_by_account}).fillna(0)

    account_summary["net"] = account_summary["income"] - account_summary["spending"]

    return account_summary.reset_index()


def reclassify_transfers():
    """
    Clean up transfer categorization based on proper accounting principles.
    This should be run once to fix existing data.
    """
    conn = database.get_connection()

    # Credit card payments should be marked as transfers
    credit_payment_keywords = [
        "CARD SERV",
        "CREDIT CRD",
        "EPAY",
        "E-PAYMENT",
        "ONLINE PMT",
        "AUTO PMT",
        "PAYMENT THANK YOU",
    ]

    # Account transfers should be marked as transfers
    transfer_keywords = ["ONLINE TRANSFER", "XFER TRANSFER", "RECURRING TRANSFER", "TRANSFER TO", "TRANSFER FROM"]

    # Build the update query
    all_keywords = credit_payment_keywords + transfer_keywords
    conditions = " OR ".join([f"UPPER(description) LIKE '%{keyword}%'" for keyword in all_keywords])

    # Update transactions to be transfers
    update_query = f"""
        UPDATE transactions
        SET category = 'Transfers', category_source = 'auto'
        WHERE ({conditions})
        AND category != 'Transfers'
    """

    cursor = conn.cursor()
    cursor.execute(update_query)
    updated_count = cursor.rowcount

    conn.commit()
    conn.close()

    return updated_count
