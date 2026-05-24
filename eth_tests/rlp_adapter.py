from __future__ import annotations

from pathlib import Path

from .fixtures import load_json
from .rlp import decode_strict, encode


def _strip_0x(v: str) -> str:
    return v[2:] if isinstance(v, str) and v.startswith("0x") else v


def _fixture_input(value):
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return [_fixture_input(v) for v in value]
    if isinstance(value, str) and value.startswith("#"):
        return int(value[1:])
    if isinstance(value, str):
        return value.encode("latin1")
    raise TypeError(f"unsupported RLP fixture value: {type(value)!r}")


def validate_rlp_tests(root: Path) -> tuple[int, int, list[str]]:
    errors: list[str] = []
    valid_checked = 0
    invalid_checked = 0

    for rel in ("RLPTests/rlptest.json", "RLPTests/RandomRLPTests/example.json"):
        path = root / rel
        if not path.is_file():
            continue
        for name, item in load_json(path).items():
            expected = _strip_0x(item["out"]).lower()
            if item["in"] == "VALID":
                decode_strict(bytes.fromhex(expected))
                valid_checked += 1
                continue
            got = encode(_fixture_input(item["in"])).hex()
            if got != expected:
                errors.append(f"{rel}::{name}: expected {expected}, got {got}")
            else:
                valid_checked += 1

    invalid = root / "RLPTests" / "invalidRLPTest.json"
    if invalid.is_file():
        for name, item in load_json(invalid).items():
            try:
                decode_strict(bytes.fromhex(_strip_0x(item["out"])))
            except Exception:
                invalid_checked += 1
            else:
                errors.append(f"RLPTests/invalidRLPTest.json::{name}: decoded invalid RLP")

    return valid_checked, invalid_checked, errors
