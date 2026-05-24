from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path

from .fixtures import iter_tgz_json
from .rlp import decode_strict


CATEGORY_MODULE_MAP = {
    "stSelfBalance": "test_core_evm.test_selfbalance",
    "stStackTests": "test_vm_opcodes",
    "VMTests": "test_vm_opcodes",
    "stSStoreTest": "test_core_evm.test_storage_*",
    "stSLoadTest": "test_core_evm.test_storage_*",
    "stLogTests": "test_core_evm.test_log_ops",
    "stShift": "test_core_evm.test_shift_ops",
    "stCallCodes": "test_contracts / test_onchain.call_codes",
    "stDelegatecallTestHomestead": "test_contracts.test_delegatecall",
    "stRevertTest": "test_contracts / test_onchain.revert",
    "stCreate2": "test_onchain.create2",
    "stCreateTest": "test_onchain.create_refund",
    "stStaticCall": "test_onchain.static_delegate",
    "stPreCompiledContracts": "test_onchain.precompiles",
    "stPreCompiledContracts2": "test_onchain.precompiles",
    "stSystemOperationsTest": "test_onchain.system_ops",
    "stMemoryTest": "test_onchain.memory_stack",
    "stReturnDataTest": "test_onchain.memory_stack",
    "stCodeSizeLimit": "test_onchain.solidity_codelimit",
}


@dataclass(frozen=True)
class StateFixtureSummary:
    files: int
    cases: int
    post_entries: int
    txbytes_checked: int
    mapped_categories: int
    categories: dict[str, int]


def _strip_0x(v: str) -> str:
    return v[2:] if isinstance(v, str) and v.startswith("0x") else v


def _category(path: str) -> str:
    parts = path.split("/")
    return parts[1] if len(parts) > 2 else "unknown"


def validate_general_state_inventory(root: Path, limit: int | None = None) -> tuple[StateFixtureSummary, list[str]]:
    errors: list[str] = []
    files = cases = post_entries = txbytes_checked = 0
    categories: collections.Counter[str] = collections.Counter()

    for path, data in iter_tgz_json(
        root,
        "fixtures_general_state_tests.tgz",
        "GeneralStateTests/",
        limit=limit,
    ):
        files += 1
        category = _category(path)
        categories[category] += 1
        for name, fixture in data.items():
            cases += 1
            for section in ("pre", "post", "transaction", "env"):
                if section not in fixture:
                    errors.append(f"{path}::{name}: missing {section}")
                    continue
            post = fixture.get("post", {})
            if not isinstance(post, dict) or not post:
                errors.append(f"{path}::{name}: missing post forks")
                continue
            for fork, entries in post.items():
                if not isinstance(entries, list):
                    errors.append(f"{path}::{name}: post[{fork}] is not a list")
                    continue
                for entry in entries:
                    post_entries += 1
                    txbytes = entry.get("txbytes")
                    if txbytes:
                        raw = bytes.fromhex(_strip_0x(txbytes))
                        try:
                            if raw and raw[0] in (1, 2, 3, 4):
                                decode_strict(raw[1:])
                            else:
                                decode_strict(raw)
                            txbytes_checked += 1
                        except Exception as exc:
                            errors.append(f"{path}::{name}: invalid txbytes RLP: {exc}")

    mapped_categories = sum(1 for cat in categories if cat in CATEGORY_MODULE_MAP)
    return (
        StateFixtureSummary(
            files=files,
            cases=cases,
            post_entries=post_entries,
            txbytes_checked=txbytes_checked,
            mapped_categories=mapped_categories,
            categories=dict(categories),
        ),
        errors,
    )
