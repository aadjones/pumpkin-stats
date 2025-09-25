import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

DATABASE_PATH = Path("data/finance.db")


def get_connection():
    """Get SQLite database connection, create tables if needed."""
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    # Create tables if they don't exist
    conn.executescript(
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

    # Insert default categories if empty
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

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO categories (name, color) VALUES (?, ?)", default_categories)

    conn.commit()
    return conn


def generate_transaction_id(date: str, description: str, amount: float, account: str) -> str:
    """Generate unique ID for transaction to avoid duplicates."""
    content = f"{date}|{description}|{amount}|{account}"
    return hashlib.md5(content.encode()).hexdigest()


def insert_transactions(transactions: List[Dict[str, Any]]) -> int:
    """Insert transactions, avoiding duplicates. Returns count of new transactions."""
    conn = get_connection()
    new_count = 0

    for txn in transactions:
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
                    txn["amount"],
                    txn["account"],
                    txn.get("category", "Other"),
                    txn.get("raw_description", txn["description"]),
                ),
            )
            new_count += 1

    conn.commit()
    conn.close()
    return new_count


def get_transactions_by_month(year: int, month: int) -> pd.DataFrame:
    """Get all transactions for a specific month."""
    conn = get_connection()

    query = """
        SELECT * FROM transactions
        WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
        ORDER BY date DESC, amount DESC
    """

    df = pd.read_sql_query(query, conn, params=(str(year), f"{month:02d}"))
    conn.close()
    return df


def get_spending_by_category(year: int, month: int) -> pd.DataFrame:
    """Get spending totals by category for a month (excluding income and transfers)."""
    conn = get_connection()

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
    conn.close()
    return df


def update_transaction_category(transaction_id: str, new_category: str) -> bool:
    """Update a transaction's category and mark as manually categorized."""
    conn = get_connection()

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
    conn.commit()
    conn.close()
    return success


def get_categories() -> List[str]:
    """Get all available category names."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories ORDER BY name")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories


def get_accounts() -> List[str]:
    """Get all account names."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT account FROM transactions ORDER BY account")
    accounts = [row[0] for row in cursor.fetchall()]
    conn.close()
    return accounts


def update_transaction_override(
    transaction_id: str,
    exclude_from_budget: Optional[bool] = None,
    manual_notes: Optional[str] = None,
    new_category: Optional[str] = None,
) -> bool:
    """Update transaction with manual overrides."""
    conn = get_connection()
    cursor = conn.cursor()

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
        conn.close()
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(transaction_id)

    query = f"""
        UPDATE transactions
        SET {', '.join(updates)}
        WHERE id = ?
    """

    cursor.execute(query, params)
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success
