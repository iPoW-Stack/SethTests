# Contract Deployment & Interaction Tests
from __future__ import annotations
import time
from utils import (
    SethTestContext, run_test, assert_tx_success, assert_equal,
    assert_true, deploy_contract, deploy_contract_with_prefund,
    print_section, results
)
from seth_sdk import StepType, compile_and_link

COUNTER_SOL = """
pragma solidity ^0.8.20;
contract Counter {
    uint256 public count;
    constructor(uint256 initial) { count = initial; }
    function increment() external { count += 1; }
    function decrement() external { require(count > 0); count -= 1; }
    function reset() external { count = 0; }
}
"""

CALLEE_SOL = """
pragma solidity ^0.8.20;
contract Callee {
    uint256 public value;
    function setValue(uint256 v) external { value = v; }
    function getValue() external view returns (uint256) { return value; }
    function addAndStore(uint256 a, uint256 b) external returns (uint256) {
        uint256 r = a + b; value = r; return r;
    }
}
"""

CALLER_SOL = """
pragma solidity ^0.8.20;
contract Caller {
    function callSetValue(address target, uint256 v) external returns (bool) {
        (bool ok, ) = target.call(abi.encodeWithSignature("setValue(uint256)", v));
        return ok;
    }
    function callAddAndStore(address target, uint256 a, uint256 b) external returns (uint256) {
        (bool ok, bytes memory ret) = target.call(abi.encodeWithSignature("addAndStore(uint256,uint256)", a, b));
        require(ok); return abi.decode(ret, (uint256));
    }
}
"""

PROXY_SOL = """
pragma solidity ^0.8.20;
contract Implementation {
    uint256 public num;
    function setNum(uint256 v) external { num = v; }
    function increment() external { num += 1; }
}
contract Proxy {
    address public implementation;
    constructor(address impl) { implementation = impl; }
    function delegateSetNum(uint256 v) external returns (bool) {
        (bool ok, ) = implementation.delegatecall(abi.encodeWithSignature("setNum(uint256)", v));
        return ok;
    }
    function delegateIncrement() external returns (bool) {
        (bool ok, ) = implementation.delegatecall(abi.encodeWithSignature("increment()"));
        return ok;
    }
}
"""

REVERT_SOL = """
pragma solidity ^0.8.20;
contract RevertTest {
    uint256 public value;
    function shouldRevert() external pure { require(false, "Intentional"); }
    function setValueIfPositive(uint256 v) external { require(v > 0, "Must be positive"); value = v; }
}
"""

def test_contract_deploy_constructor(ctx):
    """Test contract deployment with constructor args."""
    contract = deploy_contract_with_prefund(ctx, COUNTER_SOL, "Counter", args=[42])
    assert_equal(contract.functions.count().call(), 42, "deploy_constructor")

def test_contract_increment_decrement(ctx):
    """Test state mutation via increment/decrement."""
    contract = deploy_contract_with_prefund(ctx, COUNTER_SOL, "Counter", args=[10])
    contract.functions.increment().transact(ctx.ecdsa_key)
    assert_equal(contract.functions.count().call(), 11, "after_increment")
    contract.functions.decrement().transact(ctx.ecdsa_key)
    assert_equal(contract.functions.count().call(), 10, "after_decrement")

def test_contract_reset(ctx):
    """Test reset function."""
    contract = deploy_contract_with_prefund(ctx, COUNTER_SOL, "Counter", args=[100])
    contract.functions.reset().transact(ctx.ecdsa_key)
    assert_equal(contract.functions.count().call(), 0, "after_reset")

def test_cross_contract_call(ctx):
    """Test cross-contract CALL operation."""
    from eth_utils import to_checksum_address
    callee = deploy_contract_with_prefund(ctx, CALLEE_SOL, "Callee")
    caller = deploy_contract_with_prefund(ctx, CALLER_SOL, "Caller")
    caller.functions.callSetValue(to_checksum_address(callee.address), 12345).transact(ctx.ecdsa_key)
    assert_equal(callee.functions.getValue().call(), 12345, "cross_call_value")

def test_delegatecall(ctx):
    """Test DELEGATECALL for proxy pattern."""
    from eth_utils import to_checksum_address
    impl = deploy_contract_with_prefund(ctx, PROXY_SOL, "Implementation")
    proxy = deploy_contract_with_prefund(ctx, PROXY_SOL, "Proxy", args=[to_checksum_address(impl.address)])
    receipt = proxy.functions.delegateSetNum(42).transact(ctx.ecdsa_key)
    assert_tx_success(receipt, "delegatecall_set")
    receipt = proxy.functions.delegateIncrement().transact(ctx.ecdsa_key)
    assert_tx_success(receipt, "delegatecall_inc")

def test_revert_handling(ctx):
    """Test contract revert behavior."""
    contract = deploy_contract_with_prefund(ctx, REVERT_SOL, "RevertTest")
    receipt = contract.functions.shouldRevert().transact(ctx.ecdsa_key)
    assert_true(receipt.get("status") != 0, "revert_expected_fail")
    receipt = contract.functions.setValueIfPositive(10).transact(ctx.ecdsa_key)
    assert_tx_success(receipt, "revert_set_positive")

def run_all(ctx):
    print_section("Phase 1B: Contract Deployment & Interaction")
    run_test(test_contract_deploy_constructor, ctx)
    run_test(test_contract_increment_decrement, ctx)
    run_test(test_contract_reset, ctx)
    run_test(test_cross_contract_call, ctx)
    run_test(test_delegatecall, ctx)
    run_test(test_revert_handling, ctx)