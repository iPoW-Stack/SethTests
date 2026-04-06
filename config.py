# Seth Test Configuration
import os

# --- Network Configuration ---
SETH_HOST = os.environ.get("SETH_HOST", "35.184.150.163")
SETH_PORT = int(os.environ.get("SETH_PORT", "23001"))

# --- Test Account (ECDSA) ---
# Default test private key (DO NOT use in production)
TEST_ECDSA_KEY = os.environ.get(
    "SETH_TEST_KEY",
    "71e571862c0e4aefa87a3c16057a62c8331991a11746ab7ff8c6b6418e73b2f6"
)

# --- Test Account (OQS / Post-Quantum) ---
# Set these via environment variables or a keys file
TEST_OQS_KEY = os.environ.get("SETH_TEST_OQS_KEY", "")
TEST_OQS_PK = os.environ.get("SETH_TEST_OQS_PK", "")

# --- Seth Chain ID ---
# Seth currently does not define a chain ID; placeholder
SETH_CHAIN_ID = int(os.environ.get("SETH_CHAIN_ID", "0"))

# --- Transaction Defaults ---
DEFAULT_GAS_LIMIT = 5000000
DEFAULT_GAS_PRICE = 1
DEFAULT_PREPAYMENT = 10000000
DEFAULT_SHARD_ID = "0"

# --- Timing ---
TX_RECEIPT_POLL_INTERVAL = 3   # seconds
TX_RECEIPT_MAX_WAIT = 120       # seconds
CONSENSUS_SETTLE_DELAY = 2      # seconds

# --- Salt for CREATE2 deployments ---
import secrets
RANDOM_SALT = secrets.token_hex(31)