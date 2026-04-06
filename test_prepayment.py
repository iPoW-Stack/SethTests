# Gas Prepayment Tests
# Covers: Prepayment Deposit, Consumption, Accumulation, Balance Verification
# Seth-specific feature: gas prepayment mechanism for contract calls
from __future__ import annotations
import time
import requests
from utils import (
    SethTestContext, run_test, assert_tx_success, assert_equal,
    assert_true, deploy_contract, deploy_contract_with_prepayment,
    print_section, results, CONSENSUS_SETTLE_DELAY
)

# ==============================================================================
# Solidity Source Templates
# ==============================================================================

VAULT_SOL = """
pragma solidity ^0.8.20;

contract Vault {
    uint256 public val;
    event ValueSet(uint256 newValue);

    function set(uint256 v) external {
        val = v;
        emit ValueSet(v);
    }

    function get() external view returns (uint256) {
        return val;
    }
}
"""

HEAVY_WORK_SOL = """
pragma solidity ^0.8.20;

contract HeavyWork {
    uint256 public result;

    function compute(uint256 iterations) external returns (uint256) {
        uint256 r = 0;
        for (uint256 i = 0; i < iterations; i++) {
            r = r + i * i;
        }
        result = r;
        return r;
    }

    function storeMultiple(uint256[] calldata values) external {
        // This uses more gas due to array processing
        for (uint256 i = 0; i < values.length; i++) {
            result += values[i];
        }
    }
}
"""

# ==============================================================================
# Helper
# ==============================================================================

def get_prepayment_balance(ctx: SethTestContext, contract_addr: str, user_addr: str) -> int:
    """Query prepayment balance for a user on a contract."""
    prepay_addr = contract_addr + user_addr
    try:
        resp = requests.post(ctx.client.query_url, data={"address": prepay_addr}).json()
        return int(resp.get("balance", 0))
    except Exception as e:
        print(f"  [WARN] Prepayment query failed: {e}")
        return 0


# ==============================================================================
# Test Functions
# ==============================================================================

def test_prepayment_basic_deposit(ctx: SethTestContext):
    """Test basic prepayment deposit to a contract."""
    contract = deploy_contract(ctx, VAULT_SOL, "Vault")
    addr = contract.address

    initial_pp = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)

    # Deposit prepayment
    deposit_amount = 5000000
    receipt = contract.prepayment(deposit_amount, ctx.ecdsa_key)
    assert_tx_success(receipt, "prepayment_deposit_tx")

    # Wait for consensus
    time.sleep(CONSENSUS_SETTLE_DELAY)

    # Verify accumulation
    after_pp = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)
    assert_equal(after_pp, initial_pp + deposit_amount, "prepayment_deposit_accumulated")


def test_prepayment_multiple_deposits(ctx: SethTestContext):
    """Test that multiple prepayment deposits accumulate correctly."""
    contract = deploy_contract(ctx, VAULT_SOL, "Vault")
    addr = contract.address

    initial_pp = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)

    # First deposit
    receipt1 = contract.prepayment(3000000, ctx.ecdsa_key)
    assert_tx_success(receipt1, "prepayment_multi_deposit_1")
    time.sleep(CONSENSUS_SETTLE_DELAY)

    # Second deposit
    receipt2 = contract.prepayment(2000000, ctx.ecdsa_key)
    assert_tx_success(receipt2, "prepayment_multi_deposit_2")
    time.sleep(CONSENSUS_SETTLE_DELAY)

    # Verify total accumulation
    final_pp = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)
    expected = initial_pp + 5000000
    assert_equal(final_pp, expected, "prepayment_multi_accumulated")


def test_prepayment_gas_consumption(ctx: SethTestContext):
    """Test that contract call consumes gas from prepayment."""
    contract = deploy_contract(ctx, VAULT_SOL, "Vault")
    addr = contract.address

    # Deposit prepayment
    deposit_amount = 10000000
    receipt = contract.prepayment(deposit_amount, ctx.ecdsa_key)
    assert_tx_success(receipt, "prepayment_consume_deposit")
    time.sleep(CONSENSUS_SETTLE_DELAY)

    pp_before_call = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)

    # Execute contract call (should consume gas from prepayment)
    call_receipt = contract.functions.set(42).transact(ctx.ecdsa_key, prepayment=0)
    assert_tx_success(call_receipt, "prepayment_consume_call")
    time.sleep(CONSENSUS_SETTLE_DELAY)

    pp_after_call = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)

    # Verify gas was consumed
    consumed = pp_before_call - pp_after_call
    assert_true(consumed > 0, "prepayment_gas_consumed",
                f"Before: {pp_before_call}, After: {pp_after_call}, Consumed: {consumed}")


def test_prepayment_with_call_deposit(ctx: SethTestContext):
    """Test prepayment deposit included with contract call."""
    contract = deploy_contract(ctx, VAULT_SOL, "Vault")
    addr = contract.address

    # Initial deposit
    contract.prepayment(5000000, ctx.ecdsa_key)
    time.sleep(CONSENSUS_SETTLE_DELAY)
    pp_before = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)

    # Call with additional prepayment
    extra_prepay = 1000000
    call_receipt = contract.functions.set(99).transact(ctx.ecdsa_key, prepayment=extra_prepay)
    assert_tx_success(call_receipt, "prepayment_call_with_deposit_tx")
    time.sleep(CONSENSUS_SETTLE_DELAY)

    pp_after = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)
    # Should be: pp_before + extra_prepay - gas_used
    # At minimum, pp_after should be >= pp_before (since extra_prepay should cover gas)
    assert_true(pp_after >= pp_before, "prepayment_call_with_deposit_balance",
                f"Before: {pp_before}, After: {pp_after}")


def test_prepayment_heavy_gas_usage(ctx: SethTestContext):
    """Test prepayment with computationally heavy contract."""
    contract = deploy_contract(ctx, HEAVY_WORK_SOL, "HeavyWork")
    addr = contract.address

    # Deposit sufficient prepayment
    contract.prepayment(20000000, ctx.ecdsa_key)
    assert_tx_success(
        ctx.client.wait_for_receipt(
            ctx.client.send_transaction_auto(
                ctx.ecdsa_key, addr, 7, prepayment=20000000
            )
        ), "prepayment_heavy_deposit"
    )
    time.sleep(CONSENSUS_SETTLE_DELAY)

    pp_before = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)

    # Heavy computation
    receipt = contract.functions.compute(100).transact(ctx.ecdsa_key, prepayment=0)
    assert_tx_success(receipt, "prepayment_heavy_compute")
    time.sleep(CONSENSUS_SETTLE_DELAY)

    pp_after = get_prepayment_balance(ctx, addr, ctx.ecdsa_addr)
    consumed = pp_before - pp_after
    assert_true(consumed > 0, "prepayment_heavy_gas_consumed",
                f"Gas consumed: {consumed}")


# ==============================================================================
# Module Runner
# ==============================================================================

def run_all(ctx: SethTestContext):
    print_section("Phase 3A: Gas Prepayment Tests")
    run_test(test_prepayment_basic_deposit, ctx)
    run_test(test_prepayment_multiple_deposits, ctx)
    run_test(test_prepayment_gas_consumption, ctx)
    run_test(test_prepayment_with_call_deposit, ctx)
    run_test(test_prepayment_heavy_gas_usage, ctx)
