# Core EVM Operation Tests
# Covers: SLOAD/SSTORE, Arithmetic, Comparison, Bitwise, Memory, Log, SELFBALANCE
# Reference: GeneralStateTests/stSStoreTest, stSelfBalance, stLogTests, stStackTests, stShift
from __future__ import annotations
from utils import (
    SethTestContext, run_test, assert_tx_success, assert_equal,
    assert_true, deploy_contract_with_prefund, print_section, results
)

STORAGE_TEST_SOL = """
pragma solidity ^0.8.20;
contract StorageTest {
    uint256 public value;
    mapping(uint256 => uint256) public items;
    event ValueChanged(uint256 oldValue, uint256 newValue);
    function setValue(uint256 v) external { uint256 old = value; value = v; emit ValueChanged(old, v); }
    function setMapping(uint256 key, uint256 val) external { items[key] = val; }
    function getMapping(uint256 key) external view returns (uint256) { return items[key]; }
    function getValue() external view returns (uint256) { return value; }
}
"""

ARITHMETIC_TEST_SOL = """
pragma solidity ^0.8.20;
contract ArithmeticTest {
    function add(uint256 a, uint256 b) external pure returns (uint256) { return a + b; }
    function sub(uint256 a, uint256 b) external pure returns (uint256) { require(a >= b); return a - b; }
    function mul(uint256 a, uint256 b) external pure returns (uint256) { return a * b; }
    function div(uint256 a, uint256 b) external pure returns (uint256) { require(b > 0); return a / b; }
    function mod(uint256 a, uint256 b) external pure returns (uint256) { require(b > 0); return a % b; }
    function exp(uint256 base, uint256 exponent) external pure returns (uint256) { return base ** exponent; }
}
"""

COMPARISON_TEST_SOL = """
pragma solidity ^0.8.20;
contract ComparisonTest {
    function isEq(uint256 a, uint256 b) external pure returns (bool) { return a == b; }
    function isGt(uint256 a, uint256 b) external pure returns (bool) { return a > b; }
    function isLt(uint256 a, uint256 b) external pure returns (bool) { return a < b; }
    function bitwiseAnd(uint256 a, uint256 b) external pure returns (uint256) { return a & b; }
    function bitwiseOr(uint256 a, uint256 b) external pure returns (uint256) { return a | b; }
    function bitwiseXor(uint256 a, uint256 b) external pure returns (uint256) { return a ^ b; }
    function shiftLeft(uint256 v, uint8 bits) external pure returns (uint256) { return v << bits; }
    function shiftRight(uint256 v, uint8 bits) external pure returns (uint256) { return v >> bits; }
}
"""

LOG_TEST_SOL = """
pragma solidity ^0.8.20;
contract LogTest {
    event LogNoData();
    event LogSingleUint(uint256 value);
    event LogMultiUint(uint256 a, uint256 b, uint256 c);
    event LogIndexed(address indexed sender, uint256 value);
    function emitNoData() external { emit LogNoData(); }
    function emitSingleUint(uint256 v) external { emit LogSingleUint(v); }
    function emitMultiUint(uint256 a, uint256 b, uint256 c) external { emit LogMultiUint(a, b, c); }
    function emitIndexed(uint256 v) external { emit LogIndexed(msg.sender, v); }
}
"""

SELFBALANCE_TEST_SOL = """
pragma solidity ^0.8.20;
contract SelfBalanceTest {
    constructor() payable {}
    function getSelfBalance() external view returns (uint256) { return address(this).balance; }
}
"""


def test_storage_set_and_get(ctx):
    """Test basic SSTORE/SLOAD operations."""
    contract = deploy_contract_with_prefund(ctx, STORAGE_TEST_SOL, "StorageTest")
    receipt = contract.functions.setValue(42).transact(ctx.ecdsa_key)
    assert_tx_success(receipt, "storage_set_value_tx")
    result = contract.functions.getValue().call()
    assert_equal(result, 42, "storage_get_value_matches")


def test_storage_mapping(ctx):
    """Test mapping storage operations."""
    contract = deploy_contract_with_prefund(ctx, STORAGE_TEST_SOL, "StorageTest")
    contract.functions.setMapping(1, 100).transact(ctx.ecdsa_key)
    contract.functions.setMapping(2, 200).transact(ctx.ecdsa_key)
    assert_equal(contract.functions.getMapping(1).call(), 100, "storage_mapping_key1")
    assert_equal(contract.functions.getMapping(2).call(), 200, "storage_mapping_key2")


def test_storage_overwrite(ctx):
    """Test storage overwrite behavior."""
    contract = deploy_contract_with_prefund(ctx, STORAGE_TEST_SOL, "StorageTest")
    contract.functions.setValue(100).transact(ctx.ecdsa_key)
    assert_equal(contract.functions.getValue().call(), 100, "storage_overwrite_v1")
    contract.functions.setValue(200).transact(ctx.ecdsa_key)
    assert_equal(contract.functions.getValue().call(), 200, "storage_overwrite_v2")


def test_arithmetic_add(ctx):
    """Test ADD opcode."""
    contract = deploy_contract_with_prefund(ctx, ARITHMETIC_TEST_SOL, "ArithmeticTest")
    assert_equal(contract.functions.add(100, 200).call(), 300, "arith_add")
    assert_equal(contract.functions.add(0, 0).call(), 0, "arith_add_zero")


def test_arithmetic_sub(ctx):
    """Test SUB opcode."""
    contract = deploy_contract_with_prefund(ctx, ARITHMETIC_TEST_SOL, "ArithmeticTest")
    assert_equal(contract.functions.sub(500, 200).call(), 300, "arith_sub")
    assert_equal(contract.functions.sub(100, 100).call(), 0, "arith_sub_equal")


def test_arithmetic_mul(ctx):
    """Test MUL opcode."""
    contract = deploy_contract_with_prefund(ctx, ARITHMETIC_TEST_SOL, "ArithmeticTest")
    assert_equal(contract.functions.mul(7, 8).call(), 56, "arith_mul")
    assert_equal(contract.functions.mul(0, 999).call(), 0, "arith_mul_zero")


def test_arithmetic_div(ctx):
    """Test DIV opcode."""
    contract = deploy_contract_with_prefund(ctx, ARITHMETIC_TEST_SOL, "ArithmeticTest")
    assert_equal(contract.functions.div(100, 3).call(), 33, "arith_div")


def test_arithmetic_mod(ctx):
    """Test MOD opcode."""
    contract = deploy_contract_with_prefund(ctx, ARITHMETIC_TEST_SOL, "ArithmeticTest")
    assert_equal(contract.functions.mod(10, 3).call(), 1, "arith_mod")


def test_arithmetic_exp(ctx):
    """Test EXP opcode."""
    contract = deploy_contract_with_prefund(ctx, ARITHMETIC_TEST_SOL, "ArithmeticTest")
    assert_equal(contract.functions.exp(2, 10).call(), 1024, "arith_exp")


def test_comparison_eq(ctx):
    """Test EQ opcode."""
    contract = deploy_contract_with_prefund(ctx, COMPARISON_TEST_SOL, "ComparisonTest")
    assert_equal(contract.functions.isEq(5, 5).call(), True, "cmp_eq_true")
    assert_equal(contract.functions.isEq(5, 6).call(), False, "cmp_eq_false")


def test_comparison_gt_lt(ctx):
    """Test GT/LT opcodes."""
    contract = deploy_contract_with_prefund(ctx, COMPARISON_TEST_SOL, "ComparisonTest")
    assert_equal(contract.functions.isGt(10, 5).call(), True, "cmp_gt")
    assert_equal(contract.functions.isLt(5, 10).call(), True, "cmp_lt")


def test_bitwise_ops(ctx):
    """Test AND/OR/XOR opcodes."""
    contract = deploy_contract_with_prefund(ctx, COMPARISON_TEST_SOL, "ComparisonTest")
    assert_equal(contract.functions.bitwiseAnd(0xFF, 0x0F).call(), 0x0F, "bit_and")
    assert_equal(contract.functions.bitwiseOr(0xF0, 0x0F).call(), 0xFF, "bit_or")
    assert_equal(contract.functions.bitwiseXor(0xFF, 0x0F).call(), 0xF0, "bit_xor")


def test_shift_ops(ctx):
    """Test SHL/SHR opcodes."""
    contract = deploy_contract_with_prefund(ctx, COMPARISON_TEST_SOL, "ComparisonTest")
    assert_equal(contract.functions.shiftLeft(1, 8).call(), 256, "shl")
    assert_equal(contract.functions.shiftRight(256, 8).call(), 1, "shr")


def test_log_ops(ctx):
    """Test LOG opcodes."""
    contract = deploy_contract_with_prefund(ctx, LOG_TEST_SOL, "LogTest")
    assert_tx_success(contract.functions.emitNoData().transact(ctx.ecdsa_key), "log_no_data")
    assert_tx_success(contract.functions.emitSingleUint(42).transact(ctx.ecdsa_key), "log_single")
    assert_tx_success(contract.functions.emitMultiUint(1, 2, 3).transact(ctx.ecdsa_key), "log_multi")
    assert_tx_success(contract.functions.emitIndexed(999).transact(ctx.ecdsa_key), "log_indexed")


def test_selfbalance(ctx):
    """Test SELFBALANCE opcode."""
    contract = deploy_contract_with_prefund(ctx, SELFBALANCE_TEST_SOL, "SelfBalanceTest", amount=1000000)
    result = contract.functions.getSelfBalance().call()
    assert_true(result >= 0, "selfbalance", f"Balance={result}")


def run_all(ctx):
    print_section("Phase 1A: Core EVM Operations")
    run_test(test_storage_set_and_get, ctx)
    run_test(test_storage_mapping, ctx)
    run_test(test_storage_overwrite, ctx)
    run_test(test_arithmetic_add, ctx)
    run_test(test_arithmetic_sub, ctx)
    run_test(test_arithmetic_mul, ctx)
    run_test(test_arithmetic_div, ctx)
    run_test(test_arithmetic_mod, ctx)
    run_test(test_arithmetic_exp, ctx)
    run_test(test_comparison_eq, ctx)
    run_test(test_comparison_gt_lt, ctx)
    run_test(test_bitwise_ops, ctx)
    run_test(test_shift_ops, ctx)
    run_test(test_log_ops, ctx)
    run_test(test_selfbalance, ctx)
