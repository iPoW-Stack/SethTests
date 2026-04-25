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
import subprocess, sys, os

from utils import SethTestContext, print_section, results
from config import SETH_HOST, SETH_PORT, TEST_ECDSA_KEY

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# other_tests scripts with their arguments
OTHER_TESTS = [
    # (script_path, label, extra_args, timeout_seconds)
    ("other_tests/test_eip1559.py", "eip1559", [], 120),
    ("other_tests/test_cross_shard_call.py", "cross_shard_call", [], 300),
    ("other_tests/test_contract_chain_demo.py", "contract_chain", [], 600),
    ("other_tests/amm.py", "amm", ["--users", "2"], 600),
]


def _run_other_script(rel_path: str, label: str, extra_args: list, timeout: int, env: dict):
    """Run a test script from other_tests/ as subprocess."""
    path = os.path.join(SCRIPT_DIR, rel_path)
    if not os.path.exists(path):
        results.record_skip(f"other_{label}", "file not found")
        return

    try:
        cmd = [sys.executable, path,
               "--host", str(SETH_HOST),
               "--port", str(SETH_PORT),
               "--key", TEST_ECDSA_KEY] + extra_args

        r = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=env,
        )

        output = r.stdout + r.stderr

        # Try to parse "X/Y tests passed" or "X passed, Y failed" patterns
        passed_count = 0
        failed_count = 0
        for line in output.splitlines():
            # Pattern: "Total: X/Y tests passed"
            if "tests passed" in line.lower():
                parts = line.strip().split()
                for p in parts:
                    if "/" in p:
                        try:
                            passed_count, total = p.split("/")
                            passed_count = int(passed_count)
                            failed_count = int(total) - passed_count
                        except ValueError:
                            pass
            # Pattern: "X passed, Y failed"
            if "passed" in line and "failed" in line:
                parts = line.strip().split()
                for i, p in enumerate(parts):
                    if p == "passed," and i > 0:
                        try: passed_count = int(parts[i-1])
                        except ValueError: pass
                    if p == "failed" and i > 0:
                        try: failed_count = int(parts[i-1])
                        except ValueError: pass

        # Check for PASSED/FAILED keywords in output
        output_upper = output.upper()
        has_passed = "PASSED" in output_upper or "PASS" in output_upper
        has_failed = "FAILED" in output_upper or "FAIL" in output_upper

        if r.returncode == 0:
            detail = f"{passed_count} passed" if passed_count > 0 else "ok"
            if passed_count > 1:
                results.passed += passed_count - 1
            results.record_pass(f"other_{label} ({detail})")
        else:
            detail = f"{failed_count} failed, {passed_count} passed, exit={r.returncode}"
            if passed_count > 0:
                results.passed += passed_count
            if failed_count > 1:
                results.failed += failed_count - 1
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
    env = os.environ.copy()
    env["SETH_HOST"] = str(SETH_HOST)
    env["SETH_PORT"] = str(SETH_PORT)
    env["DEPLOYER_PK"] = TEST_ECDSA_KEY
    # Ensure other_tests/ can find seth_sdk.py
    other_dir = os.path.join(SCRIPT_DIR, "other_tests")
    env["PYTHONPATH"] = other_dir + os.pathsep + env.get("PYTHONPATH", "")

    for rel_path, label, extra_args, timeout in OTHER_TESTS:
        _run_other_script(rel_path, label, extra_args, timeout, env)
