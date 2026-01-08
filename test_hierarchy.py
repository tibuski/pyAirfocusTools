#!/usr/bin/env python3
"""Test hierarchy formatting"""

# Simulate hierarchy output
print("Expected Hierarchy Format:")
print("="*60)

# Root level (depth=0) - no dots
print("Root Workspace")
print("..Color: yellow")
print("..Item Key: OKR-001")
print("..Default: Comment")
print("..Groups:")
print("....Engineering_F: Full")
print("....Marketing_W: Write")

print()

# Level 1 (depth=1) - 2 dots
print("..Child Workspace")
print("....Color: blue")
print("....Item Key: OKR-002")
print("....Default: Comment")
print("....Groups:")
print("......Sales_F: Full")

print()

# Level 2 (depth=2) - 4 dots
print("....Grandchild Workspace")
print("......Color: orange")
print("......Item Key: OKR-003")
print("......Default: Comment")

print("="*60)
print("\nPattern:")
print("- Root workspace (depth=0): no dots")
print("- Workspace name: '..' * depth")
print("- Detail lines: '..' * (depth + 1)")
print("- Sub-items (users/groups): '..' * (depth + 2)")
