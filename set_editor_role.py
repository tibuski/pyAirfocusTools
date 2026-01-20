#!/usr/bin/env python3
"""
Set editor role for contributors in a given user group.

This tool updates the role of contributor users in a specified group to 'editor'.
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
        description='Set editor role for contributors in a given user group. Does not modify admin users.'
    )
    parser.add_argument(
        'group_name',
        help='Name of the user group (e.g., SP_OKR_ERA_F)'
    )
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Disable SSL certificate verification'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    args = parser.parse_args()
    
    verify_ssl = not args.no_verify_ssl
    
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
    
    # Get all members of the group
    member_ids = get_group_members(group_id)
    
    if not member_ids:
        print(colorize(f"No members found in group '{args.group_name}'.", 'yellow'))
        sys.exit(0)
    
    print(f"\nFound {len(member_ids)} member(s) in group '{args.group_name}':")
    print("="*60)
    
    # Process each member
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for user_id in member_ids:
        user_name = get_username_from_id(user_id)
        current_role = get_user_role(user_id)
        
        # Show current status
        status_line = f"{user_name} (current role: {current_role})"
        
        # Skip users who are already editors
        if current_role == 'editor':
            print(f"  {colorize('SKIP', 'yellow')}: {status_line} - already editor")
            skip_count += 1
            continue
        
        # CRITICAL: Do not touch administrators!
        if current_role == 'admin':
            print(f"  {colorize('SKIP', 'yellow')}: {status_line} - admin role protected")
            skip_count += 1
            continue
        
        # Only process contributors
        if current_role != 'contributor':
            print(f"  {colorize('SKIP', 'yellow')}: {status_line} - not a contributor")
            skip_count += 1
            continue
        
        if args.dry_run:
            print(f"  {colorize('DRY-RUN', 'cyan')}: {status_line} -> would set to editor")
            success_count += 1
            continue
        
        # Set the role to editor
        print(f"  Setting role to editor for {user_name}...", end=' ')
        success = set_user_role(user_id, 'editor', verify_ssl=verify_ssl)
        
        if success:
            print(colorize('SUCCESS', 'green'))
            success_count += 1
        else:
            print(colorize('FAILED', 'red'))
            error_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if args.dry_run:
        print(f"Dry-run mode: No changes were made")
        print(f"Would update: {colorize(str(success_count), 'cyan')} contributor(s)")
    else:
        print(f"Successfully updated: {colorize(str(success_count), 'green')} contributor(s)")
        
    print(f"Skipped (already editor/admin/other): {colorize(str(skip_count), 'yellow')} user(s)")
    
    if error_count > 0:
        print(f"Failed: {colorize(str(error_count), 'red')} user(s)")
    
    print("="*60)
    
    if error_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
