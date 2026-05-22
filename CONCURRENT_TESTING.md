# Seth Test Runner - Concurrent Testing with Multiple Private Keys

This document describes the new concurrent testing functionality added to `seth_test_runner.py`.

## New Features

### 1. Private Key List Support
- Load multiple private keys from a JSON file
- Each test case uses a different private key (cycling through the list)
- Supports both array format and object format with `private_keys` field

### 2. Concurrent Test Execution
- Run test cases in parallel using ThreadPoolExecutor
- Configurable number of worker threads
- Each test runs with its own private key and context

### 3. Enhanced Command Line Arguments
- `--private-keys <file>`: JSON file containing list of private keys
- `--concurrent`: Enable concurrent test execution
- `--max-workers <n>`: Maximum number of concurrent workers (default: 4)

## Usage Examples

### Basic Usage (Sequential)
```bash
# Run tests sequentially with default private key
python seth_test_runner.py --module core

# Run tests sequentially with multiple private keys (one per test)
python seth_test_runner.py --module core --private-keys private_keys.json
```

### Concurrent Usage
```bash
# Run tests concurrently with multiple private keys
python seth_test_runner.py --module core --private-keys private_keys.json --concurrent

# Run tests concurrently with custom worker count
python seth_test_runner.py --module core --private-keys private_keys.json --concurrent --max-workers 8

# Run all tests concurrently
python seth_test_runner.py --private-keys private_keys.json --concurrent
```

### Phase-specific Testing
```bash
# Run Phase 1 tests concurrently
python seth_test_runner.py --phase 1 --private-keys private_keys.json --concurrent
```

## Private Keys File Format

### Array Format
```json
[
  "71e571862c0e4aefa87a3c16057a62c8331991a11746ab7ff8c6b6418e73b2f6",
  "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
  "59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
]
```

### Object Format
```json
{
  "private_keys": [
    "71e571862c0e4aefa87a3c16057a62c8331991a11746ab7ff8c6b6418e73b2f6",
    "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
    "59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
  ]
}
```

## How It Works

### Key Distribution
- Tests are assigned private keys in a round-robin fashion
- If there are more tests than keys, keys are reused cyclically
- Each test gets its own `SethTestContext` with the assigned private key

### Concurrent Execution
- Uses Python's `concurrent.futures.ThreadPoolExecutor`
- Each test runs in its own thread with isolated context
- Thread-safe output formatting with test IDs
- All tests must complete before the runner exits

### Backward Compatibility
- All existing functionality remains unchanged
- Sequential execution is the default behavior
- Concurrent mode only activates when both `--concurrent` and `--private-keys` are specified

## Example Output

```
============================================================
  Seth EVM Compatibility Test Suite
============================================================
  Node:  http://127.0.0.1:23001
  Keys:  8 private keys loaded
  Mode:  Concurrent
============================================================

Running 16 tests concurrently with 4 workers
Using 8 private keys in rotation

▶ [T001] test_storage_set_and_get (Key: 71e57186...)
▶ [T002] test_storage_mapping (Key: ac0974be...)
▶ [T003] test_storage_overwrite (Key: 59c6995e...)
▶ [T004] test_arithmetic_add (Key: 5de4111a...)
  ✅ COMPLETED | [T001] test_storage_set_and_get
  ✅ COMPLETED | [T002] test_storage_mapping
...
```

## Benefits

1. **Faster Test Execution**: Multiple tests run simultaneously
2. **Better Resource Utilization**: Parallel execution uses available CPU cores
3. **Isolated Test Contexts**: Each test has its own private key and context
4. **Scalable**: Configurable worker count based on system resources
5. **Backward Compatible**: Existing scripts continue to work unchanged

## Testing

Run the functionality test to verify the new features:
```bash
python test_runner_functionality.py
```

This test verifies:
- Private key loading from JSON files
- Command line argument parsing
- Concurrent execution logic and key distribution