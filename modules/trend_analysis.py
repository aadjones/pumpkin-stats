"""
Time-series analysis for financial data.

Handles all trend analysis calculations separate from core finance calculations.
"""

from typing import Dict, Tuple

import pandas as pd

from . import database


class TrendAnalyzer:
    """Handles all time-series analysis for financial data."""

    def get_monthly_trends(self, months: int = 12) -> pd.DataFrame:
        """Get monthly spending, income, and net trends over the last N months."""
        conn = database.get_connection()

        # Get monthly summaries for the last N months
        query = f"""
            SELECT
                strftime('%Y', date) as year,
                strftime('%m', date) as month,
                CASE
                    WHEN amount < 0 AND category NOT IN ('Transfers', 'Credit Card Payment')
                         AND COALESCE(exclude_from_budget, 0) = 0
                    THEN abs(amount)
                    ELSE 0
                END as spending,
                CASE
                    WHEN amount > 0 AND category NOT IN ('Transfers', 'Credit Card Payment')
                         AND COALESCE(exclude_from_budget, 0) = 0
                         AND (
                             UPPER(description) LIKE '%PAYROLL%' OR
                             UPPER(description) LIKE '%DIRECT DEP%' OR
                             UPPER(description) LIKE '%DIRECTDEP%' OR
                             UPPER(description) LIKE '%REIMBURS%' OR
                             UPPER(description) LIKE '%REFUND%' OR
                             UPPER(description) LIKE '%CASHBACK%' OR
                             UPPER(description) LIKE '%CASH BACK%' OR
                             UPPER(description) LIKE '%GIFT%' OR
                             UPPER(description) LIKE '%BONUS%' OR
                             UPPER(description) LIKE '%INTEREST%' OR
                             (UPPER(account) LIKE '%CREDIT%' AND amount < 100)
                         )
                    THEN amount
                    ELSE 0
                END as income
            FROM transactions
            WHERE date >= date('now', '-{months} months')
            ORDER BY year DESC, month DESC
        """

        results = conn.execute(query).fetchall()
        conn.close()

        if not results:
            return pd.DataFrame()

        # Convert to DataFrame and group by month
        df = pd.DataFrame(results, columns=["year", "month", "spending", "income"])

        monthly_summary = df.groupby(["year", "month"]).agg({"spending": "sum", "income": "sum"}).reset_index()

        # Create date column and calculate net
        monthly_summary["date"] = pd.to_datetime(monthly_summary[["year", "month"]].assign(day=1))
        monthly_summary["net"] = monthly_summary["income"] - monthly_summary["spending"]
        monthly_summary["month_name"] = monthly_summary["date"].dt.strftime("%b %Y")

        # Sort by date ascending for better trend visualization
        return monthly_summary.sort_values("date")

    def get_top_category_trends(self, months: int = 12, top_n: int = 5) -> pd.DataFrame:
        """Get spending trends for top N spending categories over the last N months."""
        conn = database.get_connection()

        # First, get the top spending categories overall
        top_categories_query = f"""
            SELECT category, SUM(abs(amount)) as total_spending
            FROM transactions
            WHERE date >= date('now', '-{months} months')
            AND amount < 0
            AND category NOT IN ('Transfers', 'Credit Card Payment')
            AND COALESCE(exclude_from_budget, 0) = 0
            GROUP BY category
            ORDER BY total_spending DESC
            LIMIT {top_n}
        """

        top_categories_result = conn.execute(top_categories_query).fetchall()
        if not top_categories_result:
            conn.close()
            return pd.DataFrame()

        top_categories = [row[0] for row in top_categories_result]
        category_list = "'" + "', '".join(top_categories) + "'"

        # Now get monthly trends for these categories
        trends_query = f"""
            SELECT
                strftime('%Y-%m', date) as month_key,
                strftime('%Y', date) as year,
                strftime('%m', date) as month,
                category,
                SUM(CASE WHEN amount < 0 THEN abs(amount) ELSE 0 END) as spending
            FROM transactions
            WHERE date >= date('now', '-{months} months')
            AND category IN ({category_list})
            AND COALESCE(exclude_from_budget, 0) = 0
            AND amount < 0
            GROUP BY strftime('%Y-%m', date), category
            ORDER BY year ASC, month ASC, spending DESC
        """

        results = conn.execute(trends_query).fetchall()
        conn.close()

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results, columns=["month_key", "year", "month", "category", "spending"])

        # Create proper date for sorting
        df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
        df["month_name"] = df["date"].dt.strftime("%b %Y")

        return df.sort_values("date")

    def calculate_trend_metrics(self, trend_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate basic trend direction and volatility metrics."""
        if trend_df.empty or len(trend_df) < 2:
            return {}

        metrics = {}

        # Calculate trends for spending, income, net
        for col in ["spending", "income", "net"]:
            if col in trend_df.columns:
                values = trend_df[col].values

                # Simple trend direction (% change from first to last month)
                if len(values) >= 2 and values[0] != 0:
                    trend_pct = ((values[-1] - values[0]) / abs(values[0])) * 100
                    metrics[f"{col}_trend_pct"] = trend_pct

                # Volatility (coefficient of variation)
                if values.std() != 0 and values.mean() != 0:
                    cv = (values.std() / abs(values.mean())) * 100
                    metrics[f"{col}_volatility"] = cv

                # Average monthly value
                metrics[f"{col}_avg"] = values.mean()

        return metrics
