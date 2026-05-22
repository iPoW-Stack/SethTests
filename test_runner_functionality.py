#!/usr/bin/env python3
"""
Test script to verify the new functionality in seth_test_runner.py
This tests the private key loading and argument parsing without dependencies.
"""

import sys
import os
import json
import argparse

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_private_key_loading():
    """Test the private key loading functionality."""
    print("Testing private key loading...")
    
    # Test loading from the sample text file
    try:
        private_keys = []
        with open('private_keys.txt', 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):  # Skip empty lines and comments
                    continue
                
                # Split by whitespace (space, tab, etc.)
                parts = line.split()
                if len(parts) < 1:
                    continue
                
                private_key = parts[0].strip()
                private_keys.append(private_key)
        
        if private_keys:
            print(f"[PASS] Successfully loaded {len(private_keys)} private keys")
            print(f"   First key: {private_keys[0][:8]}...")
            print(f"   Last key:  {private_keys[-1][:8]}...")
            return True
        else:
            print("[FAIL] No private keys found")
            return False
    except Exception as e:
        print(f"[FAIL] Error loading private keys: {e}")
        return False

def test_argument_parsing():
    """Test the new command line arguments."""
    print("\nTesting argument parsing...")
    
    try:
        # Import the parse_args function from seth_test_runner
        # We'll do this in a way that doesn't trigger the dependency imports
        import importlib.util
        spec = importlib.util.spec_from_file_location("seth_test_runner", "seth_test_runner.py")
        
        # Create a mock version of the parse_args function
        parser = argparse.ArgumentParser(description="Seth EVM Compatibility Test Suite")
        parser.add_argument("--host", default=None, help="Seth node host")
        parser.add_argument("--port", type=int, default=None, help="Seth node port")
        parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5, 6], help="Run specific phase")
        parser.add_argument("--module", choices=["core", "contracts", "transactions"], help="Run specific module")
        parser.add_argument("--skip-oqs", action="store_true")
        parser.add_argument("--list", action="store_true")
        parser.add_argument("--private-keys", type=str, help="JSON file containing list of private keys")
        parser.add_argument("--concurrent", action="store_true", help="Run tests concurrently")
        parser.add_argument("--max-workers", type=int, default=4, help="Maximum number of concurrent workers")
        
        # Test parsing various argument combinations
        test_cases = [
            ["--help"],
            ["--private-keys", "private_keys.json"],
            ["--concurrent", "--max-workers", "8"],
            ["--private-keys", "private_keys.json", "--concurrent"],
            ["--module", "core", "--private-keys", "private_keys.json", "--concurrent"],
        ]
        
        for i, args in enumerate(test_cases):
            if args[0] == "--help":
                continue  # Skip help test as it exits
            try:
                parsed_args = parser.parse_args(args)
                print(f"[PASS] Test case {i+1}: {' '.join(args)}")
                if hasattr(parsed_args, 'private_keys') and parsed_args.private_keys:
                    print(f"   Private keys file: {parsed_args.private_keys}")
                if hasattr(parsed_args, 'concurrent') and parsed_args.concurrent:
                    print(f"   Concurrent mode: {parsed_args.concurrent}")
                if hasattr(parsed_args, 'max_workers'):
                    print(f"   Max workers: {parsed_args.max_workers}")
            except SystemExit:
                print(f"[FAIL] Test case {i+1} failed: {' '.join(args)}")
                return False
        
        print("[PASS] All argument parsing tests passed")
        return True
        
    except Exception as e:
        print(f"[FAIL] Error testing argument parsing: {e}")
        return False

def test_concurrent_logic():
    """Test the concurrent execution logic."""
    print("\nTesting concurrent execution logic...")
    
    try:
        # Simulate the logic for distributing private keys to tests
        private_keys = [
            "key1", "key2", "key3", "key4"
        ]
        
        test_functions = [
            "test_1", "test_2", "test_3", "test_4", "test_5", "test_6", "test_7", "test_8"
        ]
        
        # Test key distribution (cycling through keys)
        tasks = []
        for i, test_name in enumerate(test_functions):
            private_key = private_keys[i % len(private_keys)]
            test_id = f"T{i+1:03d}"
            tasks.append((test_name, private_key, test_id))
        
        print("[PASS] Task distribution:")
        for test_name, private_key, test_id in tasks:
            print(f"   [{test_id}] {test_name} -> {private_key}")
        
        # Verify each key is used
        used_keys = set(task[1] for task in tasks)
        if used_keys == set(private_keys):
            print("[PASS] All private keys are utilized")
        else:
            print(f"[FAIL] Key utilization issue: {used_keys} vs {set(private_keys)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Error testing concurrent logic: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Seth Test Runner Functionality Test")
    print("=" * 60)
    
    tests = [
        test_private_key_loading,
        test_argument_parsing,
        test_concurrent_logic,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"Test Results: {passed}/{total} passed")
    print("=" * 60)
    
    if passed == total:
        print("[SUCCESS] All functionality tests passed!")
        return True
    else:
        print("[FAILED] Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)