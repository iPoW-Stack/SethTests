# Genesis State Tests
# Merged from: GenesisTests/test_genesis.py
# Adapted to use SethTestContext (ctx.ecdsa_key) instead of hardcoded deployer key.
from __future__ import annotations

from Crypto.Hash import keccak
from ecdsa import SigningKey, SECP256k1

from utils import (
    SethTestContext, run_test, assert_equal, assert_true, assert_greater_than,
    print_section, results,
)


def test_address_derivation_consistency(ctx: SethTestContext):
    """Address derivation is consistent (offline)."""
    vectors = [
        ("c85ef7d79691fe79573b1a7064c19c1a9819ebdbd1faaab1a8ec92344438aaf4",
         "cd2a3d9f938e13cd947ec05abc7fe734df8dd826"),
        ("c87f65ff3f271bf5dc8643484f66b200109caffe4bf98c4cb393dc35740b28c0",
         "13978aee95f38490e9769c39b2773ed763d9cd5f"),
    ]
    for pk, expected in vectors:
        sk = SigningKey.from_string(bytes.fromhex(pk), curve=SECP256k1)
        pub = sk.verifying_key.to_string("uncompressed")[1:]
        addr = keccak.new(digest_bits=256).update(pub).digest()[-20:].hex()
        assert_equal(addr, expected, f"genesis_addr_{pk[:8]}")


def test_genesis_alloc_concept(ctx: SethTestContext):
    """Genesis alloc addresses are valid 20-byte hex."""
    addrs = [
        "b9c015918bdaba24b4ff057a92a3873d6eb201be",
        "cd2a3d9f938e13cd947ec05abc7fe734df8dd826",
        "0000000000000000000000000000000000000001",
        "0000000000000000000000000000000000000004",
    ]
    for a in addrs:
        assert_equal(len(a), 40, f"genesis_alloc_{a[:8]}_len")


def test_account_exists(ctx: SethTestContext):
    """Test account exists on chain with balance > 0."""
    balance = ctx.get_balance(ctx.ecdsa_addr)
    assert_true(balance > 0, "genesis_account_balance_positive", f"balance={balance}")


def test_nonexistent_account(ctx: SethTestContext):
    """Non-existent account returns 0 balance."""
    fake = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    balance = ctx.get_balance(fake)
    assert_equal(balance, 0, "genesis_nonexistent_balance_zero")


def run_all(ctx: SethTestContext):
    print_section("Genesis State Tests")
    run_test(test_address_derivation_consistency, ctx)
    run_test(test_genesis_alloc_concept, ctx)
    run_test(test_account_exists, ctx)
    run_test(test_nonexistent_account, ctx)
