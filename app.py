import streamlit as st

from modules import database, feature_flags
from modules.app_structure import render_main_app_tabs
from modules.pumpkin_quotes import get_random_quote


def main():
    """Main application entry point."""
    st.set_page_config(page_title="Pumpkin Stats", page_icon="💰", layout="wide")

    # Create automatic backup on first load (once per session)
    if feature_flags.is_enabled("backup_system"):
        if "backup_created" not in st.session_state:
            backup_path = database.create_backup()
            st.session_state.backup_created = True
            if backup_path:
                st.session_state.last_backup_path = backup_path

    # Title with logo
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image("assets/pumpkin.jpg", width=120)
    with col2:
        st.title("Pumpkin Stats, Etc.")
        st.caption(get_random_quote())

    # Render main app with tabs
    render_main_app_tabs()


if __name__ == "__main__":
    main()
