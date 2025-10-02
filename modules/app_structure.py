"""
App structure and tab organization for the Streamlit finance dashboard.

Separates UI logic from core data processing.
"""

from datetime import datetime

import streamlit as st

from . import charts, database, feature_flags, finance_calculations
from .pumpkin_quotes import (
    EMPTY_STATES,
    ERROR_MESSAGES,
    LOADING_MESSAGES,
    SUCCESS_MESSAGES,
)
from .transaction_overrides import TransactionOverrideManager
from .trend_analysis import TrendAnalyzer
from .trend_charts import (
    create_category_trends_chart,
    create_monthly_trends_chart,
    create_top_categories_chart,
)


def render_monthly_transactions_tab():
    """Render the existing monthly transaction analysis tab."""
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
        st.info(EMPTY_STATES["no_data"])
        st.stop()

    # Create month options
    month_options = []
    for year, month, count in available_months:
        date_obj = datetime(int(year), int(month), 1)
        display_name = f"{date_obj.strftime('%B %Y')} ({count} transactions)"
        month_options.append((display_name, int(year), int(month)))

    # Get display names for selectbox
    display_names = [option[0] for option in month_options]

    # Initialize default selection from session state or use first month
    default_index = 0
    if "current_year" in st.session_state and "current_month" in st.session_state:
        for idx, (_, year, month) in enumerate(month_options):
            if year == st.session_state.current_year and month == st.session_state.current_month:
                default_index = idx
                break

    # Prominent month selector
    st.markdown("### 📅 Select Month")
    selected_index = st.selectbox(
        "Select month:",
        options=range(len(display_names)),
        format_func=lambda x: display_names[x],
        index=default_index,
        key="monthly_detail_month",
        label_visibility="collapsed",
    )
    st.markdown("---")

    # Get selected month
    current_year = month_options[selected_index][1]
    current_month = month_options[selected_index][2]

    # Store in session state for consistency
    st.session_state.current_year = current_year
    st.session_state.current_month = current_month

    # Get household finances using proper accounting principles
    spending, income, net, transactions_df, breakdown = finance_calculations.get_household_finances(
        current_year, current_month
    )

    if transactions_df.empty:
        st.info(EMPTY_STATES["no_transactions"])
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

    # Unified Transaction Management
    _render_unified_transaction_table(current_year, current_month)


def render_trend_analysis_tab():
    """Render trend analysis tab with optional time range selection."""
    st.header("📈 Trends")

    # Create trend analyzer
    analyzer = TrendAnalyzer()

    # Time range selector (if feature flag enabled)
    if feature_flags.is_enabled("time_range_selector"):
        time_range = st.radio(
            "Show last:",
            options=[3, 6, 12],
            format_func=lambda x: f"{x} months",
            horizontal=True,
            index=2,  # Default to 12 months
            key="trend_timerange",
        )
    else:
        time_range = 12  # Default to 12 if feature disabled

    # Get trend data
    monthly_trends = analyzer.get_monthly_trends(months=time_range)

    if monthly_trends.empty:
        st.info(EMPTY_STATES["no_trends"])
        st.stop()

    # Monthly trends chart
    st.subheader("Financial Trends Over Time")
    trends_chart = create_monthly_trends_chart(monthly_trends)
    st.plotly_chart(trends_chart, use_container_width=True)

    # Category trends
    st.subheader("Category Spending Trends")

    category_trends = analyzer.get_top_category_trends(months=time_range, top_n=20)

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


def _render_unified_transaction_table(current_year, current_month):
    """Render the unified transaction table with status badges and inline actions."""
    st.subheader("Transaction Management")

    # Get transactions with status
    override_manager = TransactionOverrideManager()
    transactions_df = override_manager.get_transactions_with_status(current_year, current_month)

    if transactions_df.empty:
        st.info("No transactions found for this month")
        return

    # Calculate filter counts
    spend_count = len(transactions_df[(transactions_df["effective_exclude"] == 0) & (transactions_df["amount"] < 0)])

    # Income = positive amounts that ARE counted as income
    income_transactions = override_manager.get_filtered_income_transactions(current_year, current_month)
    income_ids = set(income_transactions["id"]) if not income_transactions.empty else set()
    income_count = len(transactions_df[transactions_df["id"].isin(income_ids)])

    # Excluded = auto-excluded + manually excluded + positive amounts NOT counted as income
    excluded_count = len(
        transactions_df[
            (transactions_df["effective_exclude"] == 1)
            | ((transactions_df["amount"] > 0) & (~transactions_df["id"].isin(income_ids)))
        ]
    )

    total_count = len(transactions_df)

    # Initialize the filter selection in session state if not present
    # This ensures "Spend" is the default on first load, but preserves selection on reruns
    if "transaction_filter" not in st.session_state:
        st.session_state.transaction_filter = "Spend"

    # Radio button - the key parameter links to session state for automatic persistence
    filter_option = st.radio(
        "Show:",
        options=["Spend", "Income", "Excluded", "All"],
        format_func=lambda x: f"{x} ({spend_count if x == 'Spend' else income_count if x == 'Income' else excluded_count if x == 'Excluded' else total_count})",
        horizontal=True,
        key="transaction_filter",
    )

    # Apply filter
    if filter_option == "Spend":
        display_df = transactions_df[(transactions_df["effective_exclude"] == 0) & (transactions_df["amount"] < 0)]
    elif filter_option == "Income":
        display_df = transactions_df[transactions_df["id"].isin(income_ids)]
    elif filter_option == "Excluded":
        # Excluded = everything that's either explicitly excluded OR positive but not counted as income
        display_df = transactions_df[
            (transactions_df["effective_exclude"] == 1)
            | ((transactions_df["amount"] > 0) & (~transactions_df["id"].isin(income_ids)))
        ]
    else:
        display_df = transactions_df

    if display_df.empty:
        st.info(f"No {filter_option.lower()} transactions found")
        return

    # Sort by date descending for better UX
    display_df = display_df.sort_values(["date", "amount"], ascending=[False, True])

    # Display transactions with inline actions
    st.write(f"**{len(display_df)} transactions**")

    # Use columns for each transaction row
    for idx, row in display_df.iterrows():
        col1, col2, col3, col4, col5, col6, col7 = st.columns([0.8, 2, 1, 0.8, 1.2, 1.5, 0.9])

        with col1:
            st.text(row["date"])

        with col2:
            st.markdown(f"**{row['description']}**")

        with col3:
            st.text(row["account"])

        with col4:
            # Add minus sign for negative amounts
            amount_color = "red" if row["amount"] < 0 else "green"
            amount_display = f"-${abs(row['amount']):,.2f}" if row["amount"] < 0 else f"${row['amount']:,.2f}"
            st.markdown(f":{amount_color}[**{amount_display}**]")

        with col5:
            # Category with edit capability
            categories = database.get_categories()
            new_category = st.selectbox(
                "Category",
                options=categories,
                index=categories.index(row["category"]) if row["category"] in categories else 0,
                key=f"cat_{row['id']}",
                label_visibility="collapsed",
            )
            if new_category != row["category"]:
                database.update_transaction_override(
                    row["id"], exclude_from_budget=False, manual_notes="", new_category=new_category
                )
                st.rerun()

        with col6:
            st.text(row["status_badge"])

        with col7:
            # Inline action buttons based on available actions
            actions = row["available_actions"].split(",")

            if "undo" in actions:
                if st.button("↩️", key=f"undo_{row['id']}", help="Remove manual override"):
                    override_manager.remove_manual_override(row["id"])
                    st.rerun()

            elif "include" in actions:
                if st.button("➕", key=f"include_{row['id']}", help="Include in budget"):
                    override_manager.apply_manual_override(row["id"], "include", "User included", "spending")
                    st.rerun()

            elif "exclude" in actions:
                if st.button("➖", key=f"exclude_{row['id']}", help="Exclude from budget"):
                    override_manager.apply_manual_override(row["id"], "exclude", "User excluded", "spending")
                    st.rerun()

            elif "mark_income" in actions:
                if st.button("💰", key=f"income_{row['id']}", help="Mark as income"):
                    override_manager.apply_manual_override(row["id"], "include", "User marked as income", "income")
                    st.rerun()


def render_main_app_tabs():
    """Organize and render the main app tab structure."""
    # Sidebar sections in order
    _render_file_upload_sidebar()

    # Only show backup/export if feature is enabled
    if feature_flags.is_enabled("backup_system"):
        _render_backup_export_sidebar()

    # Main content tabs
    tab1, tab2 = st.tabs(["Monthly Detail", "Trends"])

    with tab1:
        render_monthly_transactions_tab()

    with tab2:
        render_trend_analysis_tab()


def _render_file_upload_sidebar():
    """Render the file upload sidebar (existing logic from app.py)."""
    with st.sidebar:
        st.header("📁 Upload New Data")

        # Use counter in key to clear uploader after successful upload
        if "upload_counter" not in st.session_state:
            st.session_state.upload_counter = 0

        uploaded_files = st.file_uploader(
            "Upload CSV files to add new transactions",
            type=["csv"],
            accept_multiple_files=True,
            help="Upload bank or credit card CSV files. Files are processed automatically.",
            key=f"file_uploader_{st.session_state.upload_counter}",
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
                with st.spinner(LOADING_MESSAGES["processing_files"]):
                    import tempfile

                    all_inserted_ids = []

                    for uploaded_file in new_files:
                        # Use NamedTemporaryFile for safer temp file handling
                        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                            tmp.write(uploaded_file.getbuffer())
                            temp_path = Path(tmp.name)

                        # Process the file (pass original filename for account naming)
                        try:
                            transactions = data_ingestion.process_csv_file(temp_path, uploaded_file.name)

                            if transactions:
                                # Insert transactions into database
                                new_count, total_count, inserted_ids = database.insert_transactions(transactions)
                                all_inserted_ids.extend(inserted_ids)

                                # Show detailed feedback
                                st.success(f"✅ Imported {new_count} new transactions from {uploaded_file.name}")
                                if total_count > new_count:
                                    skipped = total_count - new_count
                                    st.info(f"ℹ️ Skipped {skipped} duplicate{'s' if skipped > 1 else ''}")
                            else:
                                st.warning(f"⚠️ No valid transactions found in {uploaded_file.name}")

                        except Exception as e:
                            st.error(f"{ERROR_MESSAGES['upload']}: {uploaded_file.name}")

                        # Clean up temp file
                        try:
                            temp_path.unlink(missing_ok=True)
                        except:
                            pass

                        # Mark this file as processed
                        st.session_state.processed_files.add((uploaded_file.name, len(uploaded_file.getvalue())))

                    # Clear uploader and rerun to show updated data
                    if all_inserted_ids:
                        st.session_state.upload_counter += 1
                        st.rerun()

        st.divider()

        # Account Management
        st.header("⚙️ Data Management")

        accounts = database.get_accounts_with_counts()

        if accounts:
            # Default to expanded so it doesn't collapse after delete
            with st.expander(f"Manage Accounts ({len(accounts)} accounts)", expanded=True):
                st.write("Delete transactions by account. **This cannot be undone.**")

                for account_info in accounts:
                    account_name = account_info["account"]
                    count = account_info["count"]

                    col1, col2 = st.columns([2, 1.5])

                    with col1:
                        st.write(f"**{account_name}**")
                        st.caption(f"{count} transaction{'s' if count != 1 else ''}")

                    with col2:
                        if st.button(
                            "Delete", key=f"delete_account_{account_name}", type="secondary", use_container_width=True
                        ):
                            st.session_state[f"confirm_delete_{account_name}"] = True

                    # Show confirmation dialog if delete was clicked
                    if st.session_state.get(f"confirm_delete_{account_name}"):
                        st.warning(f"⚠️ Delete **{count} transactions** from **{account_name}**? This cannot be undone.")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Yes, Delete", key=f"confirm_yes_{account_name}", type="primary"):
                                try:
                                    result = database.delete_transactions_by_account(account_name)
                                    deleted = result["deleted"]
                                    had_overrides = result["had_overrides"]

                                    msg = f"✅ Deleted {deleted} transactions from {account_name}"
                                    if had_overrides > 0:
                                        msg += f" ({had_overrides} had manual edits)"

                                    st.success(msg)

                                    # Clear processed files tracking so user can reupload the same file
                                    if "processed_files" in st.session_state:
                                        st.session_state.processed_files = set()

                                    del st.session_state[f"confirm_delete_{account_name}"]
                                    st.rerun()
                                except ValueError as e:
                                    st.error(str(e))
                                    del st.session_state[f"confirm_delete_{account_name}"]

                        with col2:
                            if st.button("Cancel", key=f"confirm_no_{account_name}"):
                                del st.session_state[f"confirm_delete_{account_name}"]
                                st.rerun()

                    st.divider()
        else:
            st.info("No accounts found. Did Pumpkin eat your data?")


def _render_backup_export_sidebar():
    """Render backup and export controls in sidebar."""
    with st.sidebar:
        st.header("💾 Backup & Export")

        # Show last backup info
        backups = database.get_backup_info()
        if backups:
            last_backup = backups[0]
            st.caption(f"Last backup: {last_backup['created'].strftime('%b %d, %Y %I:%M %p')}")
            st.caption(f"Size: {last_backup['size_mb']} MB")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Backup Now", help="Create a manual backup of your database"):
                with st.spinner(LOADING_MESSAGES["creating_backup"]):
                    backup_path = database.create_backup()
                    if backup_path:
                        st.success(SUCCESS_MESSAGES["backup"])
                        st.caption(f"{backup_path.name}")
                    else:
                        st.error(ERROR_MESSAGES["backup"])

        with col2:
            if st.button("📥 Export CSV", help="Export all transactions to CSV"):
                from pathlib import Path

                with st.spinner(LOADING_MESSAGES["exporting"]):
                    # Create export file in data directory
                    timestamp = database.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    export_path = Path("data") / f"export_{timestamp}.csv"

                    if database.export_all_transactions_to_csv(export_path):
                        st.success(SUCCESS_MESSAGES["export"])

                        # Offer download
                        with open(export_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Download Export",
                                data=f,
                                file_name=export_path.name,
                                mime="text/csv",
                            )
                    else:
                        st.error(ERROR_MESSAGES["export"])

        # Show available backups in expander with restore buttons
        if backups:
            with st.expander(f"📂 View Backups ({len(backups)} available)"):
                for i, backup in enumerate(backups):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.text(
                            f"{backup['filename']} - {backup['size_mb']} MB - {backup['created'].strftime('%b %d, %Y %I:%M %p')}"
                        )

                    with col2:
                        # Use unique key for each restore button
                        if st.button("🔄", key=f"restore_{i}", help="Restore from this backup"):
                            with st.spinner(LOADING_MESSAGES["restoring"]):
                                success = database.restore_from_backup(backup["path"])
                                if success:
                                    st.success(SUCCESS_MESSAGES["restore"])
                                    st.rerun()
                                else:
                                    st.error(ERROR_MESSAGES["restore"])

                    if i < len(backups) - 1:
                        st.divider()


def _render_calculation_breakdown(breakdown):
    """Render the calculation breakdown for transparency."""
    if not breakdown.get("auto_excluded") and not breakdown.get("manual_overrides"):
        return

    with st.expander("🔍 How we calculated your spending and income", expanded=False):
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
