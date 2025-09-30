from typing import Dict, List, Optional, Tuple

import pandas as pd

from . import constants
from .database import get_connection


class TransactionOverrideManager:
    """Handles all transaction override logic and state management."""

    def get_effective_transactions(self, year: int, month: int) -> pd.DataFrame:
        """Returns transactions with auto-exclusions + manual overrides applied."""
        with get_connection() as conn:
            query = """
                SELECT *,
                    CASE
                        WHEN manual_override_type = 'include' THEN 0
                        WHEN manual_override_type = 'exclude' THEN 1
                        WHEN auto_exclude_reason IS NOT NULL THEN 1
                        ELSE exclude_from_budget
                    END as effective_exclude
                FROM transactions
                WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
                ORDER BY date DESC, amount DESC
            """
            df = pd.read_sql_query(query, conn, params=(str(year), f"{month:02d}"))
        return df

    def get_budget_transactions(self, year: int, month: int) -> pd.DataFrame:
        """Returns only transactions that should be included in budget calculations."""
        df = self.get_effective_transactions(year, month)
        return df[df["effective_exclude"] == 0]

    def get_excluded_transactions(self, year: int, month: int) -> pd.DataFrame:
        """Returns only transactions that are excluded from budget calculations."""
        df = self.get_effective_transactions(year, month)
        return df[df["effective_exclude"] == 1]

    def get_calculation_breakdown(self, year: int, month: int) -> Dict:
        """Returns detailed breakdown for user transparency."""
        with get_connection() as conn:
            # Get auto-excluded transactions by reason
            auto_excluded_query = """
                SELECT auto_exclude_reason, COUNT(*) as count, SUM(ABS(amount)) as total
                FROM transactions
                WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
                AND auto_exclude_reason IS NOT NULL
                AND manual_override_type IS NULL
                GROUP BY auto_exclude_reason
            """
            auto_excluded = pd.read_sql_query(auto_excluded_query, conn, params=(str(year), f"{month:02d}"))

            # Get manual overrides
            manual_overrides_query = """
                SELECT manual_override_type, COUNT(*) as count, SUM(ABS(amount)) as total
                FROM transactions
                WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
                AND manual_override_type IS NOT NULL
                GROUP BY manual_override_type
            """
            manual_overrides = pd.read_sql_query(manual_overrides_query, conn, params=(str(year), f"{month:02d}"))

            # Get final totals using same logic as finance calculations
            budget_transactions = self.get_budget_transactions(year, month)
            spending = budget_transactions[budget_transactions["amount"] < 0]["amount"].sum()

            # Use filtered income logic (whitelist + manual inclusions)
            income_transactions = self.get_filtered_income_transactions(year, month)
            income = income_transactions["amount"].sum() if not income_transactions.empty else 0.0

        # Format auto-excluded breakdown
        auto_excluded_dict = {}
        for _, row in auto_excluded.iterrows():
            auto_excluded_dict[row["auto_exclude_reason"]] = {"count": int(row["count"]), "total": float(row["total"])}

        # Format manual overrides breakdown
        manual_overrides_dict = {}
        for _, row in manual_overrides.iterrows():
            manual_overrides_dict[row["manual_override_type"]] = {
                "count": int(row["count"]),
                "total": float(row["total"]),
            }

        return {
            "auto_excluded": auto_excluded_dict,
            "manual_overrides": manual_overrides_dict,
            "final_totals": {"spending": abs(spending), "income": income, "net": income + spending},
        }

    def apply_manual_override(
        self, transaction_id: str, override_type: str, reason: str = "", override_category: str = "spending"
    ) -> bool:
        """Apply manual override (include/exclude) with reason and category."""
        if override_type not in ["include", "exclude"]:
            raise ValueError("override_type must be 'include' or 'exclude'")
        if override_category not in ["spending", "income"]:
            raise ValueError("override_category must be 'spending' or 'income'")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE transactions
                SET manual_override_type = ?, override_reason = ?, override_category = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (override_type, reason, override_category, transaction_id),
            )
            success = cursor.rowcount > 0
        return success

    def remove_manual_override(self, transaction_id: str) -> bool:
        """Remove manual override, reverting to auto-categorization."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE transactions
                SET manual_override_type = NULL, override_reason = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (transaction_id,),
            )
            success = cursor.rowcount > 0
        return success

    def get_override_candidates(self, year: int, month: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Returns auto-excluded and auto-included transactions that could be overridden."""
        with get_connection() as conn:
            # Auto-excluded items that could be manually included
            auto_excluded_query = """
                SELECT * FROM transactions
                WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
                AND auto_exclude_reason IS NOT NULL
                AND manual_override_type IS NULL
                ORDER BY date DESC
            """
            auto_excluded = pd.read_sql_query(auto_excluded_query, conn, params=(str(year), f"{month:02d}"))

            # Auto-included items that could be manually excluded
            auto_included_query = """
                SELECT * FROM transactions
                WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
                AND auto_exclude_reason IS NULL
                AND manual_override_type IS NULL
                AND exclude_from_budget = 0
                ORDER BY date DESC
            """
            auto_included = pd.read_sql_query(auto_included_query, conn, params=(str(year), f"{month:02d}"))

        return auto_excluded, auto_included

    def _apply_income_whitelist(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Apply income whitelist patterns to positive transactions."""
        if transactions.empty:
            return transactions

        positive_transactions = transactions[transactions["amount"] > 0].copy()
        if positive_transactions.empty:
            return positive_transactions

        # Filter to only include clear income patterns (from constants)
        legitimate_income = positive_transactions[
            positive_transactions["description"]
            .str.upper()
            .str.contains("|".join(constants.INCOME_PATTERNS), regex=True, na=False)
        ]

        # Also include small positive amounts from credit cards (likely cashback/refunds)
        credit_card_income = positive_transactions[
            (positive_transactions["account"].str.contains("Credit", case=False))
            & (positive_transactions["amount"] < constants.CREDIT_CARD_INCOME_THRESHOLD)
        ]

        # Combine legitimate income sources
        if not legitimate_income.empty and not credit_card_income.empty:
            all_income = pd.concat([legitimate_income, credit_card_income]).drop_duplicates()
        elif not legitimate_income.empty:
            all_income = legitimate_income
        elif not credit_card_income.empty:
            all_income = credit_card_income
        else:
            all_income = pd.DataFrame()

        return all_income

    def get_filtered_income_transactions(self, year: int, month: int) -> pd.DataFrame:
        """Get transactions that should count as income (whitelist + manual inclusions)."""
        budget_transactions = self.get_budget_transactions(year, month)
        positive_transactions = budget_transactions[budget_transactions["amount"] > 0]

        if positive_transactions.empty:
            return positive_transactions

        # Apply whitelist first
        whitelist_income = self._apply_income_whitelist(positive_transactions)

        # Add manual income inclusions
        manual_income = positive_transactions[
            (positive_transactions["override_category"] == "income")
            & (positive_transactions["manual_override_type"] == "include")
        ]

        # Combine and deduplicate
        if not whitelist_income.empty and not manual_income.empty:
            all_income = pd.concat([whitelist_income, manual_income]).drop_duplicates()
        elif not whitelist_income.empty:
            all_income = whitelist_income
        elif not manual_income.empty:
            all_income = manual_income
        else:
            all_income = pd.DataFrame()

        return all_income

    def get_pending_income_overrides(self, year: int, month: int) -> pd.DataFrame:
        """Get positive transactions that were excluded by income whitelist and could be marked as income."""
        budget_transactions = self.get_budget_transactions(year, month)
        positive_transactions = budget_transactions[budget_transactions["amount"] > 0]

        if positive_transactions.empty:
            return positive_transactions

        # Get transactions that passed whitelist
        whitelist_income = self._apply_income_whitelist(positive_transactions)
        whitelist_ids = set(whitelist_income["id"]) if not whitelist_income.empty else set()

        # Get transactions already manually marked as income
        manual_income = positive_transactions[
            (positive_transactions["override_category"] == "income")
            & (positive_transactions["manual_override_type"] == "include")
        ]
        manual_income_ids = set(manual_income["id"]) if not manual_income.empty else set()

        # Return positive amounts that weren't included by either method
        excluded_ids = whitelist_ids | manual_income_ids
        pending_overrides = positive_transactions[~positive_transactions["id"].isin(excluded_ids)]

        return pending_overrides.sort_values(["date", "amount"], ascending=[False, False])

    def get_transactions_with_status(self, year: int, month: int) -> pd.DataFrame:
        """Get all transactions with computed status badges and action buttons."""
        all_transactions = self.get_effective_transactions(year, month)

        if all_transactions.empty:
            return all_transactions

        # Get income IDs for status determination
        income_transactions = self.get_filtered_income_transactions(year, month)
        income_ids = set(income_transactions["id"]) if not income_transactions.empty else set()

        # Compute status for each transaction
        statuses = []
        status_badges = []
        status_reasons = []
        available_actions = []

        for _, row in all_transactions.iterrows():
            is_positive = row["amount"] > 0
            is_excluded = row["effective_exclude"] == 1
            manual_override = row["manual_override_type"]
            auto_exclude = row["auto_exclude_reason"]
            is_income = row["id"] in income_ids

            # Determine status
            if manual_override == "exclude":
                status = "manually_excluded"
                badge = "❌ Manually excluded"
                reason = row.get("override_reason", "")
                actions = ["undo"]
            elif manual_override == "include" and row.get("override_category") == "income":
                status = "marked_income"
                badge = "💰 Marked as income"
                reason = ""
                actions = ["undo"]
            elif manual_override == "include":
                status = "manually_included"
                badge = "✓ Manually included"
                reason = ""
                actions = ["exclude"]
            elif is_excluded and auto_exclude:
                status = "auto_excluded"
                # Format reason nicely
                reason_map = {
                    "credit_card_payment": "Credit card payment",
                    "account_transfer": "Account transfer",
                    "payment": "Payment",
                }
                reason = reason_map.get(auto_exclude, auto_exclude.replace("_", " ").title())
                badge = f"🚫 Auto-excluded: {reason}"
                actions = ["include"]
            elif is_positive and is_income:
                status = "counted_income"
                badge = "✓ Counted as income"
                reason = ""
                actions = ["exclude"]
            elif is_positive and not is_income:
                status = "not_counted_income"
                badge = "⚠️ Not counted: Not clear income"
                reason = ""
                actions = ["mark_income"]
            else:
                # Regular spending transaction
                status = "in_budget"
                badge = "✓ In Budget"
                reason = ""
                actions = ["exclude"]

            statuses.append(status)
            status_badges.append(badge)
            status_reasons.append(reason)
            available_actions.append(",".join(actions))

        # Add computed columns
        all_transactions = all_transactions.copy()
        all_transactions["status"] = statuses
        all_transactions["status_badge"] = status_badges
        all_transactions["status_reason"] = status_reasons
        all_transactions["available_actions"] = available_actions

        return all_transactions
