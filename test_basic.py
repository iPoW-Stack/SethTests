# Basic Tests: Key-Address, Transaction Format, ABI Encoding, Signatures, Boundaries
# Merged from: BasicTests/test_keyaddr.py, BasicTests/test_transaction.py,
#              ABITests/test_abi_encoding.py, TransactionTests/test_signature.py,
#              TransactionTests/test_address_nonce_value.py
from __future__ import annotations
import struct, hashlib

from Crypto.Hash import keccak
from ecdsa import SigningKey, SECP256k1, BadSignatureError
from ecdsa.util import sigencode_string_canonize, sigdecode_string

import eth_abi
from eth_utils import to_checksum_address

from utils import (
    SethTestContext, run_test, assert_equal, assert_true,
    print_section, results,
)

# ==============================================================================
# Helpers & Vectors
# ==============================================================================
KEY_VECTORS = [
    {"seed": "cow",
     "key": "c85ef7d79691fe79573b1a7064c19c1a9819ebdbd1faaab1a8ec92344438aaf4",
     "addr": "cd2a3d9f938e13cd947ec05abc7fe734df8dd826"},
    {"seed": "horse",
     "key": "c87f65ff3f271bf5dc8643484f66b200109caffe4bf98c4cb393dc35740b28c0",
     "addr": "13978aee95f38490e9769c39b2773ed763d9cd5f"},
]
SIG_KEYS = [v["key"] for v in KEY_VECTORS] + [
    "4b6525236a2029ab54e2c6162c483133c1af7d38bd960f85b1f485c31e696b7b",
]

def _addr(pk): 
    sk = SigningKey.from_string(bytes.fromhex(pk), curve=SECP256k1)
    return keccak.new(digest_bits=256).update(sk.verifying_key.to_string("uncompressed")[1:]).digest()[-20:].hex()

def _u64le(v): return struct.pack("<Q", v)

def _tx_hash(pk, to, nonce=1, amount=0, step=0, prefund=0):
    sk = SigningKey.from_string(bytes.fromhex(pk), curve=SECP256k1)
    msg = bytearray()
    msg.extend(_u64le(nonce)); msg.extend(bytes.fromhex(sk.verifying_key.to_string("uncompressed").hex()))
    msg.extend(bytes.fromhex(to)); msg.extend(_u64le(amount)); msg.extend(_u64le(5000000))
    msg.extend(_u64le(1)); msg.extend(_u64le(step))
    if prefund > 0: msg.extend(_u64le(prefund))
    return keccak.new(digest_bits=256).update(msg).digest()

def _sign(pk, h):
    sk = SigningKey.from_string(bytes.fromhex(pk), curve=SECP256k1)
    sig = sk.sign_digest_deterministic(h, hashfunc=hashlib.sha256, sigencode=sigencode_string_canonize)
    return sig[:32], sig[32:64]

# ==============================================================================
# Key-Address Tests
# ==============================================================================
def test_address_derivation(ctx):
    """Private key → address derivation."""
    for v in KEY_VECTORS:
        assert_equal(_addr(v["key"]), v["addr"], f"keyaddr_derive_{v['seed']}")

def test_seth_client_address(ctx):
    """SethClient.get_address() matches."""
    for v in KEY_VECTORS:
        assert_equal(ctx.client.get_address(v["key"]), v["addr"], f"keyaddr_client_{v['seed']}")

def test_signature_deterministic(ctx):
    """Empty string signature is deterministic."""
    for v in KEY_VECTORS:
        sk = SigningKey.from_string(bytes.fromhex(v["key"]), curve=SECP256k1)
        h = keccak.new(digest_bits=256).update(b"").digest()
        s1 = sk.sign_digest_deterministic(h, hashfunc=hashlib.sha256, sigencode=sigencode_string_canonize)
        s2 = sk.sign_digest_deterministic(h, hashfunc=hashlib.sha256, sigencode=sigencode_string_canonize)
        assert_equal(s1.hex(), s2.hex(), f"keyaddr_sig_det_{v['seed']}")

# ==============================================================================
# Transaction Format Tests
# ==============================================================================
def test_tx_hash_deterministic(ctx):
    """Same inputs → same tx hash."""
    for v in KEY_VECTORS:
        h1 = _tx_hash(v["key"], v["addr"], nonce=1, amount=1000)
        h2 = _tx_hash(v["key"], v["addr"], nonce=1, amount=1000)
        assert_equal(h1.hex(), h2.hex(), f"txfmt_hash_det_{v['seed']}")

def test_tx_hash_varies(ctx):
    """Different nonce/amount/step → different hash."""
    v = KEY_VECTORS[0]
    h1 = _tx_hash(v["key"], v["addr"], nonce=1).hex()
    h2 = _tx_hash(v["key"], v["addr"], nonce=2).hex()
    assert_true(h1 != h2, "txfmt_nonce_differs")
    ha = _tx_hash(v["key"], v["addr"], amount=100).hex()
    hb = _tx_hash(v["key"], v["addr"], amount=200).hex()
    assert_true(ha != hb, "txfmt_amount_differs")
    s0 = _tx_hash(v["key"], v["addr"], step=0).hex()
    s6 = _tx_hash(v["key"], v["addr"], step=6).hex()
    assert_true(s0 != s6, "txfmt_step_differs")

def test_tx_sig_deterministic(ctx):
    """Tx signature is deterministic."""
    for v in KEY_VECTORS:
        h = _tx_hash(v["key"], v["addr"], nonce=1, amount=1000, prefund=1000000)
        r1, s1 = _sign(v["key"], h); r2, s2 = _sign(v["key"], h)
        assert_equal(r1.hex(), r2.hex(), f"txfmt_sig_r_{v['seed']}")
        assert_equal(s1.hex(), s2.hex(), f"txfmt_sig_s_{v['seed']}")

# ==============================================================================
# ABI Encoding Tests
# ==============================================================================
def test_abi_single_integer(ctx):
    """Encode single uint256."""
    r = eth_abi.encode(["uint256"], [98127491]).hex()
    assert_equal(r, "0000000000000000000000000000000000000000000000000000000005d94e83", "abi_uint256")

def test_abi_integer_and_address(ctx):
    """Encode uint256 + address."""
    r = eth_abi.encode(["uint256", "address"],
        [324124, to_checksum_address("0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826")]).hex()
    exp = ("000000000000000000000000000000000000000000000000000000000004f21c"
           "000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826")
    assert_equal(r, exp, "abi_uint256_addr")

def test_abi_decode_roundtrip(ctx):
    """Encode then decode round-trip."""
    enc = eth_abi.encode(["uint256"], [12345])
    assert_equal(eth_abi.decode(["uint256"], enc)[0], 12345, "abi_rt_uint256")
    enc = eth_abi.encode(["bool"], [True])
    assert_equal(eth_abi.decode(["bool"], enc)[0], True, "abi_rt_bool")
    enc = eth_abi.encode(["int256"], [-42])
    assert_equal(eth_abi.decode(["int256"], enc)[0], -42, "abi_rt_int256_neg")

def test_abi_function_selector(ctx):
    """Function selector = first 4 bytes of keccak256."""
    for sig, exp in [("transfer(address,uint256)", "a9059cbb"),
                     ("balanceOf(address)", "70a08231"),
                     ("approve(address,uint256)", "095ea7b3")]:
        got = keccak.new(digest_bits=256).update(sig.encode()).digest()[:4].hex()
        assert_equal(got, exp, f"abi_sel_{sig.split('(')[0]}")

# ==============================================================================
# Signature Verification Tests
# ==============================================================================
def test_sig_valid_recovery(ctx):
    """Sign and verify with public key."""
    for pk in SIG_KEYS:
        h = _tx_hash(pk, _addr(pk), nonce=1, amount=100)
        r, s = _sign(pk, h)
        vk = SigningKey.from_string(bytes.fromhex(pk), curve=SECP256k1).verifying_key
        try:
            vk.verify_digest(r + s, h, sigdecode=sigdecode_string)
            assert_true(True, f"sig_valid_{pk[:8]}")
        except BadSignatureError:
            assert_true(False, f"sig_valid_{pk[:8]}")

def test_sig_wrong_key_fails(ctx):
    """Signature from wrong key fails verification."""
    pk1, pk2 = SIG_KEYS[0], SIG_KEYS[1]
    h = _tx_hash(pk1, _addr(pk1))
    r, s = _sign(pk1, h)
    vk2 = SigningKey.from_string(bytes.fromhex(pk2), curve=SECP256k1).verifying_key
    try:
        vk2.verify_digest(r + s, h, sigdecode=sigdecode_string)
        assert_true(False, "sig_wrong_key_rejected")
    except BadSignatureError:
        assert_true(True, "sig_wrong_key_rejected")

def test_sig_components_range(ctx):
    """r and s within secp256k1 order."""
    N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    for pk in SIG_KEYS:
        h = _tx_hash(pk, _addr(pk))
        r, s = _sign(pk, h)
        assert_true(0 < int.from_bytes(r, "big") < N, f"sig_r_range_{pk[:8]}")
        assert_true(0 < int.from_bytes(s, "big") < N, f"sig_s_range_{pk[:8]}")

# ==============================================================================
# Boundary Tests
# ==============================================================================
def test_addr_nonce_value_boundaries(ctx):
    """Address, nonce, and value boundary conditions."""
    pk, addr = KEY_VECTORS[0]["key"], KEY_VECTORS[0]["addr"]
    M = (1 << 64) - 1
    assert_equal(len(addr), 40, "boundary_addr_len")
    assert_true(len(_tx_hash(pk, "0"*40).hex()) == 64, "boundary_zero_addr")
    assert_true(len(_tx_hash(pk, "f"*40).hex()) == 64, "boundary_max_addr")
    hashes = {_tx_hash(pk, addr, nonce=n).hex() for n in [0,1,2,100,999999,M]}
    assert_equal(len(hashes), 6, "boundary_6_nonces_unique")
    hashes = {_tx_hash(pk, addr, amount=a).hex() for a in [0,1,100,1000000,M]}
    assert_equal(len(hashes), 5, "boundary_5_amounts_unique")

# ==============================================================================
# Module Runner
# ==============================================================================
def run_all(ctx: SethTestContext):
    print_section("Basic Tests: Key-Address, Tx Format, ABI, Signatures, Boundaries")
    run_test(test_address_derivation, ctx)
    run_test(test_seth_client_address, ctx)
    run_test(test_signature_deterministic, ctx)
    run_test(test_tx_hash_deterministic, ctx)
    run_test(test_tx_hash_varies, ctx)
    run_test(test_tx_sig_deterministic, ctx)
    run_test(test_abi_single_integer, ctx)
    run_test(test_abi_integer_and_address, ctx)
    run_test(test_abi_decode_roundtrip, ctx)
    run_test(test_abi_function_selector, ctx)
    run_test(test_sig_valid_recovery, ctx)
    run_test(test_sig_wrong_key_fails, ctx)
    run_test(test_sig_components_range, ctx)
    run_test(test_addr_nonce_value_boundaries, ctx)
