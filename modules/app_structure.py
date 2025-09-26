"""
App structure and tab organization for the Streamlit finance dashboard.

Separates UI logic from core data processing.
"""

from datetime import datetime

import streamlit as st

from . import charts, database, finance_calculations
from .trend_analysis import TrendAnalyzer
from .trend_charts import create_category_trends_chart, create_monthly_trends_chart


def render_monthly_transactions_tab():
    """Render the existing monthly transaction analysis tab."""
    st.header("📅 Monthly Transactions")

    # Month selection sidebar content (keep existing logic)
    with st.sidebar:
        st.header("Select Month")

        # Get available months from database
        conn = database.get_connection()
        available_months = conn.execute(
            """
            SELECT DISTINCT
                strftime('%Y', date) as year,
                strftime('%m', date) as month,
                COUNT(*) as count
            FROM transactions
            GROUP BY strftime('%Y', date), strftime('%m', date)
            ORDER BY year DESC, month DESC
        """
        ).fetchall()
        conn.close()

        if not available_months:
            st.info("Upload CSV files above to get started")
            st.stop()

        # Create month options as simple strings
        month_options = []
        for year, month, count in available_months:
            date_obj = datetime(int(year), int(month), 1)
            display_name = f"{date_obj.strftime('%B %Y')} ({count} transactions)"
            month_options.append((display_name, int(year), int(month)))

        # Get display names for selectbox
        display_names = [option[0] for option in month_options]

        selected_index = st.selectbox(
            "Choose month:", options=range(len(display_names)), format_func=lambda x: display_names[x]
        )

        current_year = month_options[selected_index][1]
        current_month = month_options[selected_index][2]

    # Monthly analysis content
    st.markdown(f"### {datetime(current_year, current_month, 1).strftime('%B %Y')}")

    # Get household finances using proper accounting principles
    spending, income, net, transactions_df = finance_calculations.get_household_finances(current_year, current_month)

    if transactions_df.empty:
        st.warning("No transactions found for this month")
        st.stop()

    # Display key metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Spending", f"${spending:,.2f}")

    with col2:
        st.metric("Total Income", f"${income:,.2f}")

    with col3:
        # Show net with appropriate coloring: green for positive, red for negative
        net_color = "🟢" if net >= 0 else "🔴"
        st.metric("Net", f"{net_color} ${net:,.2f}")

    # Category breakdown
    st.subheader("Spending by Category")
    category_df = finance_calculations.get_spending_by_category(current_year, current_month)

    if not category_df.empty:
        # Create two columns - one for pie chart, one for the detailed list
        col1, col2 = st.columns([2, 1])

        with col1:
            # Create and display pie chart
            fig = charts.pie_chart(category_df, names_col="category", values_col="total_spent", title="")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.write("**Category Details:**")
            for _, row in category_df.iterrows():
                st.write(f"**{row['category']}:** ${row['total_spent']:,.2f}")
    else:
        st.info("No spending categories found")

    # Transaction Management (existing logic from app.py)
    _render_transaction_management(transactions_df, current_year, current_month)


def render_trend_analysis_tab():
    """Render the new 12-month trend analysis tab."""
    st.header("📈 12-Month Trends")

    # Create trend analyzer
    analyzer = TrendAnalyzer()

    # Get trend data
    monthly_trends = analyzer.get_monthly_trends(months=12)

    if monthly_trends.empty:
        st.info("Need at least 2 months of transaction data to show trends")
        st.stop()

    # Monthly trends chart
    st.subheader("Financial Trends Over Time")
    trends_chart = create_monthly_trends_chart(monthly_trends)
    st.plotly_chart(trends_chart, use_container_width=True)

    # Category trends
    st.subheader("Category Spending Trends")
    category_trends = analyzer.get_top_category_trends(months=12, top_n=20)  # Show more categories (increased from 5)

    if not category_trends.empty:
        category_chart = create_category_trends_chart(category_trends)
        st.plotly_chart(category_chart, use_container_width=True)

        # Show category trend table
        with st.expander("View Category Trend Details"):
            # Pivot for easier reading
            pivot_df = category_trends.pivot(index="month_name", columns="category", values="spending").fillna(0)
            st.dataframe(pivot_df.style.format("${:,.2f}"))
    else:
        st.info("Not enough category data to show trends")


def _render_transaction_management(transactions_df, current_year, current_month):
    """Helper function to render the transaction management section."""
    st.subheader("Transaction Management")

    # Make transaction editing primary - no expander needed
    st.write("📝 **Review & Edit Transactions**")
    st.write("**Click on any transaction to edit its category or exclude it from budget calculations**")

    # Show all transactions for the month with edit controls
    if not transactions_df.empty:
        # Sort by date descending, amount descending for better UX
        display_transactions = transactions_df.sort_values(["date", "amount"], ascending=[False, True])

        st.write(
            f"**{len(display_transactions)} transactions found for {datetime(current_year, current_month, 1).strftime('%B %Y')}**"
        )

        # Create editable dataframe
        edited_df = st.data_editor(
            display_transactions[
                ["date", "description", "amount", "account", "category", "exclude_from_budget", "manual_notes"]
            ],
            column_config={
                "date": st.column_config.DateColumn("Date", width="small", disabled=True),
                "description": st.column_config.TextColumn("Description", width="large", disabled=True),
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f", width="small", disabled=True),
                "account": st.column_config.TextColumn("Account", width="medium", disabled=True),
                "category": st.column_config.SelectboxColumn(
                    "Category", options=database.get_categories(), width="medium"
                ),
                "exclude_from_budget": st.column_config.CheckboxColumn(
                    "Exclude from Budget",
                    help="Check to exclude this transaction from income/spending calculations",
                    width="small",
                ),
                "manual_notes": st.column_config.TextColumn(
                    "Notes", help="Add notes about why you changed this transaction", width="medium"
                ),
            },
            hide_index=True,
            width="stretch",
            key="transaction_editor",
        )

        # Save changes button (existing logic from app.py)
        _handle_transaction_saves(edited_df, display_transactions)


def _handle_transaction_saves(edited_df, display_transactions):
    """Helper to handle saving transaction changes."""

    def _normalize_boolean_value(val):
        """Normalize a single boolean value to handle various data types and edge cases."""
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

    if st.button("💾 Save Changes", type="primary"):
        import pandas as pd

        changes_made = 0

        # Compare original vs edited data
        for idx, (_, original_row) in enumerate(display_transactions.iterrows()):
            edited_row = edited_df.iloc[idx]
            transaction_id = original_row["id"]  # Get ID from original data since we removed it from editor

            # Check what changed with robust boolean handling
            category_changed = original_row["category"] != edited_row["category"]

            # Normalize boolean values for comparison
            original_exclude = _normalize_boolean_value(original_row.get("exclude_from_budget", False))
            edited_exclude = _normalize_boolean_value(edited_row["exclude_from_budget"])
            exclude_changed = original_exclude != edited_exclude

            notes_changed = original_row.get("manual_notes", "") != edited_row["manual_notes"]

            if category_changed or exclude_changed or notes_changed:
                success = database.update_transaction_override(
                    transaction_id,
                    exclude_from_budget=edited_exclude,
                    manual_notes=edited_row["manual_notes"],
                    new_category=str(edited_row["category"]) if category_changed else None,
                )
                if success:
                    changes_made += 1

        if changes_made > 0:
            st.success(f"✅ Updated {changes_made} transactions")
            st.rerun()
        else:
            st.info("No changes detected")


def render_main_app_tabs():
    """Organize and render the main app tab structure."""
    # File upload sidebar (keep at top level)
    _render_file_upload_sidebar()

    # Main content tabs
    tab1, tab2 = st.tabs(["Monthly Detail", "12-Month Trends"])

    with tab1:
        render_monthly_transactions_tab()

    with tab2:
        render_trend_analysis_tab()


def _render_file_upload_sidebar():
    """Render the file upload sidebar (existing logic from app.py)."""
    with st.sidebar:
        st.header("📁 Upload New Data")

        uploaded_files = st.file_uploader(
            "Upload CSV files to add new transactions",
            type=["csv"],
            accept_multiple_files=True,
            help="Upload bank or credit card CSV files. Files are processed automatically.",
        )

        if uploaded_files:
            import os
            from pathlib import Path

            from modules import data_ingestion

            # Use session state to track processed files and prevent infinite loop
            if "processed_files" not in st.session_state:
                st.session_state.processed_files = set()

            # Get file signatures to track what's been processed
            current_files = {(f.name, len(f.getvalue())) for f in uploaded_files}

            # Only process files we haven't seen before
            new_files = [
                f for f in uploaded_files if (f.name, len(f.getvalue())) not in st.session_state.processed_files
            ]

            if new_files:
                with st.spinner("Processing uploaded files..."):
                    total_new_transactions = 0

                    for uploaded_file in new_files:
                        # Save uploaded file temporarily
                        temp_path = f"/tmp/{uploaded_file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        # Process the file
                        try:
                            transactions = data_ingestion.process_csv_file(Path(temp_path))

                            if transactions:
                                # Insert transactions into database
                                conn = database.get_connection()
                                for txn in transactions:
                                    conn.execute(
                                        """
                                        INSERT OR IGNORE INTO transactions
                                        (date, description, amount, account, category, raw_description)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                        (
                                            txn["date"],
                                            txn["description"],
                                            txn["amount"],
                                            txn["account"],
                                            txn["category"],
                                            txn["raw_description"],
                                        ),
                                    )
                                conn.commit()
                                conn.close()

                                total_new_transactions += len(transactions)
                                st.success(f"✅ Processed {uploaded_file.name}: {len(transactions)} transactions")
                            else:
                                st.warning(f"⚠️ No valid transactions found in {uploaded_file.name}")

                        except Exception as e:
                            st.error(f"❌ Error processing {uploaded_file.name}: {str(e)}")

                        # Clean up temp file
                        try:
                            os.remove(temp_path)
                        except:
                            pass

                        # Mark this file as processed
                        st.session_state.processed_files.add((uploaded_file.name, len(uploaded_file.getvalue())))

                    if total_new_transactions > 0:
                        st.success(f"🎉 Successfully added {total_new_transactions} new transactions!")
                        st.info("🔄 Refreshing page to show new data...")
                        st.rerun()

        st.divider()
