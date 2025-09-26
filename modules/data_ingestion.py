import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class CategoryMapper:
    """Maps various institution category names to standardized categories."""

    STANDARD_CATEGORIES = {
        "Food & drink": ["food", "drink", "restaurant", "bar", "coffee", "dining"],
        "Groceries": ["grocery", "groceries", "supermarket", "market", "food store"],
        "Automotive": [
            "gas",
            "fuel",
            "gasoline",
            "shell",
            "exxon",
            "bp",
            "chevron",
            "automotive",
            "auto",
            "oil change",
            "repair",
            "mechanic",
            "car wash",
            "parking",
        ],
        "Pumpkin": ["pet", "vet", "veterinary", "dog", "animal", "petco", "petsmart"],
        "Shopping": ["shopping", "retail", "store", "merchandise", "amazon", "target"],
        "Bills & utilities": ["utility", "utilities", "electric", "water", "internet", "phone", "cable"],
        "Travel": ["travel", "hotel", "airline", "flight", "uber", "lyft", "taxi"],
        "Health & wellness": ["health", "medical", "pharmacy", "doctor", "hospital", "fitness", "gym"],
        "Entertainment": ["entertainment", "movie", "streaming", "netflix", "spotify", "games"],
        "Fees & adjustments": ["fee", "fees", "adjustment", "overdraft", "late", "annual"],
        "Income": ["payroll", "salary", "deposit", "income", "refund", "cashback"],
        "Other": [],  # catch-all
    }

    @classmethod
    def normalize_category(cls, category: str) -> str:
        """Map institution category to standardized category."""
        if not category or pd.isna(category):
            return "Other"

        category_lower = category.lower().strip()

        # Direct mapping first
        for standard, keywords in cls.STANDARD_CATEGORIES.items():
            if category_lower in keywords:
                return standard

        # Fuzzy matching for common variations
        for standard, keywords in cls.STANDARD_CATEGORIES.items():
            for keyword in keywords:
                if keyword in category_lower:
                    return standard

        return "Other"


class TransactionParser:
    """Parses different CSV formats from various financial institutions."""

    def __init__(self):
        self.category_mapper = CategoryMapper()

    def detect_format(self, df: pd.DataFrame) -> str:
        """Detect CSV format based on column structure."""
        columns = [col.lower().strip() for col in df.columns]

        # TD Bank format (separate debit/credit columns)
        if "debit" in columns and "credit" in columns:
            return "bank"

        # Credit card format (single amount column)
        elif "amount" in columns and ("transaction date" in columns or "trans. date" in columns):
            return "credit_card"

        # Tom's bank format (no headers, different structure)
        elif len(df.columns) == 5 and df.columns[0].startswith("8/"):
            return "bank_no_headers"

        else:
            return "unknown"

    def parse_bank_csv(self, df: pd.DataFrame, account_name: str) -> List[Dict]:
        """Parse TD Bank CSV format."""
        transactions = []

        for _, row in df.iterrows():
            # Skip empty rows
            if pd.isna(row.get("Date")):
                continue

            # Determine amount and sign
            debit_val = row.get("Debit", "")
            credit_val = row.get("Credit", "")

            amount = None

            # Handle debit amounts
            if debit_val and str(debit_val).strip() and str(debit_val) != "nan":
                try:
                    amount = -float(str(debit_val).replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    pass

            # Handle credit amounts
            elif credit_val and str(credit_val).strip() and str(credit_val) != "nan":
                try:
                    amount = float(str(credit_val).replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    pass

            if amount is None:
                continue  # Skip if no valid amount

            # Auto-categorize based on transaction type and description
            txn_type = row.get("Transaction Type", "")
            description = row.get("Description", "")
            category, auto_exclude_reason = self._auto_categorize_bank(txn_type, description, amount)

            transactions.append(
                {
                    "date": self._parse_date(row["Date"]),
                    "description": description,
                    "amount": amount,
                    "account": account_name,
                    "category": category,
                    "auto_exclude_reason": auto_exclude_reason,
                    "raw_description": f"{txn_type}: {description}",
                }
            )

        return transactions

    def parse_bank_no_headers_csv(self, df: pd.DataFrame, account_name: str) -> List[Dict]:
        """Parse Tom's bank CSV format (no headers, different structure)."""
        transactions = []

        for _, row in df.iterrows():
            # Tom's format appears to be: date, amount, *, *, description
            if len(row) < 5:
                continue

            date_str = str(row.iloc[0])
            amount_str = str(row.iloc[1])
            description = str(row.iloc[4]) if len(row) > 4 else ""

            # Skip if no valid date
            if not date_str or "/" not in date_str:
                continue

            # Parse amount (appears to be negative for debits)
            try:
                amount = float(amount_str.replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                continue

            # Auto-categorize
            category, auto_exclude_reason = self._auto_categorize_bank("DEBIT", description, amount)

            transactions.append(
                {
                    "date": self._parse_date(date_str),
                    "description": description,
                    "amount": amount,
                    "account": account_name,
                    "category": category,
                    "auto_exclude_reason": auto_exclude_reason,
                    "raw_description": description,
                }
            )

        return transactions

    def parse_credit_card_csv(self, df: pd.DataFrame, account_name: str) -> List[Dict]:
        """Parse credit card CSV format."""
        transactions = []

        for _, row in df.iterrows():
            # Find date column (varies by institution)
            date_col = None
            for col in ["Transaction Date", "Trans. Date"]:
                if col in df.columns and not pd.isna(row.get(col)):
                    date_col = col
                    break

            if not date_col:
                continue

            # Parse amount
            amount_str = str(row.get("Amount", 0))
            if not amount_str or amount_str == "nan":
                continue

            amount = float(amount_str.replace(",", "").replace("$", ""))

            # Get category and description
            institution_category = row.get("Category", "")
            description = row.get("Description", "")

            # Skip credit card payments (positive amounts that are just payment processing)
            desc_upper = description.upper()
            if amount > 0 and any(word in desc_upper for word in ["PAYMENT", "BILL PA", "AUTOPAY", "ONLINE PMT"]):
                continue  # Skip credit card payments to avoid double counting

            # Normalize category - but also check description for pet stores
            category = self.category_mapper.normalize_category(institution_category)

            # Override category if description matches pet patterns
            if any(word in desc_upper for word in ["PETCO", "PETSMART", "VET", "ANIMAL HOSPITAL"]):
                category = "Pumpkin"

            transactions.append(
                {
                    "date": self._parse_date(row[date_col]),
                    "description": description,
                    "amount": amount,
                    "account": account_name,
                    "category": category,
                    "auto_exclude_reason": None,  # Credit card transactions are not auto-excluded
                    "raw_description": description,
                }
            )

        return transactions

    def _parse_date(self, date_str: str) -> str:
        """Parse date string to YYYY-MM-DD format."""
        try:
            # Handle M/D/YYYY format
            date_obj = datetime.strptime(str(date_str), "%m/%d/%Y")
            return date_obj.strftime("%Y-%m-%d")
        except:
            try:
                # Handle MM/DD/YYYY format
                date_obj = datetime.strptime(str(date_str), "%m/%d/%Y")
                return date_obj.strftime("%Y-%m-%d")
            except:
                # Return as-is if parsing fails
                return str(date_str)

    def _auto_categorize_bank(self, txn_type: str, description: str, amount: float) -> Tuple[str, Optional[str]]:
        """Auto-categorize bank transactions based on type and description.

        Returns:
            Tuple of (category, auto_exclude_reason)
            auto_exclude_reason is None for transactions that should be included in budget
        """
        desc_upper = description.upper()

        # Income patterns (regardless of amount sign, check transaction type and description)
        if txn_type in ["DIRECTDEP", "CREDIT"] or "PAYROLL" in desc_upper:
            return "Income", None
        elif ("ZELLE" in desc_upper or "VENMO" in desc_upper) and amount > 0:
            return "Income", None  # Only positive Zelle/Venmo are income
        elif amount > 0:  # Other positive amounts
            return "Income", None

        # For negative Zelle/Venmo, let them fall through to be categorized as regular spending
        # unless they have explicit transfer language

        # Transfer/Payment patterns (should not count as spending)
        # Be very conservative - only obvious credit card payments and bank transfers
        transfer_keywords = [
            "ONLINE TRANSFER",
            "RECURRING TRANSFER",
            "XFER TRANSFER",
            "CREDIT CRD EPAY",
            "CARD SERV",
            "ONLINE PMT",
            "AUTO PMT",
            "DISCOVER E-PAYMENT",
            "CHASE CARD SERV",
            "CHASE CREDIT CRD",
        ]
        if any(keyword in desc_upper for keyword in transfer_keywords):
            # Determine specific transfer type for better transparency
            if "CREDIT" in desc_upper or "CARD" in desc_upper:
                return "Transfers", "credit_card_payment"
            elif "TRANSFER" in desc_upper:
                return "Transfers", "account_transfer"
            else:
                return "Transfers", "payment"

        # Debits/Spending patterns (not excluded from budget)

        # Common patterns
        if any(word in desc_upper for word in ["GROCERY", "MARKET", "FOOD"]):
            return "Groceries", None
        elif any(word in desc_upper for word in ["GAS", "SHELL", "EXXON", "BP", "AUTOMOTIVE", "AUTO"]):
            return "Automotive", None
        elif any(word in desc_upper for word in ["VET", "PET", "PETCO", "PETSMART"]):
            return "Pumpkin", None
        elif any(word in desc_upper for word in ["RESTAURANT", "COFFEE", "STARBUCKS"]):
            return "Food & drink", None
        elif "ATM" in desc_upper or "WITHDRAWAL" in desc_upper:
            return "Other", None
        elif any(word in desc_upper for word in ["ELECTRIC", "UTILITY", "WATER", "INTERNET"]):
            return "Bills & utilities", None

        return "Other", None


def parse_account_info(filename: str) -> Tuple[str, str, str]:
    """Extract account info from filename."""
    # Remove file extension and convert to lowercase
    name = filename.lower().replace(".csv", "")

    parts = name.split("-")
    if len(parts) >= 3:
        owner = parts[0]  # dara, tom, joint
        account_type = parts[1]  # bank, credit
        institution = parts[2] if len(parts) > 2 else "unknown"

        # Clean up institution name
        institution = institution.replace("july", "").replace("aug", "").strip()

        account_name = f"{owner.title()} {account_type.title()}"
        if institution and institution != "unknown":
            account_name += f" ({institution.title()})"

        return owner, account_type, account_name

    # If no pattern matches, clean up the filename for display
    clean_filename = filename.lower().replace(".csv", "").replace("-", " ").replace("_", " ")
    # Capitalize each word
    clean_filename = " ".join(word.capitalize() for word in clean_filename.split())

    return "unknown", "unknown", clean_filename


def process_csv_file(file_path: Path, original_filename: Optional[str] = None) -> List[Dict]:
    """Process a single CSV file and return normalized transactions."""
    parser = TransactionParser()

    # Extract account info from original filename (if provided) or file path
    filename_for_parsing = original_filename if original_filename else file_path.name
    owner, account_type, account_name = parse_account_info(filename_for_parsing)

    try:
        # Read CSV
        df = pd.read_csv(file_path)

        # Detect format
        format_type = parser.detect_format(df)

        if format_type == "bank":
            transactions = parser.parse_bank_csv(df, account_name)
        elif format_type == "bank_no_headers":
            transactions = parser.parse_bank_no_headers_csv(df, account_name)
        elif format_type == "credit_card":
            transactions = parser.parse_credit_card_csv(df, account_name)
        else:
            print(f"Unknown format for {file_path.name}")
            return []

        print(f"Processed {file_path.name}: {len(transactions)} transactions ({format_type} format)")
        return transactions

    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")
        return []


def load_all_csv_files(data_dir: Path = Path("data")) -> List[Dict]:
    """Load and process all CSV files in the data directory."""
    all_transactions = []

    # Find all CSV files (case insensitive)
    csv_files = list(data_dir.glob("*.csv")) + list(data_dir.glob("*.CSV"))

    # Skip demo.csv
    csv_files = [f for f in csv_files if f.name != "demo.csv"]

    for file_path in csv_files:
        transactions = process_csv_file(file_path)
        all_transactions.extend(transactions)

    print(f"\nTotal transactions loaded: {len(all_transactions)}")
    return all_transactions
