#!/usr/bin/env python3
"""
Set role (editor or contributor) for members in a given user group.

This tool updates the role of users in a specified group to a target role.
Does not modify users with admin role.
"""

import argparse
import sys

from utils import (
    load_registries,
    get_group_by_name,
    get_group_members,
    get_username_from_id,
    get_user_role,
    set_user_role,
    colorize
)


def main():
    """Main entry point for the tool."""
    parser = argparse.ArgumentParser(
        description='Set role (editor or contributor) for members in a given user group. Does not modify admin users.'
    )
    parser.add_argument(
        'group_name',
        help='Name of the user group (e.g., SP_OKR_ERA_F)'
    )
    parser.add_argument(
        '--role',
        required=True,
        choices=['editor', 'contributor'],
        help='Target role to set (editor or contributor)'
    )
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Disable SSL certificate verification'
    )
    args = parser.parse_args()
    
    verify_ssl = not args.no_verify_ssl
    target_role = args.role
    
    # Determine the source role based on target
    if target_role == 'editor':
        source_role = 'contributor'
        action_desc = "Promoting contributors to editor"
    else:  # target_role == 'contributor'
        source_role = 'editor'
        action_desc = "Demoting editors to contributor"
    
    print("Loading registries (users & user groups)...")
    load_registries(verify_ssl=verify_ssl)
    
    # Find the group by name
    print(f"\nSearching for group: {args.group_name}")
    group = get_group_by_name(args.group_name)
    
    if not group:
        print(colorize(f"Error: Group '{args.group_name}' not found.", 'red'))
        sys.exit(1)
    
    group_id = group['id']
    print(colorize(f"Found group: {args.group_name}", 'green'))
    print(f"Target role: {colorize(target_role, 'cyan')}")
    print(f"Action: {action_desc}")
    
    # Get all members of the group
    member_ids = get_group_members(group_id)
    
    if not member_ids:
        print(colorize(f"No members found in group '{args.group_name}'.", 'yellow'))
        sys.exit(0)
    
    print(f"\nFound {len(member_ids)} member(s) in group '{args.group_name}':")
    print("="*60)
    
    # First pass: Collect changes and skipped users
    changes_to_make = []
    skipped_users = []
    
    for user_id in member_ids:
        user_name = get_username_from_id(user_id)
        current_role = get_user_role(user_id)
        
        # Skip users who already have the target role
        if current_role == target_role:
            skipped_users.append((user_name, current_role, f"already {target_role}"))
            continue
        
        # CRITICAL: Do not touch administrators!
        if current_role == 'admin':
            skipped_users.append((user_name, current_role, "admin role protected"))
            continue
        
        # Only process users with the source role
        if current_role != source_role:
            skipped_users.append((user_name, current_role, f"not a {source_role}"))
            continue
        
        # This user needs to be changed
        changes_to_make.append((user_id, user_name, current_role))
    
    # Display planned changes
    print("\n" + colorize("PLANNED CHANGES:", 'cyan'))
    print("-"*60)
    
    if changes_to_make:
        for _, user_name, current_role in changes_to_make:
            print(f"  {user_name}: {colorize(current_role, 'yellow')} -> {colorize(target_role, 'green')}")
    else:
        print("  No changes needed.")
    
    print()
    
    # Display skipped users
    if skipped_users:
        print(colorize("SKIPPED USERS:", 'yellow'))
        print("-"*60)
        for user_name, current_role, reason in skipped_users:
            print(f"  {user_name} (current role: {current_role}) - {reason}")
        print()
    
    # Summary before confirmation
    print("="*60)
    print(f"Total changes to make: {colorize(str(len(changes_to_make)), 'cyan')}")
    print(f"Total users to skip: {colorize(str(len(skipped_users)), 'yellow')}")
    print("="*60)
    
    # If no changes, exit
    if not changes_to_make:
        print("\nNo changes to apply.")
        sys.exit(0)
    
    # Ask for confirmation
    print()
    try:
        response = input(colorize("Do you want to proceed with these changes? (y/n): ", 'cyan')).strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n" + colorize("Operation cancelled by user.", 'red'))
        sys.exit(1)
    
    if response != 'y':
        print(colorize("Operation cancelled by user.", 'red'))
        sys.exit(1)
    
    # Second pass: Apply changes
    print("\n" + colorize("APPLYING CHANGES:", 'green'))
    print("-"*60)
    
    success_count = 0
    error_count = 0
    
    for user_id, user_name, current_role in changes_to_make:
        print(f"  Setting role to {target_role} for {user_name}...", end=' ')
        success = set_user_role(user_id, target_role, verify_ssl=verify_ssl)
        
        if success:
            print(colorize('SUCCESS', 'green'))
            success_count += 1
        else:
            print(colorize('FAILED', 'red'))
            error_count += 1
    
    # Final Summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"Successfully updated: {colorize(str(success_count), 'green')} {source_role}(s) to {target_role}")
    print(f"Skipped (already {target_role}/admin/other): {colorize(str(len(skipped_users)), 'yellow')} user(s)")
    
    if error_count > 0:
        print(f"Failed: {colorize(str(error_count), 'red')} user(s)")
    
    print("="*60)
    
    if error_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
