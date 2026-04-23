# Transaction Tests
# Covers: Transfer, Nonce, Contract Creation Tx, Value Transfer
# Reference: GeneralStateTests/stChainId, stEIP1559, stArgsZeroOneBalance, TransactionTests/
from __future__ import annotations
import time
from utils import (
    SethTestContext, run_test, assert_tx_success, assert_equal,
    assert_not_equal, assert_greater_than, assert_true,
    deploy_contract, deploy_contract_with_prefund, print_section, results
)
from seth_sdk import StepType

# ==============================================================================
# Solidity Source Templates
# ==============================================================================

CHAIN_ID_SOL = """
pragma solidity ^0.8.20;

contract ChainIdChecker {
    uint256 public cachedChainId;

    constructor() {
        cachedChainId = block.chainid;
    }

    function getChainId() external view returns (uint256) {
        return block.chainid;
    }

    function checkChainId(uint256 expected) external view returns (bool) {
        return block.chainid == expected;
    }
}
"""

RECEIVER_SOL = """
pragma solidity ^0.8.20;

contract ValueReceiver {
    uint256 public totalReceived;
    event Received(address from, uint256 amount);

    receive() external payable {
        totalReceived += msg.value;
        emit Received(msg.sender, msg.value);
    }

    function deposit() external payable {
        totalReceived += msg.value;
        emit Received(msg.sender, msg.value);
    }

    function withdraw(address to, uint256 amount) external {
        payable(to).transfer(amount);
    }
}
"""

GAS_TRACKER_SOL = """
pragma solidity ^0.8.20;

contract GasTracker {
    uint256 public totalOps;

    function doWork(uint256 iterations) external returns (uint256) {
        uint256 result = 0;
        for (uint256 i = 0; i < iterations; i++) {
            result += i;
        }
        totalOps += 1;
        return result;
    }
}
"""

SIMPLE_STORE_SOL = """
pragma solidity ^0.8.20;

contract SimpleStore {
    uint256 public value;

    constructor(uint256 v) {
        value = v;
    }

    function set(uint256 v) external {
        value = v;
    }
}
"""

# ==============================================================================
# Test Functions
# ==============================================================================

def test_simple_transfer(ctx: SethTestContext):
    """Test basic native token transfer between accounts."""
    dest = "620a1c023fdef21f3c10bf3d468de37d5ecfdc7b"
    balance_before = ctx.get_balance(dest)
    receipt = ctx.w3.seth.send_transaction(
        {'to': dest, 'value': 1000000}, ctx.ecdsa_key
    )

    count = 0
    while count < 30:
        time.sleep(2)
        balance_after = ctx.get_balance(dest)
        if balance_after > balance_before:
            break

        count += 1
    assert_equal(balance_after, balance_before + 1000000, "transfer_balance_increased")


def test_transfer_zero_value(ctx: SethTestContext):
    """Test zero-value transfer (ref: stArgsZeroOneBalance)."""
    dest = "620a1c023fdef21f3c10bf3d468de37d5ecfdc7b"
    balance_before = ctx.get_balance(dest)
    receipt = ctx.w3.seth.send_transaction(
        {'to': dest, 'value': 0}, ctx.ecdsa_key
    )
    assert_tx_success(receipt, "transfer_zero_value_success")
    count = 0
    while count < 10:
        time.sleep(2)
        count += 1

    balance_after = ctx.get_balance(dest)
    assert_equal(balance_after, balance_before, "transfer_zero_value_no_change")


def test_contract_creation_via_tx(ctx: SethTestContext):
    """Test creating a contract through a transaction (ref: stCreateTest)."""
    contract = deploy_contract_with_prefund(
        ctx, SIMPLE_STORE_SOL, "SimpleStore", args=[42]
    )
    val = contract.functions.value().call()
    assert_equal(val, 42, "contract_creation_initial_value")
    receipt = contract.functions.set(100).transact(ctx.ecdsa_key)
    assert_tx_success(receipt, "contract_creation_set_value")
    assert_equal(contract.functions.value().call(), 100, "contract_creation_after_set")


def test_chain_id(ctx: SethTestContext):
    """Test that the EVM returns the correct chain ID (ref: stChainId)."""
    contract = deploy_contract_with_prefund(ctx, CHAIN_ID_SOL, "ChainIdChecker")
    chain_id = contract.functions.getChainId().call()[0]
    print(f"Chain ID: {chain_id}")
    assert_true(chain_id >= 0, "chain_id_non_negative", f"Got chain_id={chain_id}")


def test_value_transfer_to_contract(ctx: SethTestContext):
    """Test sending value to a contract with receive() function."""
    contract = deploy_contract_with_prefund(ctx, RECEIVER_SOL, "ValueReceiver")
    time.sleep(3)
    receipt = contract.functions.deposit().transact(ctx.ecdsa_key, value=500000)
    assert_tx_success(receipt, "value_transfer_deposit_tx")
    events = receipt.get('decoded_events', [])
    assert_true(len(events) > 0, "value_transfer_event_emitted", "No Received event")


def test_multiple_transfers_sequential(ctx: SethTestContext):
    """Test multiple sequential transfers (nonce increment)."""
    dest = "620a1c023fdef21f3c10bf3d468de37d5ecfdc7b"
    for i in range(3):
        receipt = ctx.w3.seth.send_transaction(
            {'to': dest, 'value': 100000}, ctx.ecdsa_key
        )
        assert_tx_success(receipt, f"sequential_transfer_{i+1}")
        time.sleep(5)


def test_contract_call_with_value(ctx: SethTestContext):
    """Test contract call that includes value transfer."""
    contract = deploy_contract_with_prefund(ctx, RECEIVER_SOL, "ValueReceiver")
    time.sleep(3)
    receipt = contract.functions.deposit().transact(ctx.ecdsa_key, value=1000000)
    assert_tx_success(receipt, "call_with_value_tx")
    total = contract.functions.totalReceived().call()[0]
    print(f"Total received: {total}")
    assert_true(total > 0, "call_with_value_total_received", f"Total: {total}")


def test_gas_consumption(ctx: SethTestContext):
    """Test that gas is consumed during contract execution."""
    contract = deploy_contract_with_prefund(ctx, GAS_TRACKER_SOL, "GasTracker")
    time.sleep(3)
    receipt = contract.functions.doWork(10).transact(ctx.ecdsa_key)
    assert_tx_success(receipt, "gas_consumption_work_tx")
    ops = contract.functions.totalOps().call()
    assert_equal(ops, 1, "gas_consumption_ops_count")


def test_nonce_increment(ctx: SethTestContext):
    """Test that nonce increments with each transaction."""
    initial_nonce = ctx.get_nonce(ctx.ecdsa_addr)
    dest = "620a1c023fdef21f3c10bf3d468de37d5ecfdc7b"
    ctx.w3.seth.send_transaction({'to': dest, 'value': 1000}, ctx.ecdsa_key)
    time.sleep(3)
    new_nonce = ctx.get_nonce(ctx.ecdsa_addr)
    assert_true(
        new_nonce >= initial_nonce,
        "nonce_incremented",
        f"Before: {initial_nonce}, After: {new_nonce}"
    )


# ==============================================================================
# Module Runner
# ==============================================================================

def run_all(ctx: SethTestContext):
    print_section("Phase 2: Transaction Tests")
    run_test(test_simple_transfer, ctx)
    run_test(test_transfer_zero_value, ctx)
    run_test(test_contract_creation_via_tx, ctx)
    run_test(test_chain_id, ctx)
    run_test(test_value_transfer_to_contract, ctx)
    run_test(test_contract_call_with_value, ctx)
    run_test(test_multiple_transfers_sequential, ctx)
    run_test(test_gas_consumption, ctx)
    run_test(test_nonce_increment, ctx)
