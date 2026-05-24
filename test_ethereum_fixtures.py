from __future__ import annotations

import collections
import os

from Crypto.Hash import keccak
from ecdsa import SECP256k1, SigningKey

from eth_tests.basic_adapter import validate_crypto_tests, validate_hex_prefix_tests
from eth_tests.fixtures import (
    find_ethereum_tests_root,
    iter_fixture_inventory,
    load_json,
)
from eth_tests.rlp_adapter import validate_rlp_tests
from eth_tests.state_adapter import validate_general_state_inventory
from eth_tests.transaction_adapter import validate_transaction_tests
from utils import SethTestContext, assert_equal, assert_true, print_section, results, run_test


def _addr(pk_hex: str) -> str:
    sk = SigningKey.from_string(bytes.fromhex(pk_hex), curve=SECP256k1)
    pub = sk.verifying_key.to_string("uncompressed")[1:]
    return keccak.new(digest_bits=256).update(pub).digest()[-20:].hex()


def _fixture_root_or_skip(test_name: str):
    root = find_ethereum_tests_root()
    if root is None:
        results.record_skip(
            test_name,
            "set ETHEREUM_TESTS_ROOT=/path/to/ethereum/tests to enable official fixtures",
        )
    return root


def test_fixture_inventory(ctx: SethTestContext):
    """ethereum/tests fixture inventory is available."""
    root = _fixture_root_or_skip("ethfixtures_inventory")
    if root is None:
        return
    counts = collections.Counter(ref.suite for ref in iter_fixture_inventory(root))
    assert_true(counts["BasicTests"] > 0, "ethfixtures_basic_present", str(counts))
    assert_true(counts["TransactionTests"] > 0, "ethfixtures_tx_present", str(counts))
    assert_true(counts["RLPTests"] > 0, "ethfixtures_rlp_present", str(counts))
    assert_true(
        counts["GeneralStateTests"] > 0 or counts["BlockchainTests"] > 0,
        "ethfixtures_state_or_blockchain_present",
        str(counts),
    )


def test_basic_keyaddr_fixture(ctx: SethTestContext):
    """BasicTests/keyaddrtest.json vectors match Seth address derivation."""
    root = _fixture_root_or_skip("eth_basic_keyaddr_fixture")
    if root is None:
        return
    vectors = load_json(root / "BasicTests" / "keyaddrtest.json")
    for item in vectors:
        assert_equal(_addr(item["key"]), item["addr"], f"eth_basic_keyaddr_{item['seed']}")
        assert_equal(ctx.client.get_address(item["key"]), item["addr"], f"eth_basic_client_{item['seed']}")


def test_basic_txtest_fixture(ctx: SethTestContext):
    """BasicTests/txtest.json keeps Ethereum raw tx hashes reproducible."""
    root = _fixture_root_or_skip("eth_basic_txtest_fixture")
    if root is None:
        return
    vectors = load_json(root / "BasicTests" / "txtest.json")
    for i, item in enumerate(vectors, 1):
        raw = bytes.fromhex(item["signed"])
        tx_hash = keccak.new(digest_bits=256).update(raw).hexdigest()
        assert_equal(len(tx_hash), 64, f"eth_basic_txtest_hash_len_{i}")
        assert_true(item["unsigned"] != item["signed"], f"eth_basic_txtest_signed_differs_{i}")


def test_basic_hexprefix_fixture(ctx: SethTestContext):
    """BasicTests/hexencodetest.json compact trie path encoding vectors pass."""
    root = _fixture_root_or_skip("eth_basic_hexprefix_fixture")
    if root is None:
        return
    assert_equal(validate_hex_prefix_tests(root), [], "eth_basic_hexprefix_validate")


def test_basic_crypto_fixture(ctx: SethTestContext):
    """BasicTests/crypto.json supported crypto vectors pass."""
    root = _fixture_root_or_skip("eth_basic_crypto_fixture")
    if root is None:
        return
    checked, errors = validate_crypto_tests(root)
    assert_true(checked > 0, "eth_basic_crypto_supported_present")
    assert_equal(errors, [], "eth_basic_crypto_validate")


def test_rlp_fixtures_offline(ctx: SethTestContext):
    """RLPTests valid and invalid canonical RLP fixtures pass."""
    root = _fixture_root_or_skip("eth_rlp_fixtures_offline")
    if root is None:
        return
    valid_checked, invalid_checked, errors = validate_rlp_tests(root)
    assert_true(valid_checked > 0, "eth_rlp_valid_present")
    assert_true(invalid_checked > 0, "eth_rlp_invalid_present")
    assert_equal(errors[:5], [], "eth_rlp_offline_validate")


def test_transaction_fixtures_offline(ctx: SethTestContext):
    """TransactionTests raw fixtures validate offline hash/gas/exception metadata."""
    root = _fixture_root_or_skip("eth_transaction_fixtures_offline")
    if root is None:
        return
    summary, errors = validate_transaction_tests(root)
    assert_true(summary.total > 0, "eth_txfixtures_total", str(summary))
    assert_true(summary.valid > 0, "eth_txfixtures_valid_present", str(summary))
    assert_true(summary.invalid > 0, "eth_txfixtures_invalid_present", str(summary))
    assert_equal(errors[:5], [], "eth_txfixtures_offline_validate")


def test_general_state_fixtures_inventory(ctx: SethTestContext):
    """GeneralStateTests fixtures are indexed and mapped to Seth coverage areas."""
    root = _fixture_root_or_skip("eth_general_state_fixtures_inventory")
    if root is None:
        return
    limit = int(os.environ.get("ETHEREUM_STATE_FIXTURE_LIMIT", "0") or "0") or None
    summary, errors = validate_general_state_inventory(root, limit=limit)
    assert_true(summary.files > 0, "eth_statefixtures_files_present", str(summary))
    assert_true(summary.cases > 0, "eth_statefixtures_cases_present", str(summary))
    assert_true(summary.mapped_categories > 0, "eth_statefixtures_mapped_categories", str(summary))
    assert_true(summary.txbytes_checked > 0, "eth_statefixtures_txbytes_checked", str(summary))
    assert_equal(errors[:5], [], "eth_statefixtures_inventory_validate")


def run_all(ctx: SethTestContext):
    print_section("Ethereum/tests Fixture Migration")
    run_test(test_fixture_inventory, ctx)
    run_test(test_basic_keyaddr_fixture, ctx)
    run_test(test_basic_txtest_fixture, ctx)
    run_test(test_basic_hexprefix_fixture, ctx)
    run_test(test_basic_crypto_fixture, ctx)
    run_test(test_rlp_fixtures_offline, ctx)
    run_test(test_transaction_fixtures_offline, ctx)
    run_test(test_general_state_fixtures_inventory, ctx)
