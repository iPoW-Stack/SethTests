from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path

from .fixtures import iter_tgz_json
from .rlp import decode_strict


@dataclass(frozen=True)
class BlockchainFixtureSummary:
    files: int
    cases: int
    valid_cases: int
    invalid_cases: int
    blocks: int
    rlp_checked: int
    categories: dict[str, int]


def _strip_0x(v: str) -> str:
    return v[2:] if isinstance(v, str) and v.startswith("0x") else v


def _category(path: str) -> str:
    parts = path.split("/")
    if len(parts) >= 3:
        return f"{parts[1]}/{parts[2]}"
    return "unknown"


def validate_blockchain_inventory(root: Path, limit: int | None = None) -> tuple[BlockchainFixtureSummary, list[str]]:
    errors: list[str] = []
    files = cases = valid_cases = invalid_cases = blocks = rlp_checked = 0
    categories: collections.Counter[str] = collections.Counter()

    for path, data in iter_tgz_json(
        root,
        "fixtures_blockchain_tests.tgz",
        "BlockchainTests/",
        limit=limit,
    ):
        files += 1
        category = _category(path)
        categories[category] += 1
        is_invalid_file = path.startswith("BlockchainTests/InvalidBlocks/")
        if not isinstance(data, dict):
            continue
        for name, fixture in data.items():
            if not isinstance(fixture, dict):
                continue
            cases += 1
            if is_invalid_file:
                invalid_cases += 1
            else:
                valid_cases += 1
            for section in ("blocks", "genesisBlockHeader", "pre"):
                if section not in fixture:
                    errors.append(f"{path}::{name}: missing {section}")
            block_list = fixture.get("blocks", [])
            if not isinstance(block_list, list):
                errors.append(f"{path}::{name}: blocks is not a list")
                continue
            for block in block_list:
                blocks += 1
                rlp = block.get("rlp")
                if not rlp:
                    errors.append(f"{path}::{name}: block missing rlp")
                    continue
                try:
                    decode_strict(bytes.fromhex(_strip_0x(rlp)))
                    rlp_checked += 1
                except Exception as exc:
                    errors.append(f"{path}::{name}: invalid block RLP: {exc}")

    return (
        BlockchainFixtureSummary(
            files=files,
            cases=cases,
            valid_cases=valid_cases,
            invalid_cases=invalid_cases,
            blocks=blocks,
            rlp_checked=rlp_checked,
            categories=dict(categories),
        ),
        errors,
    )
