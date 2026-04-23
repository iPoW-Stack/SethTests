#!/usr/bin/env python3
"""批量更新solc版本从0.8.20回到0.8.30"""
import os

files_to_update = [
    "test_vm_opcodes.py",
    "BlockchainTests/StateTests/test_attack_badop.py",
    "BlockchainTests/StateTests/test_call_codes.py",
    "BlockchainTests/StateTests/test_code_env.py",
    "BlockchainTests/StateTests/test_create2.py",
    "BlockchainTests/StateTests/test_create_refund.py",
    "BlockchainTests/StateTests/test_log_shift.py",
    "BlockchainTests/StateTests/test_memory_stack.py",
    "BlockchainTests/StateTests/test_precompiles.py",
    "BlockchainTests/StateTests/test_revert.py",
    "BlockchainTests/StateTests/test_solidity_codelimit.py",
    "BlockchainTests/StateTests/test_static_delegate.py",
    "BlockchainTests/StateTests/test_storage.py",
    "BlockchainTests/StateTests/test_system_ops.py",
    "BlockchainTests/StateTests/test_zero_boundary.py",
    "BlockchainTests/VMTests/test_vm_opcodes.py",
]

for filepath in files_to_update:
    if not os.path.exists(filepath):
        print(f"跳过不存在的文件: {filepath}")
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换所有0.8.20为0.8.30
    new_content = content.replace('0.8.20', '0.8.30')
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✓ 已更新: {filepath}")
    else:
        print(f"- 无需更新: {filepath}")

print("\n完成！所有文件已改回使用 solc 0.8.30")
