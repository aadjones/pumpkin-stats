"""
App structure and tab organization for the Streamlit finance dashboard.

Separates UI logic from core data processing.
"""

from datetime import datetime

import streamlit as st

from . import charts, database, finance_calculations
from .trend_analysis import TrendAnalyzer
from .trend_charts import (
    create_category_trends_chart,
    create_monthly_trends_chart,
    create_top_categories_chart,
)


def render_monthly_transactions_tab():
    """Render the existing monthly transaction analysis tab."""
    st.header("📅 Monthly Transactions")

    # Month selection sidebar content (keep existing logic)
    with st.sidebar:
        st.header("Select Month")

        # Get available months from database
        with database.get_connection() as conn:
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
    spending, income, net, transactions_df, breakdown = finance_calculations.get_household_finances(
        current_year, current_month
    )

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

    # Calculation breakdown for transparency
    _render_calculation_breakdown(breakdown)

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

    # Transaction Management with override controls
    _render_transaction_management(transactions_df, current_year, current_month)

    # Manual override controls
    _render_override_controls(current_year, current_month)

    # Income override controls
    _render_income_override_controls(current_year, current_month)


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

    category_trends = analyzer.get_top_category_trends(months=12, top_n=20)

    if not category_trends.empty:
        # Primary chart: Top categories line chart
        top_n = st.slider("Number of top categories to show", 3, 8, 5)
        category_chart = create_top_categories_chart(category_trends, top_n=top_n)
        st.plotly_chart(category_chart, use_container_width=True)

        # Secondary chart: All categories stacked area (collapsible)
        with st.expander("View Rainbow Mountain 🌈⛰️"):
            st.write("*Shows all categories in a colorful stacked area visualization*")
            stacked_chart = create_category_trends_chart(category_trends)
            st.plotly_chart(stacked_chart, use_container_width=True)

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
                    "Exclude",
                    help="Check to exclude this transaction from income/spending calculations",
                    width=80,
                    default=False,
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
    import pandas as pd

    def _normalize_boolean_value(val):
        """Normalize a single boolean value to handle various data types and edge cases."""
        # Simple approach: convert anything truthy to True, anything falsy to False
        try:
            # Handle None/NaN
            if pd.isna(val):
                return False
            # Convert to bool - this handles int, numpy.int64, bool, etc.
            return bool(val)
        except:
            # If anything fails, default to False
            return False

    if st.button("💾 Save Changes", type="primary"):
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
                        import tempfile

                        temp_path = tempfile.mktemp(suffix=".csv")
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        # Process the file (pass original filename for account naming)
                        try:
                            transactions = data_ingestion.process_csv_file(Path(temp_path), uploaded_file.name)

                            if transactions:
                                # Insert transactions into database using the proper function
                                new_count = database.insert_transactions(transactions)
                                total_new_transactions += new_count
                                st.success(
                                    f"✅ Processed {uploaded_file.name}: {new_count} new transactions ({len(transactions)} total)"
                                )
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


def _render_calculation_breakdown(breakdown):
    """Render the calculation breakdown for transparency."""
    if not breakdown.get("auto_excluded") and not breakdown.get("manual_overrides"):
        return

    with st.expander("🔍 How we calculated your spending", expanded=False):
        st.write("**Calculation Transparency**")

        # Auto-excluded transactions
        if breakdown.get("auto_excluded"):
            st.write("**Automatically excluded from budget:**")
            for reason, data in breakdown["auto_excluded"].items():
                reason_label = {
                    "credit_card_payment": "Credit card payments",
                    "account_transfer": "Account transfers",
                    "payment": "Other payments",
                }.get(reason, reason.replace("_", " ").title())

                st.write(f"• {reason_label}: {data['count']} transactions (${data['total']:,.2f})")

        # Manual overrides
        if breakdown.get("manual_overrides"):
            st.write("**Manual overrides:**")
            for override_type, data in breakdown["manual_overrides"].items():
                action = "Manually included" if override_type == "include" else "Manually excluded"
                st.write(f"• {action}: {data['count']} transactions (${data['total']:,.2f})")

        # Income filtering explanation
        st.write("**Income calculation:**")
        st.write(
            "We use a conservative approach to income - only counting transactions that clearly represent actual income:"
        )
        st.write("• Payroll deposits (PAYROLL, DIRECT DEP)")
        st.write("• Cashback and refunds")
        st.write("• Small credit card credits (likely cashback)")
        st.write("• Work reimbursements, bonuses, interest")
        st.info(
            "💡 This excludes transfers between accounts, Zelle/Venmo that might be shared expenses, and other unclear positive amounts."
        )

        # Final totals summary
        st.write("**Final calculation:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Spending", f"${breakdown['final_totals']['spending']:,.2f}")
        with col2:
            st.metric("Income", f"${breakdown['final_totals']['income']:,.2f}")
        with col3:
            st.metric("Net", f"${breakdown['final_totals']['net']:,.2f}")


def _render_override_controls(current_year, current_month):
    """Render manual override controls for transactions."""
    from .transaction_overrides import TransactionOverrideManager

    override_manager = TransactionOverrideManager()
    auto_excluded, auto_included = override_manager.get_override_candidates(current_year, current_month)

    st.subheader("Override Automatic Decisions")
    st.write("Review and adjust transactions that were automatically included or excluded from your budget.")

    # Auto-excluded transactions that could be included
    if not auto_excluded.empty:
        with st.expander(f"📋 Auto-excluded transactions ({len(auto_excluded)} items)", expanded=False):
            st.write(
                "These transactions were automatically excluded from budget calculations. Click 'Include' if any should count as spending."
            )

            for _, txn in auto_excluded.iterrows():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    reason_label = {
                        "credit_card_payment": "Credit card payment",
                        "account_transfer": "Account transfer",
                        "payment": "Payment",
                    }.get(txn["auto_exclude_reason"], txn["auto_exclude_reason"])

                    st.write(f"**{txn['description']}**")
                    st.write(f"${txn['amount']:,.2f} • {reason_label} • {txn['account']}")

                with col2:
                    st.write(f"${abs(txn['amount']):,.2f}")

                with col3:
                    include_key = f"include_{txn['id']}"
                    if st.button(
                        "Include in budget", key=include_key, help="Include this transaction in spending calculations"
                    ):
                        success = override_manager.apply_manual_override(
                            txn["id"], "include", "User manually included", "spending"
                        )
                        if success:
                            st.success("✅ Transaction included in budget")
                            st.rerun()
                        else:
                            st.error("❌ Failed to update transaction")

                with col4:
                    st.write(f"*{txn['category']}*")

    # Auto-included transactions that could be excluded
    if not auto_included.empty:
        # Show only spending transactions (negative amounts) for manual exclusion
        spending_transactions = auto_included[auto_included["amount"] < 0]

        if not spending_transactions.empty:
            with st.expander(f"💰 Included spending transactions ({len(spending_transactions)} items)", expanded=False):
                st.write(
                    "These transactions are currently included in your spending. Click 'Exclude' if any should not count as spending."
                )

                # Pagination for large lists
                page_size = 10
                total_pages = (len(spending_transactions) + page_size - 1) // page_size

                if total_pages > 1:
                    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1) - 1
                    start_idx = page * page_size
                    end_idx = start_idx + page_size
                    display_transactions = spending_transactions.iloc[start_idx:end_idx]
                else:
                    display_transactions = spending_transactions

                for _, txn in display_transactions.iterrows():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                    with col1:
                        st.write(f"**{txn['description']}**")
                        st.write(f"${txn['amount']:,.2f} • {txn['account']}")

                    with col2:
                        st.write(f"${abs(txn['amount']):,.2f}")

                    with col3:
                        exclude_key = f"exclude_{txn['id']}"
                        if st.button(
                            "Exclude from budget",
                            key=exclude_key,
                            help="Exclude this transaction from spending calculations",
                        ):
                            success = override_manager.apply_manual_override(
                                txn["id"], "exclude", "User manually excluded", "spending"
                            )
                            if success:
                                st.success("✅ Transaction excluded from budget")
                                st.rerun()
                            else:
                                st.error("❌ Failed to update transaction")

                    with col4:
                        st.write(f"*{txn['category']}*")


def _render_income_override_controls(current_year, current_month):
    """Render income override controls for transactions."""
    from .transaction_overrides import TransactionOverrideManager

    override_manager = TransactionOverrideManager()
    pending_income_overrides = override_manager.get_pending_income_overrides(current_year, current_month)

    if not pending_income_overrides.empty:
        st.subheader("Income Classification Review")
        st.write(
            "These positive amounts were not automatically counted as income. Review them and mark any that should count as income."
        )

        with st.expander(f"💰 Potential income not counted ({len(pending_income_overrides)} items)", expanded=False):
            st.write(
                "**We use a conservative approach to income** - only counting clear income patterns like payroll, cashback, etc."
            )
            st.write(
                "If you see legitimate income below that we missed, click 'Mark as Income' to include it in your totals."
            )

            # Pagination for large lists
            page_size = 10
            total_pages = (len(pending_income_overrides) + page_size - 1) // page_size

            if total_pages > 1:
                page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="income_page") - 1
                start_idx = page * page_size
                end_idx = start_idx + page_size
                display_transactions = pending_income_overrides.iloc[start_idx:end_idx]
                st.write(
                    f"Showing {start_idx + 1}-{min(end_idx, len(pending_income_overrides))} of {len(pending_income_overrides)}"
                )
            else:
                display_transactions = pending_income_overrides

            for _, txn in display_transactions.iterrows():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    st.write(f"**{txn['description']}**")
                    st.write(f"${txn['amount']:,.2f} • {txn['account']}")

                with col2:
                    st.write(f"${txn['amount']:,.2f}")

                with col3:
                    mark_income_key = f"mark_income_{txn['id']}"
                    if st.button(
                        "Mark as Income", key=mark_income_key, help="Include this transaction in income calculations"
                    ):
                        success = override_manager.apply_manual_override(
                            txn["id"], "include", "User marked as legitimate income", "income"
                        )
                        if success:
                            st.success("✅ Transaction marked as income")
                            st.rerun()
                        else:
                            st.error("❌ Failed to update transaction")

                with col4:
                    st.write(f"*{txn['category']}*")

                st.divider()
    else:
        # Show a collapsed section even when there are no overrides
        with st.expander("💰 Income Classification Review", expanded=False):
            st.info("✅ All positive amounts have been properly classified. No income overrides needed this month.")
