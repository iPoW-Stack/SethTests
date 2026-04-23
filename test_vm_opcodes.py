# VM Opcode Tests (on-chain)
# Merged from: BlockchainTests/VMTests/test_vm_opcodes.py
# Adapted to use SethTestContext with ctx.ecdsa_key.
from __future__ import annotations
import os, secrets, time

import eth_abi
import solcx
from solcx import compile_source, install_solc
from Crypto.Hash import keccak

from seth_sdk import StepType
from utils import (
    SethTestContext, run_test, assert_equal, assert_true,
    print_section, results,
)

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "BlockchainTests", "VMTests")

def _sel(sig):
    return keccak.new(digest_bits=256).update(sig.encode()).digest()[:4].hex()

def _decode_uint(raw):
    txt = (raw or "").strip().lower().replace("0x", "")
    if len(txt) < 64: return 0
    return int(txt[-64:], 16)

def _decode_bool(raw): return _decode_uint(raw) != 0

def _decode_addr(raw):
    txt = (raw or "").strip().lower().replace("0x", "")
    if len(txt) >= 64: return txt[-40:]
    return txt

def _calc_create2(deployer, salt, code):
    d = bytes.fromhex(deployer); s = bytes.fromhex(salt.zfill(64)); c = bytes.fromhex(code)
    kc = keccak.new(digest_bits=256); kc.update(c)
    kf = keccak.new(digest_bits=256); kf.update(b"\xff" + d + s + kc.digest())
    return kf.digest()[-20:].hex()

def test_vm_opcodes(ctx: SethTestContext):
    """Deploy VMTestContract and test EVM opcodes."""
    cli = ctx.client
    pk = ctx.ecdsa_key
    sender = ctx.ecdsa_addr

    # Compile
    try:
        install_solc("0.8.30")
    except Exception as e:
        print(f"  Warning: Could not download solc (network issue?): {e}")
        print("  Attempting to use existing solc installation...")
    solcx.set_solc_version("0.8.30")
    sol_path = os.path.join(SCRIPT_DIR, "VMTestContract.sol")
    if not os.path.exists(sol_path):
        results.record_skip("vm_opcodes", "VMTestContract.sol not found")
        return
    with open(sol_path, "r") as f:
        src = f.read()
    comp = compile_source(src, output_values=["abi", "bin"],
                           solc_version="0.8.30", optimize=True, optimize_runs=200,
                           evm_version="shanghai")
    contract = next(v for k, v in comp.items() if "VMTestContract" in k)
    bytecode = contract["bin"].replace("0x", "").strip()

    # Deploy
    salt = secrets.token_hex(32)  # 生成随机salt避免地址冲突
    addr = _calc_create2(sender, salt, bytecode)
    tx = cli.send_transaction_auto(pk, addr, StepType.kCreateContract,
                                    contract_code=bytecode, prefund=10_000_000)
    rc = cli.wait_for_receipt(tx)
    assert_true(rc and rc.get("status") == 0, "vm_deploy")

    # Prefund
    tx = cli.send_transaction_auto(pk, addr, StepType.kContractGasPrefund, prefund=10_000_000)
    cli.wait_for_receipt(tx)

    def qv(sig, types, args):
        inp = _sel(sig) + eth_abi.encode(types, args).hex()
        return cli.query_contract(sender, addr, inp)

    # Arithmetic
    assert_equal(_decode_uint(qv("testAdd(uint256,uint256)", ["uint256","uint256"], [3,5])), 8, "vm_add")
    assert_equal(_decode_uint(qv("testSub(uint256,uint256)", ["uint256","uint256"], [10,3])), 7, "vm_sub")
    assert_equal(_decode_uint(qv("testMul(uint256,uint256)", ["uint256","uint256"], [6,7])), 42, "vm_mul")
    assert_equal(_decode_uint(qv("testDiv(uint256,uint256)", ["uint256","uint256"], [100,3])), 33, "vm_div")
    assert_equal(_decode_uint(qv("testMod(uint256,uint256)", ["uint256","uint256"], [100,3])), 1, "vm_mod")
    assert_equal(_decode_uint(qv("testExp(uint256,uint256)", ["uint256","uint256"], [2,10])), 1024, "vm_exp")

    # Bitwise
    assert_equal(_decode_uint(qv("testAnd(uint256,uint256)", ["uint256","uint256"], [0xFF,0x0F])), 0x0F, "vm_and")
    assert_equal(_decode_uint(qv("testOr(uint256,uint256)", ["uint256","uint256"], [0xF0,0x0F])), 0xFF, "vm_or")
    assert_equal(_decode_uint(qv("testXor(uint256,uint256)", ["uint256","uint256"], [0xFF,0x0F])), 0xF0, "vm_xor")
    assert_equal(_decode_uint(qv("testShl(uint256,uint256)", ["uint256","uint256"], [4,1])), 16, "vm_shl")
    assert_equal(_decode_uint(qv("testShr(uint256,uint256)", ["uint256","uint256"], [4,256])), 16, "vm_shr")

    # Comparison
    assert_equal(_decode_bool(qv("testLt(uint256,uint256)", ["uint256","uint256"], [3,5])), True, "vm_lt")
    assert_equal(_decode_bool(qv("testGt(uint256,uint256)", ["uint256","uint256"], [5,3])), True, "vm_gt")
    assert_equal(_decode_bool(qv("testEq(uint256,uint256)", ["uint256","uint256"], [42,42])), True, "vm_eq")
    assert_equal(_decode_bool(qv("testIsZero(uint256)", ["uint256"], [0])), True, "vm_iszero_0")
    assert_equal(_decode_bool(qv("testIsZero(uint256)", ["uint256"], [1])), False, "vm_iszero_1")

    # Environment
    assert_equal(_decode_addr(qv("testAddress()", [], [])), addr, "vm_address")

    # Hash
    test_data = b"hello seth"
    expected = keccak.new(digest_bits=256).update(test_data).digest().hex()
    raw = qv("testKeccak256(bytes)", ["bytes"], [test_data])
    raw_hex = (raw or "").strip().lower().replace("0x", "")
    assert_equal(raw_hex[-64:], expected, "vm_keccak256")

    # Storage (needs tx)
    inp = _sel("testSStore(uint256)") + eth_abi.encode(["uint256"], [12345]).hex()
    tx = cli.send_transaction_auto(pk, addr, StepType.kContractExcute,
                                    input_hex=inp, prefund=5_000_000)
    rc = cli.wait_for_receipt(tx)
    assert_true(rc and rc.get("status") == 0, "vm_sstore")
    assert_equal(_decode_uint(cli.query_contract(sender, addr, _sel("testSLoad()"))), 12345, "vm_sload")

    # Log
    inp = _sel("testLog0(uint256)") + eth_abi.encode(["uint256"], [999]).hex()
    tx = cli.send_transaction_auto(pk, addr, StepType.kContractExcute,
                                    input_hex=inp, prefund=5_000_000)
    rc = cli.wait_for_receipt(tx)
    assert_true(rc and rc.get("status") == 0, "vm_log0")
    assert_true(rc and len(rc.get("events", [])) > 0, "vm_log0_events")


def run_all(ctx: SethTestContext):
    print_section("VM Opcode Tests (on-chain)")
    run_test(test_vm_opcodes, ctx)
