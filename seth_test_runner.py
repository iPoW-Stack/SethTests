# Seth Test Runner - Main entry point
from __future__ import annotations
import sys, os, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SETH_HOST, SETH_PORT, TEST_ECDSA_KEY
from utils import SethTestContext, Color, print_section, results
import test_core_evm, test_contracts, test_transactions, test_transaction_integration, test_blockchain, test_prefund, test_oqs

def parse_args():
    p = argparse.ArgumentParser(description="Seth EVM Compatibility Test Suite")
    p.add_argument("--host", default=None, help="Seth node host")
    p.add_argument("--port", type=int, default=None, help="Seth node port")
    p.add_argument("--phase", type=int, choices=[1, 2, 3, 4], help="Run specific phase")
    p.add_argument("--module", choices=["core","contracts","transactions","txint","blockchain","prefund","oqs"])
    p.add_argument("--skip-oqs", action="store_true")
    p.add_argument("--list", action="store_true")
    return p.parse_args()

def print_banner(ctx):
    sep = "=" * 60
    print()
    print(sep)
    print("  Seth EVM Compatibility Test Suite")
    print(sep)
    print(f"  Node:  http://{SETH_HOST}:{SETH_PORT}")
    print(f"  ECDSA: {ctx.ecdsa_addr}")
    print(sep)
    print()

def list_tests():
    mods = [
        ("Phase 1A: Core EVM", "core", test_core_evm),
        ("Phase 1B: Contracts", "contracts", test_contracts),
        ("Phase 2:  Transactions", "transactions", test_transactions),
        ("Phase 2B: Integrated Transaction Semantics", "txint", test_transaction_integration),
        ("Phase 4: Blockchain Semantics", "blockchain", test_blockchain),
        ("Phase 3A: Prefund", "prefund", test_prefund),
        ("Phase 3B: OQS", "oqs", test_oqs),
    ]
    print()
    print("Available Test Modules:")
    print()
    for name, mod_name, mod in mods:
        print(f"  {name} (--module {mod_name})")
        for n in sorted(dir(mod)):
            if n.startswith("test_"):
                f = getattr(mod, n)
                if callable(f) and f.__doc__: print(f"    - {n}: {f.__doc__.strip()}")
                elif callable(f): print(f"    - {n}")
        print()

def main():
    args = parse_args()
    if args.host: import config; config.SETH_HOST = args.host
    if args.port: import config; config.SETH_PORT = args.port
    ctx = SethTestContext()
    if args.list: list_tests(); return
    print_banner(ctx)
    t0 = time.time()
    if args.module:
        m = {"core":test_core_evm,"contracts":test_contracts,
             "transactions":test_transactions,"txint":test_transaction_integration,
             "blockchain":test_blockchain,"prefund":test_prefund,"oqs":test_oqs}
        m[args.module].run_all(ctx)
    elif args.phase == 1: test_core_evm.run_all(ctx); test_contracts.run_all(ctx)
    elif args.phase == 2: test_transactions.run_all(ctx); test_transaction_integration.run_all(ctx)
    elif args.phase == 3:
        test_prefund.run_all(ctx)
        if not args.skip_oqs: test_oqs.run_all(ctx)
    elif args.phase == 4: test_blockchain.run_all(ctx)
    else:
        test_core_evm.run_all(ctx); test_contracts.run_all(ctx)
        test_transactions.run_all(ctx); test_transaction_integration.run_all(ctx)
        test_blockchain.run_all(ctx); test_prefund.run_all(ctx)
        if not args.skip_oqs: test_oqs.run_all(ctx)
    elapsed = time.time() - t0
    ok = results.summary()
    print(f"  Total Time: {elapsed:.1f}s")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
