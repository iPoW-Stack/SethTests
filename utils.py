# Seth Test Utilities
from __future__ import annotations
import sys
import os
import time
import traceback
from typing import Optional, Callable

# Add clipy to path so we can import seth_sdk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'clipy'))

from seth_sdk import (
    SethWeb3Mock, SethClient, SethContract, StepType,
    MessageHandleStatus, compile_and_link
)
from config import (
    SETH_HOST, SETH_PORT, TEST_ECDSA_KEY,
    TX_RECEIPT_POLL_INTERVAL, TX_RECEIPT_MAX_WAIT,
    CONSENSUS_SETTLE_DELAY, RANDOM_SALT, DEFAULT_PREPAYMENT
)

# ==============================================================================
# Colors for terminal output
# ==============================================================================
class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

# ==============================================================================
# Test Result Tracker
# ==============================================================================
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def record_pass(self, name: str):
        self.passed += 1
        print(f"  {Color.GREEN}✅ PASS{Color.END} | {name}")

    def record_fail(self, name: str, reason: str = ""):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  {Color.RED}❌ FAIL{Color.END} | {name} — {reason}")

    def record_skip(self, name: str, reason: str = ""):
        self.skipped += 1
        print(f"  {Color.YELLOW}⏭ SKIP{Color.END} | {name} — {reason}")

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*60}")
        print(f"{Color.BOLD}Test Summary{Color.END}")
        print(f"{'='*60}")
        print(f"  Total:   {total}")
        print(f"  {Color.GREEN}Passed:  {self.passed}{Color.END}")
        print(f"  {Color.RED}Failed:  {self.failed}{Color.END}")
        print(f"  {Color.YELLOW}Skipped: {self.skipped}{Color.END}")
        if self.errors:
            print(f"\n{Color.RED}Failed Tests:{Color.END}")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        print(f"{'='*60}")
        return self.failed == 0

# Global result tracker
results = TestResult()

# ==============================================================================
# Seth Test Context
# ==============================================================================
class SethTestContext:
    """Holds shared state for all tests: client, accounts, etc."""

    def __init__(self):
        self.w3 = SethWeb3Mock(SETH_HOST, SETH_PORT)
        self.client: SethClient = self.w3.client
        self.ecdsa_key = TEST_ECDSA_KEY
        self.ecdsa_addr = self.client.get_address(TEST_ECDSA_KEY)
        self.salt_counter = 0

    def next_salt(self) -> str:
        self.salt_counter += 1
        return f"{RANDOM_SALT}{self.salt_counter:04d}"

    def get_balance(self, addr: str) -> int:
        return self.client.get_balance(addr)

    def get_nonce(self, addr: str) -> int:
        return self.client.get_nonce(addr)

# ==============================================================================
# Assertion Helpers
# ==============================================================================
def assert_tx_success(receipt: dict, test_name: str):
    """Assert that a transaction succeeded (status == 0)."""
    status = receipt.get('status')
    if status == 0:
        results.record_pass(test_name)
    else:
        msg = receipt.get('msg', f"status={status}")
        results.record_fail(test_name, msg)

def assert_tx_fail(receipt: dict, test_name: str):
    """Assert that a transaction failed (status != 0)."""
    status = receipt.get('status')
    if status != 0:
        results.record_pass(test_name)
    else:
        results.record_fail(test_name, "Expected failure but got success")

def assert_equal(actual, expected, test_name: str):
    """Assert equality."""
    if actual == expected:
        results.record_pass(test_name)
    else:
        results.record_fail(test_name, f"Expected {expected}, got {actual}")

def assert_not_equal(actual, expected, test_name: str):
    """Assert inequality."""
    if actual != expected:
        results.record_pass(test_name)
    else:
        results.record_fail(test_name, f"Values should differ but both are {actual}")

def assert_greater_than(actual, threshold, test_name: str):
    if actual > threshold:
        results.record_pass(test_name)
    else:
        results.record_fail(test_name, f"Expected >{threshold}, got {actual}")

def assert_true(condition: bool, test_name: str, detail: str = ""):
    if condition:
        results.record_pass(test_name)
    else:
        results.record_fail(test_name, detail or "Condition is False")

# ==============================================================================
# Deployment Helpers
# ==============================================================================
def deploy_contract(ctx: SethTestContext, source: str, name: str,
                    args: list = None, amount: int = 0,
                    libs: dict = None) -> SethContract:
    """Compile and deploy a contract, return the SethContract object."""
    bin_code, abi = compile_and_link(source, name, libs=libs)
    contract = ctx.w3.seth.contract(abi=abi, bytecode=bin_code, sender_address=ctx.ecdsa_addr)
    contract.deploy({
        'from': ctx.ecdsa_addr,
        'salt': ctx.next_salt(),
        'args': args or [],
        'amount': amount,
    }, ctx.ecdsa_key)
    return contract

def deploy_contract_with_prepayment(ctx: SethTestContext, source: str, name: str,
                                     args: list = None, amount: int = 0,
                                     prepayment: int = DEFAULT_PREPAYMENT,
                                     libs: dict = None) -> SethContract:
    """Deploy a contract and add prepayment for subsequent calls."""
    contract = deploy_contract(ctx, source, name, args=args, amount=amount, libs=libs)
    contract.prefund(prepayment, ctx.ecdsa_key)
    time.sleep(CONSENSUS_SETTLE_DELAY)
    return contract

# ==============================================================================
# Test Runner Helper
# ==============================================================================
def run_test(func: Callable, ctx: SethTestContext, *args, **kwargs):
    """Run a single test function with error handling."""
    name = func.__name__
    print(f"\n{Color.BLUE}▶ {name}{Color.END}")
    try:
        func(ctx, *args, **kwargs)
    except Exception as e:
        results.record_fail(name, f"Exception: {e}")
        traceback.print_exc()

def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"{Color.BOLD}{title}{Color.END}")
    print(f"{'='*60}")
