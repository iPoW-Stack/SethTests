# Post-Quantum (OQS) Signature Tests
from __future__ import annotations
import time, requests
from utils import (
    SethTestContext, run_test, assert_tx_success, assert_equal,
    assert_true, assert_greater_than, deploy_contract_with_prefund,
    print_section, results, CONSENSUS_SETTLE_DELAY
)
from config import TEST_OQS_KEY, TEST_OQS_PK
from seth_sdk import compile_and_link

OQS_VAULT_SOL = """
pragma solidity ^0.8.20;
contract OqsVault {
    uint256 public data;
    function store(uint256 v) public { data = v; }
    function get() public view returns (uint256) { return data; }
}
"""

OQS_COUNTER_SOL = """
pragma solidity ^0.8.20;
contract OqsCounter {
    uint256 public count;
    function increment() external { count += 1; }
    function getCount() external view returns (uint256) { return count; }
}
"""

def oqs_available():
    return bool(TEST_OQS_KEY and TEST_OQS_PK)

def get_oqs_context(ctx):
    return ctx.client.get_oqs_address(TEST_OQS_PK), TEST_OQS_KEY, TEST_OQS_PK

def get_pp_balance(ctx, caddr, uaddr):
    try:
        r = requests.post(ctx.client.query_url, data={"address": caddr + uaddr}).json()
        return int(r.get("balance", 0))
    except Exception:
        return 0

def test_oqs_transfer(ctx):
    """Test post-quantum transfer transaction."""
    if not oqs_available(): results.record_skip("oqs_transfer", "OQS not configured"); return
    addr, key, pk = get_oqs_context(ctx)
    dest = "0000000000000000000000000000000000000002"
    before = ctx.get_balance(dest)
    ctx.w3.send_oqs_transaction({"to": dest, "value": 8888, "pubkey": pk}, key)
    assert_greater_than(ctx.get_balance(dest), before, "oqs_transfer")

def test_oqs_contract_deploy(ctx):
    """Test deploying contract using OQS account."""
    if not oqs_available(): results.record_skip("oqs_deploy", "OQS not configured"); return
    addr, key, pk = get_oqs_context(ctx)
    bin_code, abi = compile_and_link(OQS_VAULT_SOL, "OqsVault")
    contract = ctx.w3.seth.contract(abi=abi, bytecode=bin_code, sender_address=addr)
    contract.deploy({"from": addr, "salt": ctx.next_salt(), "pubkey": pk}, key)
    assert_true(contract.address is not None, "oqs_deploy", f"addr={contract.address}")

def test_oqs_counter(ctx):
    """Test OQS counter with multiple increments."""
    if not oqs_available(): results.record_skip("oqs_counter", "OQS not configured"); return
    addr, key, pk = get_oqs_context(ctx)
    bin_code, abi = compile_and_link(OQS_COUNTER_SOL, "OqsCounter")
    contract = ctx.w3.seth.contract(abi=abi, bytecode=bin_code, sender_address=addr)
    contract.deploy({"from": addr, "salt": ctx.next_salt(), "pubkey": pk}, key)
    for i in range(3):
        receipt = contract.functions.increment().transact(key, oqs_pubkey=pk)
        assert_tx_success(receipt, f"oqs_inc_{i+1}")
        time.sleep(1)
    assert_equal(contract.functions.getCount().call(), 3, "oqs_counter_final")

def test_oqs_prefund(ctx):
    """Test OQS prefund deposit and consumption."""
    if not oqs_available(): results.record_skip("oqs_pp", "OQS not configured"); return
    addr, key, pk = get_oqs_context(ctx)
    bin_code, abi = compile_and_link(OQS_VAULT_SOL, "OqsVault")
    contract = ctx.w3.seth.contract(abi=abi, bytecode=bin_code, sender_address=addr)
    contract.deploy({"from": addr, "salt": ctx.next_salt(), "pubkey": pk}, key)
    caddr = contract.address
    init_pp = get_pp_balance(ctx, caddr, addr)
    contract.prefund(5000000, key, oqs_pubkey=pk)
    time.sleep(CONSENSUS_SETTLE_DELAY)
    assert_equal(get_pp_balance(ctx, caddr, addr), init_pp + 5000000, "oqs_pp_deposit")

def run_all(ctx):
    print_section("Phase 3B: Post-Quantum (OQS) Tests")
    run_test(test_oqs_transfer, ctx)
    run_test(test_oqs_contract_deploy, ctx)
    run_test(test_oqs_counter, ctx)
    run_test(test_oqs_prefund, ctx)