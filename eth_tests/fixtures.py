from __future__ import annotations

import json
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


DEFAULT_ROOTS = (
    os.environ.get("ETHEREUM_TESTS_ROOT"),
    "/tmp/ethereum-tests",
    "/tmp/ethereum-tests-sparse",
    str(Path(__file__).resolve().parents[1] / "ethereum-tests"),
)


@dataclass(frozen=True)
class FixtureRef:
    suite: str
    name: str
    path: str
    source: str


def find_ethereum_tests_root() -> Path | None:
    for candidate in DEFAULT_ROOTS:
        if not candidate:
            continue
        root = Path(candidate).expanduser()
        if (root / "BasicTests").is_dir() or (root / "fixtures_general_state_tests.tgz").is_file():
            return root
    return None


def require_ethereum_tests_root() -> Path:
    root = find_ethereum_tests_root()
    if root is None:
        raise FileNotFoundError(
            "ethereum/tests fixtures not found. Set ETHEREUM_TESTS_ROOT=/path/to/ethereum/tests "
            "or clone https://github.com/ethereum/tests to /tmp/ethereum-tests."
        )
    return root


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_json_files(root: Path, rel_dir: str) -> Iterator[Path]:
    base = root / rel_dir
    if not base.is_dir():
        return
    yield from sorted(base.rglob("*.json"))


def iter_tgz_members(root: Path, archive_name: str, prefix: str) -> Iterator[FixtureRef]:
    archive = root / archive_name
    if not archive.is_file():
        return
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf:
            if member.isfile() and member.name.startswith(prefix) and member.name.endswith(".json"):
                name = Path(member.name).stem
                yield FixtureRef(prefix.rstrip("/"), name, member.name, archive_name)


def iter_tgz_json(root: Path, archive_name: str, prefix: str, limit: int | None = None):
    archive = root / archive_name
    if not archive.is_file():
        return
    seen = 0
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf:
            if not (member.isfile() and member.name.startswith(prefix) and member.name.endswith(".json")):
                continue
            f = tf.extractfile(member)
            if f is None:
                continue
            yield member.name, json.load(f)
            seen += 1
            if limit and seen >= limit:
                return


def iter_fixture_inventory(root: Path) -> Iterator[FixtureRef]:
    for suite in ("BasicTests", "TransactionTests", "RLPTests", "BlockchainTests"):
        for path in iter_json_files(root, suite):
            yield FixtureRef(suite, path.stem, str(path.relative_to(root)), "directory")

    general_state_dir = root / "GeneralStateTests"
    if general_state_dir.is_dir():
        for path in sorted(general_state_dir.rglob("*.json")):
            yield FixtureRef("GeneralStateTests", path.stem, str(path.relative_to(root)), "directory")

    yield from iter_tgz_members(
        root,
        "fixtures_general_state_tests.tgz",
        "GeneralStateTests/",
    )
    yield from iter_tgz_members(
        root,
        "fixtures_blockchain_tests.tgz",
        "BlockchainTests/",
    )
