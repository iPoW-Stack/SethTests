# Seth Test Runner - Main entry point
from __future__ import annotations
import sys, os, argparse, time, json
import concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SETH_HOST, SETH_PORT, TEST_ECDSA_KEY
from utils import SethTestContext, Color, print_section, results
import test_core_evm, test_contracts, test_transactions, test_transaction_integration
import test_blockchain, test_prefund, test_oqs
import test_basic, test_genesis, test_vm_opcodes, test_onchain
import test_other
import test_ethereum_fixtures

MODULE_MAP = {
    "core": test_core_evm,
    "contracts": test_contracts,
    "transactions": test_transactions,
    "txint": test_transaction_integration,
    "blockchain": test_blockchain,
    "prefund": test_prefund,
    "oqs": test_oqs,
    "basic": test_basic,
    "genesis": test_genesis,
    "vm": test_vm_opcodes,
    "onchain": test_onchain,
    "other": test_other,
    "ethfixtures": test_ethereum_fixtures,
}

def parse_args():
    p = argparse.ArgumentParser(description="Seth EVM Compatibility Test Suite")
    p.add_argument("--host", default=None, help="Seth node host")
    p.add_argument("--port", type=int, default=None, help="Seth node port")
    p.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5, 6], help="Run specific phase")
    p.add_argument("--module", choices=list(MODULE_MAP.keys()),
                   help="Run specific module")
    p.add_argument("--skip-oqs", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--private-keys", type=str, help="JSON file containing list of private keys")
    p.add_argument("--concurrent", action="store_true", help="Run tests concurrently")
    p.add_argument("--max-workers", type=int, default=4, help="Maximum number of concurrent workers")
    return p.parse_args()

def print_banner(ctx, private_keys=None, concurrent=False):
    import config
    sep = "=" * 60
    print()
    print(sep)
    print("  Seth EVM Compatibility Test Suite")
    print(sep)
    print(f"  Node:  http://{config.SETH_HOST}:{config.SETH_PORT}")
    if private_keys:
        print(f"  Keys:  {len(private_keys)} private keys loaded")
        print(f"  Mode:  {'Concurrent' if concurrent else 'Sequential'}")
    else:
        print(f"  ECDSA: {ctx.ecdsa_addr}")
        print(f"  Mode:  Sequential (single key)")
    print(sep)
    print()

def list_tests():
    mods = [
        ("Phase 0:  Basic (offline)", "basic", test_basic),
        ("Phase 1A: Core EVM", "core", test_core_evm),
        ("Phase 1B: Contracts", "contracts", test_contracts),
        ("Phase 2:  Transactions", "transactions", test_transactions),
        ("Phase 2B: Integrated Tx Semantics", "txint", test_transaction_integration),
        ("Phase 3A: Prefund", "prefund", test_prefund),
        ("Phase 3B: OQS", "oqs", test_oqs),
        ("Phase 4:  Blockchain Semantics", "blockchain", test_blockchain),
        ("Phase 5A: Genesis", "genesis", test_genesis),
        ("Phase 5B: VM Opcodes", "vm", test_vm_opcodes),
        ("Phase 5C: On-chain State Tests", "onchain", test_onchain),
        ("Phase 6:  Other Tests (AMM, Cross-Shard, EIP-1559)", "other", test_other),
        ("Ethereum/tests Fixture Migration", "ethfixtures", test_ethereum_fixtures),
    ]
    print()
    print("Available Test Modules:")
    print()
    for name, mod_name, mod in mods:
        print(f"  {name} (--module {mod_name})")
        for n in sorted(dir(mod)):
            if n.startswith("test_"):
                f = getattr(mod, n)
                if callable(f) and f.__doc__:
                    print(f"    - {n}: {f.__doc__.strip()}")
                elif callable(f):
                    print(f"    - {n}")
        print()

def load_private_keys(file_path):
    """Load private keys from text file (two columns, first column is private key)."""
    try:
        private_keys = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):  # Skip empty lines and comments
                    continue
                
                # Split by whitespace (space, tab, etc.)
                parts = line.split()
                if len(parts) < 1:
                    continue
                
                private_key = parts[0].strip()
                if len(private_key) != 64:  # Standard private key length
                    print(f"{Color.YELLOW}Warning: Line {line_num} - Private key length is not 64 characters: {private_key[:8]}...{Color.END}")
                
                private_keys.append(private_key)
        
        if not private_keys:
            raise ValueError("No valid private keys found in file")
        
        return private_keys
        
    except Exception as e:
        print(f"{Color.RED}Error loading private keys from {file_path}: {e}{Color.END}")
        sys.exit(1)

def get_test_functions(module):
    """Extract all test functions from a module."""
    test_functions = []
    for name in sorted(dir(module)):
        if name.startswith("test_"):
            func = getattr(module, name)
            if callable(func):
                test_functions.append((name, func))
    return test_functions

def _addresses_for_keys(ctx, private_keys):
    return [ctx.client.get_address(key) for key in private_keys]

def _recipient_keys(private_keys, active_keys):
    recipients = [key for key in private_keys if key not in set(active_keys)]
    return recipients or private_keys

def _key_window(private_keys, module_index, window_size):
    start = module_index * max(1, window_size)
    return [private_keys[(start + i) % len(private_keys)] for i in range(max(1, window_size))]

def _context_for_key(private_keys, key_index=0, recipient_pool=None):
    ctx = SethTestContext()
    ctx.ecdsa_key = private_keys[key_index % len(private_keys)]
    ctx.ecdsa_addr = ctx.client.get_address(ctx.ecdsa_key)
    ctx.known_addresses = _addresses_for_keys(ctx, _recipient_keys(recipient_pool or private_keys, [ctx.ecdsa_key]))
    return ctx

def _run_with_config_key(module, ctx):
    import config
    old_key = config.TEST_ECDSA_KEY
    old_env_key = os.environ.get("SETH_TEST_KEY")
    try:
        config.TEST_ECDSA_KEY = ctx.ecdsa_key
        os.environ["SETH_TEST_KEY"] = ctx.ecdsa_key
        module.run_all(ctx)
    finally:
        config.TEST_ECDSA_KEY = old_key
        if old_env_key is None:
            os.environ.pop("SETH_TEST_KEY", None)
        else:
            os.environ["SETH_TEST_KEY"] = old_env_key

def run_module_concurrent(module, private_keys, max_workers, module_index=0):
    """Run a module under the concurrent policy.

    Stateful modules keep their original sequential order.  Only wrapper modules
    that expose run_all_concurrent and do not define direct test functions fan
    out internally to subprocess workers.
    """
    test_functions = get_test_functions(module)
    module_name = getattr(module, "__name__", "module")
    module_keys = _key_window(private_keys, module_index, max_workers)

    if not test_functions:
        if hasattr(module, "run_all_concurrent"):
            print(f"{Color.YELLOW}{module_name}: running module wrapper concurrently{Color.END}")
            ctx = _context_for_key(module_keys, 0, recipient_pool=private_keys)
            module.run_all_concurrent(ctx, max_workers, private_keys=module_keys)
        elif hasattr(module, "run_all"):
            print(f"{Color.YELLOW}{module_name}: running module wrapper sequentially{Color.END}")
            ctx = _context_for_key(module_keys, 0, recipient_pool=private_keys)
            _run_with_config_key(module, ctx)
        else:
            print(f"{Color.YELLOW}No test functions found in module{Color.END}")
        return

    print(f"\n{Color.BOLD}{module_name}: running {len(test_functions)} tests sequentially (ordered dependencies preserved){Color.END}")
    ctx = _context_for_key(module_keys, 0, recipient_pool=private_keys)
    key_number = private_keys.index(ctx.ecdsa_key) + 1
    print(f"Using private key {key_number}/{len(private_keys)} for ordered module run")
    print(f"Using {len(ctx.known_addresses)} known recipient addresses")
    module.run_all(ctx)

def run_module_sequential(module, ctx):
    """Run all tests in a module sequentially (original behavior)."""
    module.run_all(ctx)

def execute_test_phase(modules, private_keys, run_concurrent, max_workers, ctx):
    """Execute a phase of tests either concurrently or sequentially."""
    if not run_concurrent or not private_keys:
        for module in modules:
            run_module_sequential(module, ctx)
        return

    module_workers = min(max_workers, len(modules))
    print(f"\n{Color.BOLD}Running {len(modules)} modules concurrently with {module_workers} module workers; each stateful module preserves internal order{Color.END}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=module_workers) as executor:
        futures = [
            executor.submit(run_module_concurrent, module, private_keys, max_workers, i)
            for i, module in enumerate(modules)
        ]
        concurrent.futures.wait(futures)
        for future in futures:
            future.result()

def main():
    args = parse_args()
    
    # Configure host and port
    if args.host:
        import config
        config.SETH_HOST = args.host
        os.environ["SETH_HOST"] = args.host
    if args.port:
        import config
        config.SETH_PORT = args.port
        os.environ["SETH_PORT"] = str(args.port)
    
    # Load private keys if specified
    private_keys = None
    if args.private_keys:
        private_keys = load_private_keys(args.private_keys)
        if not private_keys:
            print(f"{Color.RED}No private keys found in file{Color.END}")
            sys.exit(1)
        print(f"{Color.GREEN}Loaded {len(private_keys)} private keys{Color.END}")
    
    # Create default context
    ctx = SethTestContext()
    
    # Handle list command
    if args.list: 
        list_tests()
        return
    
    # Print banner
    print_banner(ctx, private_keys, args.concurrent)
    t0 = time.time()

    # Determine execution mode
    concurrent = args.concurrent and private_keys is not None
    if args.concurrent and not private_keys:
        print(f"{Color.YELLOW}Warning: --concurrent specified but no private keys provided. Running sequentially.{Color.END}")

    # Execute tests based on arguments
    if args.module:
        module = MODULE_MAP[args.module]
        if concurrent:
            run_module_concurrent(module, private_keys, args.max_workers)
        else:
            run_module_sequential(module, ctx)
    elif args.phase == 1:
        execute_test_phase([test_core_evm, test_contracts], private_keys, concurrent, args.max_workers, ctx)
    elif args.phase == 2:
        execute_test_phase([test_transactions, test_transaction_integration], private_keys, concurrent, args.max_workers, ctx)
    elif args.phase == 3:
        modules = [test_prefund]
        if not args.skip_oqs:
            modules.append(test_oqs)
        execute_test_phase(modules, private_keys, concurrent, args.max_workers, ctx)
    elif args.phase == 4:
        execute_test_phase([test_blockchain], private_keys, concurrent, args.max_workers, ctx)
    elif args.phase == 5:
        execute_test_phase([test_basic, test_genesis, test_vm_opcodes, test_onchain], private_keys, concurrent, args.max_workers, ctx)
    elif args.phase == 6:
        execute_test_phase([test_other], private_keys, concurrent, args.max_workers, ctx)
    else:
        # Run everything
        all_modules = [
            test_basic,  # Phase 0: Offline basic tests
            test_core_evm, test_contracts,  # Phase 1: Core EVM + Contracts
            test_transactions, test_transaction_integration,  # Phase 2: Transactions
            test_prefund,  # Phase 3A: Prefund
        ]
        if not args.skip_oqs:
            all_modules.append(test_oqs)  # Phase 3B: OQS
        all_modules.extend([
            test_blockchain,  # Phase 4: Blockchain semantics
            test_genesis, test_vm_opcodes, test_onchain,  # Phase 5: Genesis + VM + On-chain state tests
            test_other,  # Phase 6: Other tests
        ])
        execute_test_phase(all_modules, private_keys, concurrent, args.max_workers, ctx)

    elapsed = time.time() - t0
    ok = results.summary()
    print(f"  Total Time: {elapsed:.1f}s")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
