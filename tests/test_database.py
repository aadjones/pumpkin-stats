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
