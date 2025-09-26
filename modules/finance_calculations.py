"""
Proper finance calculations following standard accounting principles.

Key principles:
1. Credit card PURCHASES = expenses (categorize by what was bought)
2. Credit card PAYMENTS = transfers (exclude from spending)
3. Account transfers = transfers (exclude from spending)
4. Synthesize all accounts for household view
"""

from typing import Dict, Tuple

import pandas as pd

from . import database
from .transaction_overrides import TransactionOverrideManager


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


def get_household_finances(year: int, month: int) -> Tuple[float, float, float, pd.DataFrame, Dict]:
    """
    Get household finances following proper accounting principles.

    Returns:
        spending, income, net, transactions_df, breakdown_info
    """
    override_manager = TransactionOverrideManager()

    # Get transactions with overrides applied
    budget_transactions = override_manager.get_budget_transactions(year, month)
    all_transactions = override_manager.get_effective_transactions(year, month)

    if budget_transactions.empty:
        breakdown = override_manager.get_calculation_breakdown(year, month)
        return 0.0, 0.0, 0.0, all_transactions, breakdown

    # SPENDING = negative amounts that are included in budget
    # This automatically excludes transfers and manually excluded items
    spending_transactions = budget_transactions[budget_transactions["amount"] < 0]
    spending = abs(spending_transactions["amount"].sum())

    # INCOME = use override manager's filtered income logic (whitelist + manual inclusions)
    income_transactions = override_manager.get_filtered_income_transactions(year, month)
    income = income_transactions["amount"].sum() if not income_transactions.empty else 0.0

    # NET = income - spending
    net = income - spending

    # Get calculation breakdown for transparency
    breakdown = override_manager.get_calculation_breakdown(year, month)

    return spending, income, net, all_transactions, breakdown


def get_spending_by_category(year: int, month: int) -> pd.DataFrame:
    """Get spending breakdown by category, excluding transfers."""
    override_manager = TransactionOverrideManager()
    budget_transactions = override_manager.get_budget_transactions(year, month)

    if budget_transactions.empty:
        return pd.DataFrame()

    # Only include actual spending (negative amounts)
    spending_transactions = budget_transactions[budget_transactions["amount"] < 0]

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
    override_manager = TransactionOverrideManager()
    budget_transactions = override_manager.get_budget_transactions(year, month)

    if budget_transactions.empty:
        return pd.DataFrame()

    # Separate spending and income
    spending_by_account = (
        budget_transactions[budget_transactions["amount"] < 0].groupby("account")["amount"].sum().abs()
    )

    income_by_account = budget_transactions[budget_transactions["amount"] > 0].groupby("account")["amount"].sum()

    # Combine into summary
    account_summary = pd.DataFrame({"spending": spending_by_account, "income": income_by_account}).fillna(0)

    account_summary["net"] = account_summary["income"] - account_summary["spending"]

    return account_summary.reset_index()


def reclassify_transfers():
    """
    Clean up transfer categorization based on proper accounting principles.
    This should be run once to fix existing data.
    """
    with database.get_connection() as conn:
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

    return updated_count
