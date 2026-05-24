from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from Crypto.Hash import keccak

from .fixtures import iter_json_files, load_json
from .rlp import decode


PREFERRED_FORKS = ("Prague", "Cancun", "Shanghai", "Paris", "London", "Berlin")


@dataclass(frozen=True)
class TxFixtureResult:
    total: int = 0
    valid: int = 0
    invalid: int = 0
    checked: int = 0


def _strip_0x(v: str) -> str:
    return v[2:] if isinstance(v, str) and v.startswith("0x") else v


def _preferred_result(result: dict) -> dict:
    for fork in PREFERRED_FORKS:
        if fork in result:
            return result[fork]
    return next(iter(result.values()), {})


def _tx_hash(raw_hex: str) -> str:
    raw = bytes.fromhex(_strip_0x(raw_hex))
    return "0x" + keccak.new(digest_bits=256).update(raw).hexdigest()


def _decode_raw_tx(raw_hex: str):
    raw = bytes.fromhex(_strip_0x(raw_hex))
    if raw and raw[0] in (1, 2, 3, 4):
        return decode(raw[1:])
    return decode(raw)


def validate_transaction_tests(root: Path, limit: int | None = None) -> tuple[TxFixtureResult, list[str]]:
    errors: list[str] = []
    total = valid = invalid = checked = 0
    for path in iter_json_files(root, "TransactionTests"):
        data = load_json(path)
        for name, fixture in data.items():
            total += 1
            expected = _preferred_result(fixture.get("result", {}))
            raw = fixture.get("txbytes")
            label = f"{path.relative_to(root)}::{name}"
            if "exception" in expected:
                invalid += 1
                if expected.get("intrinsicGas") == "0x00":
                    checked += 1
                else:
                    errors.append(f"{label}: invalid tx has non-zero intrinsicGas marker")
            else:
                valid += 1
                if not raw:
                    errors.append(f"{label}: valid tx missing txbytes")
                    continue
                got_hash = _tx_hash(raw)
                exp_hash = expected.get("hash")
                if exp_hash and got_hash.lower() != exp_hash.lower():
                    errors.append(f"{label}: hash expected {exp_hash}, got {got_hash}")
                    continue
                # Fork-specific intrinsic gas has changed across hard forks
                # and is not directly Seth-executable yet.  This adapter keeps
                # raw transaction parsing/hash coverage here; live Seth
                # execution is added per supported fixture family.
                _decode_raw_tx(raw)
                checked += 1
            if limit and total >= limit:
                return TxFixtureResult(total, valid, invalid, checked), errors
    return TxFixtureResult(total, valid, invalid, checked), errors
