# Central place for finance dashboard configuration
"""
This module contains all shared constants used across the application.
Consolidating these ensures consistent behavior between data ingestion,
financial calculations, and trend analysis.
"""

# ============================================================================
# INCOME DETECTION PATTERNS
# ============================================================================
# Keywords that identify legitimate income transactions
# Used to filter positive amounts and avoid counting transfers/Venmo as income
INCOME_PATTERNS = [
    "PAYROLL",
    "DIRECT DEP",
    "DIRECTDEP",
    "REIMBURS",
    "REFUND",
    "CASHBACK",
    "CASH BACK",
    "GIFT",
    "BONUS",
    "INTEREST",
]

# Credit card positive amounts under this threshold are considered cashback/refunds
CREDIT_CARD_INCOME_THRESHOLD = 100.00

# ============================================================================
# TRANSFER/PAYMENT DETECTION PATTERNS
# ============================================================================
# Keywords that identify transactions to exclude from spending calculations
# These are money movements between accounts, not actual spending
TRANSFER_KEYWORDS = [
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

# Categories to exclude from budget calculations
EXCLUDED_CATEGORIES = [
    "Transfers",
    "Credit Card Payment",
]
