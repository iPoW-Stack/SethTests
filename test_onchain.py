# On-chain State Tests wrapper
# Runs the existing test scripts from BlockchainTests/StateTests/ and GenesisTests/
# as subprocesses and records results in the unified test tracker.
from __future__ import annotations
import concurrent.futures
import subprocess, sys, os

from utils import SethTestContext, print_section, results
import config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# On-chain test scripts that need SETH_HOST
# Note: GenesisTests and VMTests are handled by test_genesis.py and test_vm_opcodes.py
# natively, so they are NOT included here to avoid double-running.
ONCHAIN_TESTS = [
    ("BlockchainTests/StateTests/test_create2.py", "create2"),
    ("BlockchainTests/StateTests/test_revert.py", "revert"),
    ("BlockchainTests/StateTests/test_call_codes.py", "call_codes"),
    ("BlockchainTests/StateTests/test_precompiles.py", "precompiles"),
    ("BlockchainTests/StateTests/test_storage.py", "storage"),
    ("BlockchainTests/StateTests/test_log_shift.py", "log_shift"),
    ("BlockchainTests/StateTests/test_code_env.py", "code_env"),
    ("BlockchainTests/StateTests/test_system_ops.py", "system_ops"),
    ("BlockchainTests/StateTests/test_static_delegate.py", "static_delegate"),
    ("BlockchainTests/StateTests/test_memory_stack.py", "memory_stack"),
    ("BlockchainTests/StateTests/test_create_refund.py", "create_refund"),
    ("BlockchainTests/StateTests/test_zero_boundary.py", "zero_boundary"),
    ("BlockchainTests/StateTests/test_attack_badop.py", "attack_badop"),
    ("BlockchainTests/StateTests/test_solidity_codelimit.py", "solidity_codelimit"),
]


def _subprocess_env(private_key: str | None = None) -> dict:
    env = os.environ.copy()
    env["SETH_HOST"] = str(config.SETH_HOST)
    env["SETH_PORT"] = str(config.SETH_PORT)
    env["DEPLOYER_PK"] = private_key or config.TEST_ECDSA_KEY
    existing = env.get("PYTHONPATH", "")
    parts = [SCRIPT_DIR] + ([existing] if existing else [])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def _run_script(rel_path: str, label: str, env: dict):
    """Run a test script as subprocess, return (passed, failed) from output."""
    path = os.path.join(SCRIPT_DIR, rel_path)
    if not os.path.exists(path):
        results.record_skip(f"onchain_{label}", "file not found")
        return

    try:
        r = subprocess.run(
            [sys.executable, path],
            timeout=300,
            capture_output=True,
            text=True,
            env=env,
        )
        # Parse summary line: "Results: X passed, Y failed"
        output = r.stdout + r.stderr
        passed_count = 0
        failed_count = 0
        for line in output.splitlines():
            if "passed" in line and "failed" in line:
                parts = line.strip().split()
                for i, p in enumerate(parts):
                    if p == "passed," and i > 0:
                        try: passed_count = int(parts[i-1])
                        except ValueError: pass
                    if p == "failed" and i > 0:
                        try: failed_count = int(parts[i-1])
                        except ValueError: pass

        if r.returncode == 0:
            # 将子进程中的实际测试数量加到总数中
            # 减去1是因为record_pass本身会加1
            results.add_counts(passed=passed_count - 1 if passed_count > 0 else 0)
            results.record_pass(f"onchain_{label} ({passed_count} passed)")
        else:
            # 记录子进程中的实际通过/失败数量
            results.add_counts(
                passed=passed_count,
                failed=failed_count - 1 if failed_count > 0 else 0,
            )
            results.record_fail(f"onchain_{label}",
                                f"{failed_count} failed, {passed_count} passed, exit={r.returncode}")
            # Print last 20 lines of output for debugging
            lines = output.strip().splitlines()
            for l in lines[-20:]:
                print(f"    {l}")

    except subprocess.TimeoutExpired:
        results.record_fail(f"onchain_{label}", "timeout (300s)")
    except Exception as e:
        results.record_fail(f"onchain_{label}", f"error: {e}")


def run_all(ctx: SethTestContext):
    print_section("On-chain State Tests (subprocess)")
    env = _subprocess_env()

    for rel_path, label in ONCHAIN_TESTS:
        _run_script(rel_path, label, env)


def run_all_concurrent(ctx: SethTestContext, max_workers: int = 4, private_keys: list[str] | None = None):
    print_section("On-chain State Tests (subprocess, concurrent)")
    key_count = len(private_keys) if private_keys else 1
    workers = min(max_workers, len(ONCHAIN_TESTS), key_count)
    print(f"Running {len(ONCHAIN_TESTS)} on-chain scripts with {workers} workers")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _run_script,
                rel_path,
                label,
                _subprocess_env(private_keys[i % len(private_keys)] if private_keys else None),
            )
            for i, (rel_path, label) in enumerate(ONCHAIN_TESTS)
        ]
        concurrent.futures.wait(futures)
