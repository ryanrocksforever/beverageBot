#!/usr/bin/env python3
"""
Fix relative imports in source files for Raspberry Pi
Converts relative imports to absolute imports
"""

import os
import re
import sys

def fix_imports_in_file(filepath):
    """Fix relative imports in a Python file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Track if changes were made
    original = content
    
    # Replace relative imports with absolute imports
    replacements = [
        (r'from \.camera import', 'from camera import'),
        (r'from \.aruco_center_demo import', 'from aruco_center_demo import'),
        (r'from \.camera_config import', 'from camera_config import'),
        (r'from \.pins import', 'from pins import'),
        (r'from \.motor_gpiozero import', 'from motor_gpiozero import'),
        (r'from \.actuator_gpiozero import', 'from actuator_gpiozero import'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    src_dir = 'src'
    
    if not os.path.exists(src_dir):
        print(f"Error: {src_dir} directory not found")
        return 1
    
    fixed_files = []
    
    for filename in os.listdir(src_dir):
        if filename.endswith('.py'):
            filepath = os.path.join(src_dir, filename)
            if fix_imports_in_file(filepath):
                fixed_files.append(filename)
    
    if fixed_files:
        print(f"Fixed imports in {len(fixed_files)} files:")
        for f in fixed_files:
            print(f"  - {f}")
    else:
        print("No relative imports found to fix")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())