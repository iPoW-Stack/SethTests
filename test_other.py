# Other Tests wrapper
# Runs the test scripts from other_tests/ as subprocesses
# and records results in the unified test tracker.
#
# Tests included:
#   - amm: AMM Multi-User Atomic Swap Demo (single-pool)
#   - amm_multi: Multi-Shard AMM (6 tokens, 15 pools, parallel execution)
#   - amm_cross: Cross-Shard AMM Swap via Output Relay
#   - cross_shard_call: Cross-Shard Contract-to-Contract Call
#   - eip1559: EIP-1559 Transaction Tests
#   - contract_chain: Contract Chain Same-Shard/Pool Demo
from __future__ import annotations
import concurrent.futures
import subprocess, sys, os

from utils import SethTestContext, print_section, results
from config import SETH_HOST, SETH_PORT, TEST_ECDSA_KEY

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# other_tests scripts with their arguments
OTHER_TESTS = [
    # (script_path, label, extra_args, timeout_seconds)
    ("other_tests/test_eip1559.py", "eip1559", [], 120),
    ("other_tests/test_cross_shard_call.py", "cross_shard_call", [], 600),
    ("other_tests/test_contract_chain_demo.py", "contract_chain", [], 600),
    ("other_tests/amm.py", "amm_user1", ["--users", "1"], 540),
    ("other_tests/amm.py", "amm_user2", ["--users", "1"], 540),
    ("other_tests/seth3.py", "seth3_ws", ["--case", "ws"], 300),
    ("other_tests/seth3.py", "seth3_ecdsa_core", ["--case", "ecdsa_core"], 540),
    ("other_tests/seth3.py", "seth3_ecdsa_contracts", ["--case", "ecdsa_contracts"], 540),
    ("other_tests/seth3.py", "seth3_ecdsa_iweth", ["--case", "ecdsa_iweth"], 360),
    ("other_tests/seth3.py", "seth3_ecdsa_misc", ["--case", "ecdsa_misc"], 360),
    ("other_tests/seth3.py", "seth3_oqs", ["--case", "oqs"], 300),
    ("other_tests/seth3.py", "seth3_gmssl", ["--case", "gmssl"], 240),
]


def _run_other_script(rel_path: str, label: str, extra_args: list, timeout: int, env: dict, private_key: str | None = None):
    """Run a test script from other_tests/ as subprocess."""
    import config
    import time
    path = os.path.join(SCRIPT_DIR, rel_path)
    if not os.path.exists(path):
        results.record_skip(f"other_{label}", "file not found")
        return

    try:
        # seth3.py reads host/port/key from env and supports --case splitting.
        if label.startswith("seth3"):
            cmd = [sys.executable, path] + extra_args
        else:
            key = private_key or config.TEST_ECDSA_KEY
            cmd = [sys.executable, path,
                   "--host", str(config.SETH_HOST),
                   "--port", str(config.SETH_PORT),
                   "--key", key] + extra_args

        print(f"  ▶ other_{label}: start ({os.path.basename(rel_path)} {' '.join(extra_args)})")
        started = time.time()
        r = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=env,
        )
        elapsed = time.time() - started

        output = r.stdout + r.stderr

        # Count ✅ and ❌ in output lines to get per-test-case counts
        passed_count = 0
        failed_count = 0
        for line in output.splitlines():
            # Count ✅ PASS / ✅ SUCCESS / ✅ <anything>
            if "✅" in line:
                passed_count += 1
            # Count ❌ FAIL / ❌ FAILED / ❌ <anything>
            if "❌" in line:
                failed_count += 1

        # Also try to parse "X/Y tests passed" or "X passed, Y failed" patterns
        for line in output.splitlines():
            if "tests passed" in line.lower():
                parts = line.strip().split()
                for p in parts:
                    if "/" in p:
                        try:
                            p_count, total = p.split("/")
                            passed_count = int(p_count)
                            failed_count = int(total) - passed_count
                        except ValueError:
                            pass
            if "passed" in line and "failed" in line and "Results:" in line:
                parts = line.strip().split()
                for i, p in enumerate(parts):
                    if p == "passed," and i > 0:
                        try: passed_count = int(parts[i-1])
                        except ValueError: pass
                    if p == "failed" and i > 0:
                        try: failed_count = int(parts[i-1])
                        except ValueError: pass

        total_count = passed_count + failed_count

        if r.returncode == 0:
            detail = f"{passed_count} passed, {elapsed:.1f}s" if total_count > 0 else f"ok, {elapsed:.1f}s"
            # Add extra counts beyond the 1 that record_pass will add
            if passed_count > 1:
                results.add_counts(passed=passed_count - 1)
            results.record_pass(f"other_{label} ({detail})")
        else:
            detail = f"{failed_count} failed, {passed_count} passed, exit={r.returncode}, {elapsed:.1f}s"
            if passed_count > 0:
                results.add_counts(passed=passed_count)
            if failed_count > 1:
                results.add_counts(failed=failed_count - 1)
            results.record_fail(f"other_{label}", detail)
            # Print last 30 lines of output for debugging
            lines = output.strip().splitlines()
            for l in lines[-30:]:
                print(f"    {l}")

    except subprocess.TimeoutExpired:
        results.record_fail(f"other_{label}", f"timeout ({timeout}s)")
    except Exception as e:
        results.record_fail(f"other_{label}", f"error: {e}")


def run_all(ctx: SethTestContext):
    print_section("Other Tests (subprocess)")
    # Import config directly to get the latest values (may be modified by seth_test_runner)
    import config
    env = os.environ.copy()
    env["SETH_HOST"] = str(config.SETH_HOST)
    env["SETH_PORT"] = str(config.SETH_PORT)
    env["DEPLOYER_PK"] = config.TEST_ECDSA_KEY
    # Ensure other_tests/ can find seth_sdk.py
    other_dir = os.path.join(SCRIPT_DIR, "other_tests")
    env["PYTHONPATH"] = other_dir + os.pathsep + env.get("PYTHONPATH", "")

    for rel_path, label, extra_args, timeout in OTHER_TESTS:
        _run_other_script(rel_path, label, extra_args, timeout, env)


def run_all_concurrent(ctx: SethTestContext, max_workers: int = 4, private_keys: list[str] | None = None):
    print_section("Other Tests (subprocess, concurrent)")
    # Import config directly to get the latest values (may be modified by seth_test_runner)
    import config
    env = os.environ.copy()
    env["SETH_HOST"] = str(config.SETH_HOST)
    env["SETH_PORT"] = str(config.SETH_PORT)
    # Ensure other_tests/ can find seth_sdk.py
    other_dir = os.path.join(SCRIPT_DIR, "other_tests")
    env["PYTHONPATH"] = other_dir + os.pathsep + env.get("PYTHONPATH", "")

    workers = min(max_workers, len(OTHER_TESTS))
    print(f"Running {len(OTHER_TESTS)} other scripts with {workers} workers")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _run_other_script,
                rel_path,
                label,
                extra_args,
                timeout,
                {**env, "DEPLOYER_PK": private_keys[i % len(private_keys)] if private_keys else config.TEST_ECDSA_KEY},
                private_keys[i % len(private_keys)] if private_keys else None,
            )
            for i, (rel_path, label, extra_args, timeout) in enumerate(OTHER_TESTS)
        ]
        concurrent.futures.wait(futures)
