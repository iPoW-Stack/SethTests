# Gas Prefund Tests
# Covers: Prefund Deposit, Consumption, Accumulation, Balance Verification
# Seth-specific feature: gas prefund mechanism for contract calls
from __future__ import annotations
import time
import requests
from utils import (
    SethTestContext, run_test, assert_tx_success, assert_equal,
    assert_true, deploy_contract, deploy_contract_with_prefund,
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

def get_prefund_balance(ctx: SethTestContext, contract_addr: str, user_addr: str) -> int:
    """Query prefund balance for a user on a contract."""
    prepay_addr = contract_addr + user_addr
    try:
        resp = requests.post(ctx.client.query_url, data={"address": prepay_addr}).json()
        return int(resp.get("balance", 0))
    except Exception as e:
        print(f"  [WARN] Prefund query failed: {e}")
        return 0


# ==============================================================================
# Test Functions
# ==============================================================================

def test_prefund_basic_deposit(ctx: SethTestContext):
    """Test basic prefund deposit to a contract."""
    contract = deploy_contract(ctx, VAULT_SOL, "Vault")
    addr = contract.address

    initial_pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)

    # Deposit prefund
    deposit_amount = 5000000
    receipt = contract.prefund(deposit_amount, ctx.ecdsa_key)
    assert_tx_success(receipt, "prefund_deposit_tx")

    count = 0
    while count < 10:
        time.sleep(2)
        pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
        if pp > initial_pp:
            break

        count += 1

    # Verify accumulation
    after_pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
    assert_equal(after_pp, initial_pp + deposit_amount, "prefund_deposit_accumulated")


def test_prefund_multiple_deposits(ctx: SethTestContext):
    """Test that multiple prefund deposits accumulate correctly."""
    contract = deploy_contract(ctx, VAULT_SOL, "Vault")
    addr = contract.address

    initial_pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)

    # First deposit
    receipt1 = contract.prefund(3000000, ctx.ecdsa_key)
    assert_tx_success(receipt1, "prefund_multi_deposit_1")

    # Second deposit
    receipt2 = contract.prefund(2000000, ctx.ecdsa_key)
    assert_tx_success(receipt2, "prefund_multi_deposit_2")

    count = 0
    while count < 30:
        time.sleep(2)
        pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
        if pp >= initial_pp + 5000000:
            break

        count += 1

    # Verify total accumulation
    final_pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
    expected = initial_pp + 5000000
    assert_equal(final_pp, expected, "prefund_multi_accumulated")


def test_prefund_gas_consumption(ctx: SethTestContext):
    """Test that contract call consumes gas from prefund."""
    contract = deploy_contract(ctx, VAULT_SOL, "Vault")
    addr = contract.address
    initial_pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)

    # Deposit prefund
    deposit_amount = 10000000
    receipt = contract.prefund(deposit_amount, ctx.ecdsa_key)
    assert_tx_success(receipt, "prefund_consume_deposit")
    time.sleep(CONSENSUS_SETTLE_DELAY)

    count = 0
    while count < 30:
        time.sleep(2)
        pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
        if pp >= initial_pp + deposit_amount:
            break

        count += 1

    pp_before_call = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)

    # Execute contract call (should consume gas from prefund)
    call_receipt = contract.functions.set(42).transact(ctx.ecdsa_key, prefund=0)
    assert_tx_success(call_receipt, "prefund_consume_call")


    count = 0
    while count < 30:
        time.sleep(2)
        pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
        if pp < deposit_amount:
            break

        count += 1

    pp_after_call = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)

    # Verify gas was consumed
    consumed = pp_before_call - pp_after_call
    assert_true(consumed > 0, "prefund_gas_consumed",
                f"Before: {pp_before_call}, After: {pp_after_call}, Consumed: {consumed}")


def test_prefund_with_call_deposit(ctx: SethTestContext):
    """Test prefund deposit included with contract call."""
    contract = deploy_contract(ctx, VAULT_SOL, "Vault")
    addr = contract.address

    # Initial deposit
    contract.prefund(5000000, ctx.ecdsa_key)
    count = 0
    while count < 30:
        time.sleep(2)
        pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
        if pp >= 5000000:
            break

        count += 1

    pp_before = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)

    # Call with additional prefund
    extra_prepay = 1000000
    call_receipt = contract.functions.set(99).transact(ctx.ecdsa_key, prefund=extra_prepay)
    assert_tx_success(call_receipt, "prefund_call_with_deposit_tx")
    count = 0
    while count < 30:
        time.sleep(2)
        pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
        if pp < pp_before:
            break

        count += 1
    pp_after = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
    # Should be: pp_before + extra_prepay - gas_used
    # At minimum, pp_after should be >= pp_before (since extra_prepay should cover gas)
    assert_true(pp_after >= pp_before, "prefund_call_with_deposit_balance",
                f"Before: {pp_before}, After: {pp_after}")


def test_prefund_heavy_gas_usage(ctx: SethTestContext):
    """Test prefund with computationally heavy contract."""
    contract = deploy_contract(ctx, HEAVY_WORK_SOL, "HeavyWork")
    addr = contract.address

    # Deposit sufficient prefund
    contract.prefund(20000000, ctx.ecdsa_key)
    count = 0
    while count < 30:
        time.sleep(2)
        pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
        if pp >= 20000000:
            break

        count += 1

    assert_tx_success(
        ctx.client.wait_for_receipt(
            ctx.client.send_transaction_auto(
                ctx.ecdsa_key, addr, 7, prefund=20000000
            )
        ), "prefund_heavy_deposit"
    )

    pp_before = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)

    # Heavy computation
    receipt = contract.functions.compute(100).transact(ctx.ecdsa_key, prefund=0)
    assert_tx_success(receipt, "prefund_heavy_compute")
    count = 0
    while count < 30:
        time.sleep(2)
        pp = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
        if pp < 20000000:
            break

        count += 1

    pp_after = get_prefund_balance(ctx, addr, ctx.ecdsa_addr)
    assert_true(pp_after < pp_before, "prefund_heavy_gas_consumed",
                f"Gas consumed: {pp_before - pp_after}")


# ==============================================================================
# Module Runner
# ==============================================================================

def run_all(ctx: SethTestContext):
    print_section("Phase 3A: Gas Prefund Tests")
    run_test(test_prefund_basic_deposit, ctx)
    run_test(test_prefund_multiple_deposits, ctx)
    run_test(test_prefund_gas_consumption, ctx)
    run_test(test_prefund_with_call_deposit, ctx)
    run_test(test_prefund_heavy_gas_usage, ctx)
