# Seth EVM Compatibility Test Suite

A comprehensive test suite for validating EVM compatibility on the Seth blockchain, covering core EVM operations, contract interactions, transaction types, gas prepayment, and post-quantum (OQS) signatures.

## Prerequisites

- **Python 3.8+**
- **pip** packages:
  ```bash
  pip install web3 eth-utils requests py-solc-x
  ```
- Access to a running **Seth node** with JSON-RPC enabled.

## Quick Start

```bash
# List all available tests
python seth_tests/seth_test_runner.py --list

# Run all tests
python seth_tests/seth_test_runner.py

# Run with a custom node address
python seth_tests/seth_test_runner.py --host 35.184.150.163 --port 23001
```

## Configuration

Edit `seth_tests/config.py` or use environment variables:

| Variable | Default | Description |
|---|---|---|
| `SETH_HOST` | `35.184.150.163` | Seth node RPC host |
| `SETH_PORT` | `23001` | Seth node RPC port |
| `SETH_TEST_KEY` | *(built-in test key)* | ECDSA private key for testing |
| `SETH_TEST_OQS_KEY` | *(empty)* | OQS (post-quantum) private key |
| `SETH_TEST_OQS_PK` | *(empty)* | OQS (post-quantum) public key |
| `SETH_CHAIN_ID` | `0` | Chain ID (Seth uses 0) |

## Test Modules

### Phase 1A: Core EVM Operations (`--module core`)

Validates fundamental EVM opcodes and state operations.

| Test | Description |
|---|---|
| `test_storage_set_and_get` | Basic SSTORE/SLOAD operations |
| `test_storage_overwrite` | Storage overwrite behavior |
| `test_storage_mapping` | Mapping storage operations |
| `test_arithmetic_add` | ADD opcode |
| `test_arithmetic_sub` | SUB opcode |
| `test_arithmetic_mul` | MUL opcode |
| `test_arithmetic_div` | DIV opcode |
| `test_arithmetic_mod` | MOD opcode |
| `test_arithmetic_exp` | EXP opcode |
| `test_comparison_eq` | EQ opcode |
| `test_comparison_gt_lt` | GT/LT opcodes |
| `test_bitwise_ops` | AND/OR/XOR opcodes |
| `test_shift_ops` | SHL/SHR opcodes |
| `test_log_ops` | LOG0–LOG4 opcodes |
| `test_selfbalance` | SELFBALANCE opcode |

### Phase 1B: Contract Deployment & Interaction (`--module contracts`)

Tests Solidity contract lifecycle including cross-contract calls and proxy patterns.

| Test | Description |
|---|---|
| `test_contract_deploy_constructor` | Deploy contract with constructor arguments |
| `test_contract_increment_decrement` | State mutation (increment/decrement) |
| `test_contract_reset` | State reset function |
| `test_cross_contract_call` | Cross-contract CALL with value and return data |
| `test_delegatecall` | DELEGATECALL for proxy pattern |
| `test_revert_handling` | Contract revert behavior |

### Phase 2: Transactions (`--module transactions`)

Validates standard Ethereum transaction types against Seth.

| Test | Description |
|---|---|
| `test_simple_transfer` | Basic native token transfer |
| `test_transfer_zero_value` | Zero-value transfer |
| `test_nonce_increment` | Nonce increments per transaction |
| `test_multiple_transfers_sequential` | Sequential transfers with nonce management |
| `test_contract_creation_via_tx` | Contract creation via transaction |
| `test_contract_call_with_value` | Contract call with value transfer |
| `test_value_transfer_to_contract` | Sending value to a contract with receive() |
| `test_gas_consumption` | Gas consumption during execution |
| `test_chain_id` | Chain ID returned by the EVM |

### Phase 3A: Gas Prepayment (`--module prepayment`)

Tests Seth's prepayment mechanism for gasless transactions.

| Test | Description |
|---|---|
| `test_prepayment_basic_deposit` | Basic prepayment deposit |
| `test_prepayment_multiple_deposits` | Multiple deposits accumulate correctly |
| `test_prepayment_gas_consumption` | Gas consumed from prepayment balance |
| `test_prepayment_with_call_deposit` | Prepayment included with contract call |
| `test_prepayment_heavy_gas_usage` | Prepayment under heavy computation |

### Phase 3B: Post-Quantum (OQS) Signatures (`--module oqs`)

Tests ML-DSA-44 post-quantum signature support (Seth-specific feature).

| Test | Description |
|---|---|
| `test_oqs_transfer` | OQS-signed transfer |
| `test_oqs_contract_deploy` | Deploy contract with OQS account |
| `test_oqs_counter` | Multiple OQS-signed contract calls |
| `test_oqs_prepayment` | OQS prepayment deposit and consumption |

> **Note:** OQS tests require `SETH_TEST_OQS_KEY` and `SETH_TEST_OQS_PK` to be set. They will be automatically skipped if not configured.

## Usage Examples

```bash
# Run a specific phase
python seth_tests/seth_test_runner.py --phase 1     # Core EVM + Contracts
python seth_tests/seth_test_runner.py --phase 2     # Transactions
python seth_tests/seth_test_runner.py --phase 3     # Prepayment + OQS

# Run a single module
python seth_tests/seth_test_runner.py --module core
python seth_tests/seth_test_runner.py --module contracts
python seth_tests/seth_test_runner.py --module transactions
python seth_tests/seth_test_runner.py --module prepayment
python seth_tests/seth_test_runner.py --module oqs

# Skip OQS tests (if no OQS keys available)
python seth_tests/seth_test_runner.py --skip-oqs

# Override node address via command line
python seth_tests/seth_test_runner.py --host 192.168.1.100 --port 8545
```

## File Structure

```
seth_tests/
├── README.md               # This file
├── __init__.py             # Package init & exports
├── config.py               # Configuration & environment variables
├── utils.py                # Test framework: context, assertions, helpers
├── seth_test_runner.py     # Main CLI entry point
├── test_core_evm.py        # Phase 1A: Core EVM opcode tests
├── test_contracts.py       # Phase 1B: Contract deployment & interaction
├── test_transactions.py    # Phase 2: Transaction type tests
├── test_prepayment.py      # Phase 3A: Gas prepayment tests
└── test_oqs.py             # Phase 3B: Post-quantum signature tests
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All tests passed |
| `1` | One or more tests failed |

## Extending the Suite

To add a new test:

1. Create a `test_<name>(ctx)` function in the appropriate module file.
2. Add a docstring — it will appear in `--list` output.
3. Register it in the module's `run_all(ctx)` function.
4. If creating a new module, import it in `seth_test_runner.py` and add it to the `list_tests()` and `main()` functions.

## License

Same as the parent ethereum/tests repository.
