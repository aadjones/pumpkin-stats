import streamlit as st

from modules.app_structure import render_main_app_tabs


def main():
    """Main application entry point."""
    st.set_page_config(page_title="Pumpkin Stats", page_icon="💰", layout="wide")

    # Title with logo
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image("assets/pumpkin.jpg", width=120)
    with col2:
        st.title("Pumpkin Stats")

    # Render main app with tabs
    render_main_app_tabs()


if __name__ == "__main__":
    main()
