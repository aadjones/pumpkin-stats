"""
Tests for core database operations.

Focuses on transaction lifecycle: insert, delete, and re-insert behavior.
"""

import pytest

from modules import database


class TestTransactionLifecycle:
    """Test transaction insert, delete, and reinsert scenarios."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Clean up test database before/after each test."""
        # Clean up before
        database.DATABASE_PATH.unlink(missing_ok=True)
        yield
        # Clean up after
        database.DATABASE_PATH.unlink(missing_ok=True)

    def test_delete_account_allows_reupload(self):
        """
        Critical bug fix: After deleting an account, the same transactions
        should be insertable again.

        This test locks in the behavior that delete truly removes transactions
        from the database, allowing re-import of the same CSV file.
        """
        # Initial set of transactions
        transactions = [
            {
                "date": "2024-01-15",
                "description": "Coffee Shop",
                "amount": -4.50,
                "account": "Test Account",
                "category": "Food & drink",
            },
            {
                "date": "2024-01-16",
                "description": "Gas Station",
                "amount": -45.00,
                "account": "Test Account",
                "category": "Automotive",
            },
        ]

        # Insert transactions
        new_count, total_count, inserted_ids = database.insert_transactions(transactions)
        assert new_count == 2, "Should insert 2 new transactions"
        assert total_count == 2, "Should process 2 total transactions"

        # Verify they exist
        with database.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM transactions WHERE account = ?", ("Test Account",)).fetchone()[0]
            assert count == 2, "Should have 2 transactions in database"

        # Delete the account
        result = database.delete_transactions_by_account("Test Account")
        assert result["deleted"] == 2, "Should delete 2 transactions"

        # Verify they're gone
        with database.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM transactions WHERE account = ?", ("Test Account",)).fetchone()[0]
            assert count == 0, "Should have 0 transactions after delete"

        # CRITICAL: Re-insert the same transactions (simulating file re-upload)
        new_count, total_count, inserted_ids = database.insert_transactions(transactions)
        assert new_count == 2, "Should insert 2 new transactions after delete"
        assert total_count == 2, "Should process 2 total transactions"

        # Verify they exist again
        with database.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM transactions WHERE account = ?", ("Test Account",)).fetchone()[0]
            assert count == 2, "Should have 2 transactions after re-upload"

    def test_duplicate_detection_works_normally(self):
        """Verify duplicate detection still works for actual duplicates."""
        transactions = [
            {
                "date": "2024-01-15",
                "description": "Coffee Shop",
                "amount": -4.50,
                "account": "Test Account",
                "category": "Food & drink",
            }
        ]

        # First insert
        new_count, total_count, _ = database.insert_transactions(transactions)
        assert new_count == 1, "Should insert 1 new transaction"

        # Duplicate insert (without deleting)
        new_count, total_count, _ = database.insert_transactions(transactions)
        assert new_count == 0, "Should insert 0 new transactions (duplicate)"
        assert total_count == 1, "Should process 1 transaction"

        # Verify still only one transaction
        with database.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM transactions WHERE account = ?", ("Test Account",)).fetchone()[0]
            assert count == 1, "Should have exactly 1 transaction (no duplicates)"

    def test_overlapping_csv_uploads(self):
        """
        Test the scenario where two CSV files contain some overlapping transactions.
        This reproduces the bug where duplicate transactions are double-counted.
        """
        # First CSV with transactions from Jan 1-15
        csv1_transactions = [
            {
                "date": "2024-01-01",
                "description": "Coffee Shop",
                "amount": -4.50,
                "account": "Test Account",
                "category": "Food & drink",
            },
            {
                "date": "2024-01-05",
                "description": "Gas Station",
                "amount": -45.00,
                "account": "Test Account",
                "category": "Automotive",
            },
            {
                "date": "2024-01-15",
                "description": "Grocery Store",
                "amount": -120.50,
                "account": "Test Account",
                "category": "Groceries",
            },
        ]

        # Second CSV with transactions from Jan 10-20 (overlaps with Jan 15 from first CSV)
        csv2_transactions = [
            {
                "date": "2024-01-10",
                "description": "Restaurant",
                "amount": -35.00,
                "account": "Test Account",
                "category": "Food & drink",
            },
            {
                "date": "2024-01-15",  # DUPLICATE from CSV1
                "description": "Grocery Store",
                "amount": -120.50,
                "account": "Test Account",
                "category": "Groceries",
            },
            {
                "date": "2024-01-20",
                "description": "Pet Store",
                "amount": -50.00,
                "account": "Test Account",
                "category": "Pumpkin",
            },
        ]

        # Upload first CSV
        new_count, total_count, _ = database.insert_transactions(csv1_transactions)
        assert new_count == 3, "Should insert 3 new transactions from first CSV"
        assert total_count == 3, "Should process 3 total transactions"

        # Upload second CSV with overlapping data
        new_count, total_count, _ = database.insert_transactions(csv2_transactions)
        assert new_count == 2, "Should insert only 2 new transactions (excluding duplicate)"
        assert total_count == 3, "Should process 3 transactions from second CSV"

        # Verify total count is correct (no double counting)
        with database.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM transactions WHERE account = ?", ("Test Account",)).fetchone()[0]
            assert count == 5, "Should have exactly 5 unique transactions (3 from CSV1 + 2 new from CSV2)"

            # Verify the duplicate transaction exists only once
            grocery_count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE description = ? AND date = ?",
                ("Grocery Store", "2024-01-15"),
            ).fetchone()[0]
            assert grocery_count == 1, "Grocery Store transaction should exist exactly once"
