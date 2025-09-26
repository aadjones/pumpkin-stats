#!/usr/bin/env python3
"""
Quick test script to understand boolean normalization behavior with SQLite data.
This will help us debug the checkbox detection issue.
"""

import pandas as pd

from modules.database import get_connection


def _normalize_boolean_value(val):
    """Copy of the exact function from app_structure.py for testing."""
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


def test_database_boolean_values():
    """Test actual values coming from the database."""
    print("=== Testing Boolean Values from Database ===")

    with get_connection() as conn:
        # Get a few sample transactions to examine exclude_from_budget values
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, description, exclude_from_budget,
                   typeof(exclude_from_budget) as type_name
            FROM transactions
            LIMIT 10
        """
        )

        results = cursor.fetchall()

        print("\nDirect database query results:")
        for row in results:
            id_val, desc, exclude_val, type_name = row
            print(f"ID: {id_val[:8]}...")
            print(f"  Description: {desc[:30]}...")
            print(f"  exclude_from_budget: {exclude_val} (SQLite type: {type_name}, Python type: {type(exclude_val)})")
            print(f"  _normalize_boolean_value result: {_normalize_boolean_value(exclude_val)}")
            print("---")


def test_pandas_dataframe_values():
    """Test values as they come through pandas DataFrame."""
    print("\n=== Testing Values Through Pandas DataFrame ===")

    with get_connection() as conn:
        # Read same data through pandas
        df = pd.read_sql_query(
            """
            SELECT id, description, exclude_from_budget
            FROM transactions
            LIMIT 10
        """,
            conn,
        )

        print(f"DataFrame info:")
        print(f"  exclude_from_budget dtype: {df['exclude_from_budget'].dtype}")
        print(f"  exclude_from_budget unique values: {df['exclude_from_budget'].unique()}")

        print("\nPandas DataFrame results:")
        for idx, row in df.iterrows():
            exclude_val = row["exclude_from_budget"]
            print(f"Row {idx}: {row['description'][:30]}...")
            print(f"  exclude_from_budget: {exclude_val} (type: {type(exclude_val)})")
            print(f"  pd.isna(): {pd.isna(exclude_val)}")
            print(f"  _normalize_boolean_value result: {_normalize_boolean_value(exclude_val)}")
            print("---")


def test_edge_cases():
    """Test various edge cases for boolean normalization."""
    print("\n=== Testing Edge Cases ===")

    test_values = [
        None,
        0,
        1,
        0.0,
        1.0,
        False,
        True,
        "0",
        "1",
        "false",
        "true",
        "False",
        "True",
        "",
        pd.NA,
        float("nan"),
    ]

    for val in test_values:
        try:
            result = _normalize_boolean_value(val)
            print(f"Input: {val} (type: {type(val)}) -> Output: {result}")
        except Exception as e:
            print(f"Input: {val} (type: {type(val)}) -> ERROR: {e}")


if __name__ == "__main__":
    test_database_boolean_values()
    test_pandas_dataframe_values()
    test_edge_cases()
