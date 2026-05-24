from __future__ import annotations

from pathlib import Path

from Crypto.Cipher import AES

from .fixtures import load_json


def encode_hex_prefix(seq: list[int], term: bool) -> str:
    nibbles = list(seq) + ([16] if term else [])
    odd = len(nibbles) % 2
    flags = 2 * int(term) + odd
    if odd:
        prefixed = [flags] + nibbles
    else:
        prefixed = [flags, 0] + nibbles
    out = bytearray()
    for i in range(0, len(prefixed), 2):
        out.append((prefixed[i] << 4) | prefixed[i + 1])
    return out.hex()


def validate_hex_prefix_tests(root: Path) -> list[str]:
    errors: list[str] = []
    data = load_json(root / "BasicTests" / "hexencodetest.json")
    for name, item in data.items():
        got = encode_hex_prefix(item["seq"], bool(item["term"]))
        if got != item["out"].lower():
            errors.append(f"{name}: expected {item['out']}, got {got}")
    return errors


def validate_crypto_tests(root: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    checked = 0
    data = load_json(root / "BasicTests" / "crypto.json")
    for name, item in data.items():
        if item.get("decryption_type") != "aes_ctr":
            continue
        key = bytes.fromhex(item["key"])
        cipher = bytes.fromhex(item["cipher"])
        # The legacy test vector uses AES-CTR with zero initial counter.
        aes = AES.new(key, AES.MODE_CTR, nonce=b"", initial_value=0)
        got = aes.decrypt(cipher).hex()
        if got != item["payload"].lower():
            errors.append(f"{name}: expected {item['payload']}, got {got}")
        checked += 1
    return checked, errors

