import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

DATABASE_PATH = Path("data/finance.db")


class DatabaseConnection:
    """Context manager for database connections."""

    def __init__(self):
        self.conn = None

    def __enter__(self):
        DATABASE_PATH.parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(DATABASE_PATH)

        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Create tables if they don't exist
        self._create_tables()
        self._insert_default_categories()

        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            self.conn.close()

    def _create_tables(self):
        """Create database tables if they don't exist."""
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                date DATE NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                account TEXT NOT NULL,
                category TEXT,
                category_source TEXT DEFAULT 'auto',
                raw_description TEXT,
                exclude_from_budget BOOLEAN DEFAULT 0,
                manual_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                name TEXT PRIMARY KEY,
                color TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS accounts (
                name TEXT PRIMARY KEY,
                bank TEXT,
                account_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
            CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
            CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account);
        """
        )

    def _insert_default_categories(self):
        """Insert default categories if empty."""
        default_categories = [
            ("Food & drink", "#20B2AA"),
            ("Groceries", "#4682B4"),
            ("Automotive", "#FFA500"),
            ("Pumpkin", "#DDA0DD"),
            ("Bills & utilities", "#8B4513"),
            ("Shopping", "#FF69B4"),
            ("Travel", "#9370DB"),
            ("Health & wellness", "#32CD32"),
            ("Entertainment", "#FFD700"),
            ("Fees & adjustments", "#FF4500"),
            ("Income", "#00FF00"),
            ("Transfers", "#A9A9A9"),
            ("Other", "#808080"),
        ]

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO categories (name, color) VALUES (?, ?)", default_categories)


def get_connection():
    """Get database connection context manager."""
    return DatabaseConnection()


def generate_transaction_id(date: str, description: str, amount: float, account: str) -> str:
    """Generate unique ID for transaction to avoid duplicates."""
    content = f"{date}|{description}|{amount}|{account}"
    return hashlib.md5(content.encode()).hexdigest()


def validate_transaction(txn: Dict[str, Any]) -> bool:
    """Validate transaction data for basic integrity."""
    # Check required fields
    required_fields = ["date", "description", "amount", "account"]
    for field in required_fields:
        if not txn.get(field):
            return False

    # Validate amount is a number
    try:
        amount = float(txn["amount"])
        # Check for reasonable bounds (not extreme values)
        if abs(amount) > 1_000_000:  # No single transaction over $1M
            return False
    except (ValueError, TypeError):
        return False

    # Validate date format (basic check)
    date_str = str(txn["date"])
    if len(date_str) < 8 or "-" not in date_str:
        return False

    # Validate description is not empty or just whitespace
    if not str(txn["description"]).strip():
        return False

    return True


def insert_transactions(transactions: List[Dict[str, Any]]) -> int:
    """Insert transactions, avoiding duplicates. Returns count of new transactions."""
    new_count = 0

    with get_connection() as conn:
        for txn in transactions:
            # Validate transaction data
            if not validate_transaction(txn):
                continue

            txn_id = generate_transaction_id(txn["date"], txn["description"], txn["amount"], txn["account"])

            # Check if already exists
            existing = conn.execute("SELECT id FROM transactions WHERE id = ?", (txn_id,)).fetchone()

            if not existing:
                conn.execute(
                    """
                    INSERT INTO transactions
                    (id, date, description, amount, account, category, raw_description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        txn_id,
                        txn["date"],
                        txn["description"],
                        float(txn["amount"]),  # Ensure numeric
                        txn["account"],
                        txn.get("category", "Other"),
                        txn.get("raw_description", txn["description"]),
                    ),
                )
                new_count += 1

    return new_count


def get_transactions_by_month(year: int, month: int) -> pd.DataFrame:
    """Get all transactions for a specific month."""
    with get_connection() as conn:
        query = """
            SELECT * FROM transactions
            WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
            ORDER BY date DESC, amount DESC
        """

        df = pd.read_sql_query(query, conn, params=(str(year), f"{month:02d}"))
    return df


def get_spending_by_category(year: int, month: int) -> pd.DataFrame:
    """Get spending totals by category for a month (excluding income and transfers)."""
    with get_connection() as conn:
        query = """
            SELECT
                category,
                SUM(ABS(amount)) as total_spent,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE strftime('%Y', date) = ?
            AND strftime('%m', date) = ?
            AND amount < 0
            AND category != 'Transfers'
            GROUP BY category
            ORDER BY total_spent DESC
        """

        df = pd.read_sql_query(query, conn, params=(str(year), f"{month:02d}"))
    return df


def update_transaction_category(transaction_id: str, new_category: str) -> bool:
    """Update a transaction's category and mark as manually categorized."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE transactions
            SET category = ?, category_source = 'manual', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (new_category, transaction_id),
        )

        success = cursor.rowcount > 0
    return success


def get_categories() -> List[str]:
    """Get all available category names."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name")
        categories = [row[0] for row in cursor.fetchall()]
    return categories


def get_accounts() -> List[str]:
    """Get all account names."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT account FROM transactions ORDER BY account")
        accounts = [row[0] for row in cursor.fetchall()]
    return accounts


def update_transaction_override(
    transaction_id: str,
    exclude_from_budget: Optional[bool] = None,
    manual_notes: Optional[str] = None,
    new_category: Optional[str] = None,
) -> bool:
    """Update transaction with manual overrides."""
    updates = []
    params = []

    if exclude_from_budget is not None:
        updates.append("exclude_from_budget = ?")
        params.append(exclude_from_budget)

    if manual_notes is not None:
        updates.append("manual_notes = ?")
        params.append(manual_notes)

    if new_category is not None:
        updates.append("category = ?")
        updates.append("category_source = 'manual'")
        params.append(new_category)

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(transaction_id)

    query = f"""
        UPDATE transactions
        SET {', '.join(updates)}
        WHERE id = ?
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        success = cursor.rowcount > 0
    return success
