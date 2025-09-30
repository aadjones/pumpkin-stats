import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

DATABASE_PATH = Path("data/finance.db")
BACKUP_DIR = Path("data/backups")


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
        self._migrate_schema()
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
                auto_exclude_reason TEXT,
                manual_override_type TEXT,
                override_reason TEXT,
                override_category TEXT,
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
            CREATE INDEX IF NOT EXISTS idx_transactions_override ON transactions(manual_override_type);
        """
        )

    def _migrate_schema(self):
        """Add new columns to existing databases."""
        cursor = self.conn.cursor()

        # Check if new columns exist, add them if not
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]

        if "auto_exclude_reason" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN auto_exclude_reason TEXT")

        if "manual_override_type" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN manual_override_type TEXT")

        if "override_reason" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN override_reason TEXT")

        if "override_category" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN override_category TEXT")
            # Migrate existing overrides to 'spending' category
            cursor.execute(
                """
                UPDATE transactions
                SET override_category = 'spending'
                WHERE manual_override_type IS NOT NULL
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
    """
    Generate unique ID for transaction to avoid duplicates.

    Normalizes description and amount to catch duplicates even when formatting varies.
    """
    # Normalize description: uppercase, strip whitespace, collapse multiple spaces
    normalized_desc = str(description).upper().strip()
    normalized_desc = " ".join(normalized_desc.split())  # Collapse multiple spaces to single

    # Round amount to 2 decimal places to handle floating point inconsistencies
    rounded_amount = round(float(amount), 2)

    # Normalize account name similarly
    normalized_account = str(account).upper().strip()
    normalized_account = " ".join(normalized_account.split())

    content = f"{date}|{normalized_desc}|{rounded_amount}|{normalized_account}"
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


def insert_transactions(transactions: List[Dict[str, Any]]) -> tuple[int, int, List[str]]:
    """
    Insert transactions, avoiding duplicates.

    Returns:
        (new_count, total_count, inserted_ids)
    """
    new_count = 0
    total_count = 0
    inserted_ids = []

    with get_connection() as conn:
        for txn in transactions:
            # Validate transaction data
            if not validate_transaction(txn):
                continue

            total_count += 1

            txn_id = generate_transaction_id(txn["date"], txn["description"], txn["amount"], txn["account"])

            # Check if already exists
            existing = conn.execute("SELECT id FROM transactions WHERE id = ?", (txn_id,)).fetchone()

            if not existing:
                conn.execute(
                    """
                    INSERT INTO transactions
                    (id, date, description, amount, account, category, raw_description, auto_exclude_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        txn_id,
                        txn["date"],
                        txn["description"],
                        float(txn["amount"]),  # Ensure numeric
                        txn["account"],
                        txn.get("category", "Other"),
                        txn.get("raw_description", txn["description"]),
                        txn.get("auto_exclude_reason"),
                    ),
                )
                new_count += 1
                inserted_ids.append(txn_id)

    return new_count, total_count, inserted_ids


def delete_transactions_by_ids(transaction_ids: List[str]) -> int:
    """
    Delete transactions by their IDs.

    Args:
        transaction_ids: List of transaction IDs to delete

    Returns:
        Number of transactions deleted
    """
    if not transaction_ids:
        return 0

    with get_connection() as conn:
        placeholders = ",".join("?" * len(transaction_ids))
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", transaction_ids)
        return cursor.rowcount


def delete_transactions_by_account(account_name: str) -> Dict[str, int]:
    """
    Delete all transactions for an account.

    Returns dict with 'deleted' count and 'had_overrides' count.
    Raises ValueError if account doesn't exist.
    """
    with get_connection() as conn:
        # Check account exists
        existing = conn.execute("SELECT COUNT(*) FROM transactions WHERE account = ?", (account_name,)).fetchone()[0]

        if existing == 0:
            raise ValueError(f"Account '{account_name}' not found")

        # Check for manual overrides (warn user they'll lose work)
        overrides = conn.execute(
            """SELECT COUNT(*) FROM transactions
               WHERE account = ?
               AND (manual_override_type IS NOT NULL
                    OR category_source = 'manual')""",
            (account_name,),
        ).fetchone()[0]

        # Delete
        conn.execute("DELETE FROM transactions WHERE account = ?", (account_name,))

        return {"deleted": existing, "had_overrides": overrides}


def get_accounts_with_counts() -> List[Dict[str, any]]:
    """Get list of accounts with transaction counts."""
    with get_connection() as conn:
        results = conn.execute(
            """
            SELECT account, COUNT(*) as count
            FROM transactions
            GROUP BY account
            ORDER BY account
        """
        ).fetchall()

    return [{"account": row[0], "count": row[1]} for row in results]


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


# ============================================================================
# BACKUP AND EXPORT FUNCTIONS
# ============================================================================


def create_backup() -> Optional[Path]:
    """
    Create a backup of the database.

    Returns the path to the backup file, or None if backup failed.
    Automatically maintains the last 7 backups.
    """
    if not DATABASE_PATH.exists():
        return None

    # Create backup directory
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = BACKUP_DIR / f"finance_{timestamp}.db"

    try:
        # Copy database file
        shutil.copy2(DATABASE_PATH, backup_path)

        # Clean up old backups (keep last 7)
        backups = sorted(BACKUP_DIR.glob("finance_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_backup in backups[7:]:
            old_backup.unlink()

        return backup_path
    except Exception as e:
        print(f"Backup failed: {e}")
        return None


def get_backup_info() -> List[Dict[str, Any]]:
    """
    Get information about available backups.

    Returns list of dicts with backup metadata sorted by date (newest first).
    """
    if not BACKUP_DIR.exists():
        return []

    backups = []
    for backup_path in BACKUP_DIR.glob("finance_*.db"):
        stat = backup_path.stat()
        backups.append(
            {
                "path": backup_path,
                "filename": backup_path.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_mtime),
            }
        )

    # Sort by creation time, newest first
    backups.sort(key=lambda x: x["created"], reverse=True)
    return backups


def restore_from_backup(backup_path: Path) -> bool:
    """
    Restore database from a backup file.

    Creates a backup of current database before restoring.

    Args:
        backup_path: Path to the backup file to restore from

    Returns:
        True if restore succeeded, False otherwise
    """
    if not backup_path.exists():
        print(f"Backup file not found: {backup_path}")
        return False

    try:
        # Create a backup of current database before overwriting
        if DATABASE_PATH.exists():
            current_backup = create_backup()
            if not current_backup:
                print("Failed to backup current database before restore")
                return False

        # Copy backup file over current database
        shutil.copy2(backup_path, DATABASE_PATH)
        return True

    except Exception as e:
        print(f"Restore failed: {e}")
        return False


def export_all_transactions_to_csv(output_path: Path) -> bool:
    """
    Export all transactions to a CSV file with all columns.
    Automatically cleans up old exports (keeps last 5).

    Args:
        output_path: Path where CSV should be saved

    Returns:
        True if export succeeded, False otherwise
    """
    try:
        with get_connection() as conn:
            # Get all transactions with all columns
            query = """
                SELECT
                    id,
                    date,
                    description,
                    amount,
                    account,
                    category,
                    category_source,
                    raw_description,
                    exclude_from_budget,
                    manual_notes,
                    auto_exclude_reason,
                    manual_override_type,
                    override_reason,
                    override_category,
                    created_at,
                    updated_at
                FROM transactions
                ORDER BY date DESC, amount DESC
            """
            df = pd.read_sql_query(query, conn)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Export to CSV
        df.to_csv(output_path, index=False)

        # Clean up old exports (keep last 5)
        export_dir = output_path.parent
        exports = sorted(export_dir.glob("export_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_export in exports[5:]:
            try:
                old_export.unlink()
            except:
                pass  # Ignore cleanup errors

        return True

    except Exception as e:
        print(f"Export failed: {e}")
        return False
