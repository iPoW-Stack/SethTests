# Blockchain Semantics Tests
# Reference:
#   - ethereum/tests BlockchainTests/ValidBlocks/bcStateTests
#   - ethereum/tests BlockchainTests/ValidBlocks/bcValidBlockTest
#   - ethereum/tests BlockchainTests/InvalidBlocks/*
#
# Goal:
#   Validate chain-level state persistence and transaction ordering semantics
#   through the live Seth node. These are not raw Ethereum fixture replays;
#   instead they reproduce the most important blockchain invariants using the
#   existing Seth SDK black-box interfaces.

from __future__ import annotations

import time

from utils import (
    SethTestContext,
    assert_equal,
    assert_greater_than,
    assert_tx_fail,
    assert_tx_success,
    deploy_contract_with_prefund,
    print_section,
    run_test,
)


BLOCKCHAIN_COUNTER_SOL = """
pragma solidity ^0.8.20;

contract ChainCounter {
    uint256 public value;
    uint256 public totalReceived;

    event ValueSet(uint256 value);

    constructor(uint256 initialValue) payable {
        value = initialValue;
        if (msg.value > 0) {
            totalReceived = msg.value;
        }
    }

    function increment() external {
        value += 1;
        emit ValueSet(value);
    }

    function setValue(uint256 newValue) external {
        value = newValue;
        emit ValueSet(value);
    }

    function add(uint256 delta) external {
        value += delta;
        emit ValueSet(value);
    }

    function guardedSub(uint256 delta) external {
        require(value >= delta, "underflow-guard");
        value -= delta;
        emit ValueSet(value);
    }

    function payableBump(uint256 delta) external payable {
        value += delta;
        totalReceived += msg.value;
        emit ValueSet(value);
    }
}
"""


def _settle(delay: int = 5):
    time.sleep(delay)


def test_state_persists_across_confirmed_transactions(ctx: SethTestContext):
    """Reference: bcStateTests; state written in one confirmed tx must be visible to later blocks."""
    contract = deploy_contract_with_prefund(ctx, BLOCKCHAIN_COUNTER_SOL, "ChainCounter", args=[10])

    r1 = contract.functions.increment().transact(ctx.ecdsa_key)
    assert_tx_success(r1, "bc_state_tx1_success")
    _settle()
    assert_equal(contract.functions.value().call(), 11, "bc_state_after_tx1")

    r2 = contract.functions.add(9).transact(ctx.ecdsa_key)
    assert_tx_success(r2, "bc_state_tx2_success")
    _settle()
    assert_equal(contract.functions.value().call(), 20, "bc_state_after_tx2")


def test_reverted_transaction_does_not_corrupt_following_state(ctx: SethTestContext):
    """Reference: invalid state transition isolation; a reverted tx must not corrupt later successful execution."""
    contract = deploy_contract_with_prefund(ctx, BLOCKCHAIN_COUNTER_SOL, "ChainCounter", args=[5])

    ok1 = contract.functions.add(5).transact(ctx.ecdsa_key)
    assert_tx_success(ok1, "bc_revert_pre_success")
    _settle()
    assert_equal(contract.functions.value().call(), 10, "bc_revert_pre_value")

    bad = contract.functions.guardedSub(100).transact(ctx.ecdsa_key)
    assert_tx_fail(bad, "bc_revert_expected_fail")
    _settle()
    assert_equal(contract.functions.value().call(), 10, "bc_revert_preserves_state")

    ok2 = contract.functions.guardedSub(3).transact(ctx.ecdsa_key)
    assert_tx_success(ok2, "bc_revert_post_success")
    _settle()
    assert_equal(contract.functions.value().call(), 7, "bc_revert_post_value")


def test_transaction_ordering_yields_expected_final_state(ctx: SethTestContext):
    """Reference: valid block ordering semantics; sequential tx execution from one sender should produce deterministic final state."""
    contract = deploy_contract_with_prefund(ctx, BLOCKCHAIN_COUNTER_SOL, "ChainCounter", args=[0])

    sequence = [1, 2, 3, 4]
    expected = 0
    for idx, delta in enumerate(sequence, start=1):
        receipt = contract.functions.add(delta).transact(ctx.ecdsa_key)
        assert_tx_success(receipt, f"bc_order_tx_{idx}_success")
        expected += delta
        _settle()

    assert_equal(contract.functions.value().call(), expected, "bc_order_final_value")


def test_value_transfer_and_state_survive_across_blocks(ctx: SethTestContext):
    """Reference: bcValidBlockTest value+state execution; payable tx should persist balance and state across confirmations."""
    contract = deploy_contract_with_prefund(ctx, BLOCKCHAIN_COUNTER_SOL, "ChainCounter", args=[1])
    before_total = contract.functions.totalReceived().call()
    if isinstance(before_total, tuple):
        before_total = before_total[0]

    r1 = contract.functions.payableBump(4).transact(ctx.ecdsa_key, value=700000)
    assert_tx_success(r1, "bc_value_tx1_success")
    _settle()
    assert_equal(contract.functions.value().call(), 5, "bc_value_after_tx1_state")
    assert_equal(contract.functions.totalReceived().call(), before_total + 700000, "bc_value_after_tx1_balance_proxy")

    r2 = contract.functions.payableBump(5).transact(ctx.ecdsa_key, value=300000)
    assert_tx_success(r2, "bc_value_tx2_success")
    _settle()
    assert_equal(contract.functions.value().call(), 10, "bc_value_after_tx2_state")
    assert_equal(contract.functions.totalReceived().call(), before_total + 1000000, "bc_value_after_tx2_balance_proxy")


def test_nonce_and_balance_move_forward_together(ctx: SethTestContext):
    """Reference: block import should commit both sender nonce changes and recipient balance changes."""
    dest = "620a1c023fdef21f3c10bf3d468de37d5ecfdc7b"
    nonce_before = ctx.get_nonce(ctx.ecdsa_addr)
    balance_before = ctx.get_balance(dest)

    receipt = ctx.w3.seth.send_transaction({"to": dest, "value": 3456}, ctx.ecdsa_key)
    assert_tx_success(receipt, "bc_nonce_balance_tx_success")
    _settle()

    nonce_after = ctx.get_nonce(ctx.ecdsa_addr)
    assert_equal(nonce_after, nonce_before + 1, "bc_nonce_incremented")

    # Retry balance query up to 60 seconds
    balance_after = balance_before
    for _ in range(30):
        balance_after = ctx.get_balance(dest)
        if balance_after > balance_before:
            break
        time.sleep(1)
    assert_greater_than(balance_after, balance_before, "bc_balance_increased")


def run_all(ctx: SethTestContext):
    print_section("Phase 4: Blockchain Semantics")
    run_test(test_state_persists_across_confirmed_transactions, ctx)
    run_test(test_reverted_transaction_does_not_corrupt_following_state, ctx)
    run_test(test_transaction_ordering_yields_expected_final_state, ctx)
    run_test(test_value_transfer_and_state_survive_across_blocks, ctx)
    run_test(test_nonce_and_balance_move_forward_together, ctx)

