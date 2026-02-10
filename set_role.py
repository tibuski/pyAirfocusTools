#!/usr/bin/env python3
"""
Set role (editor or contributor) for members in a given user group or for orphaned users.

This tool updates the role of users in a specified group to a target role.
Can also target orphaned users (not in SP_OKR_/SP_ProdMgt_ groups with no workspace/folder access).
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
    colorize,
    get_users_not_in_specific_groups,
    build_user_access_mappings
)


def get_orphaned_users(verify_ssl: bool = True) -> dict:
    """
    Get all users who are not in SP_OKR_/SP_ProdMgt_ groups AND have no workspace/folder access.
    
    Args:
        verify_ssl: Whether to verify SSL certificates
    
    Returns:
        Dictionary mapping user_id -> {'name': str, 'workspace_count': int, 'folder_count': int}
    """
    # Get editors not in SP_OKR_/SP_ProdMgt_ groups
    editors_not_in_groups = get_users_not_in_specific_groups(
        prefixes=['SP_OKR_', 'SP_ProdMgt_'],
        exclude_suffix='_C_U',
        role='editor'
    )
    
    if not editors_not_in_groups:
        return {}
    
    # Use shared function to build access mappings (no duplication!)
    access_data = build_user_access_mappings(verify_ssl=verify_ssl)
    user_to_workspaces = access_data['user_to_workspaces']
    user_to_folders = access_data['user_to_folders']
    
    # Filter for truly orphaned users (no workspace or folder access)
    orphaned_users = {}
    for user_id in editors_not_in_groups:
        workspace_count = len(user_to_workspaces.get(user_id, []))
        folder_count = len(user_to_folders.get(user_id, []))
        
        # Only include users with ZERO access
        if workspace_count == 0 and folder_count == 0:
            orphaned_users[user_id] = {
                'name': get_username_from_id(user_id),
                'workspace_count': workspace_count,
                'folder_count': folder_count
            }
    
    return orphaned_users


def main():
    """Main entry point for the tool."""
    parser = argparse.ArgumentParser(
        description='Set role (editor or contributor) for members in a user group or for orphaned users. Does not modify admin users.'
    )
    parser.add_argument(
        'group_name',
        nargs='?',
        help='Name of the user group (e.g., SP_OKR_ERA_F). Not required when using --orphaned.'
    )
    parser.add_argument(
        '--role',
        required=True,
        choices=['editor', 'contributor'],
        help='Target role to set (editor or contributor)'
    )
    parser.add_argument(
        '--orphaned',
        action='store_true',
        help='Target orphaned users (not in SP_OKR_/SP_ProdMgt_ groups with zero workspace/folder access)'
    )
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Disable SSL certificate verification'
    )
    
    # Display help if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    args = parser.parse_args()
    
    verify_ssl = not args.no_verify_ssl
    target_role = args.role
    
    # Validate arguments
    if args.orphaned and args.group_name:
        print(colorize("Error: Cannot specify both group_name and --orphaned flag.", 'red'))
        sys.exit(1)
    
    if not args.orphaned and not args.group_name:
        print(colorize("Error: Must specify either group_name or --orphaned flag.", 'red'))
        sys.exit(1)
    
    verify_ssl = not args.no_verify_ssl
    target_role = args.role
    
    # Validate arguments
    if args.orphaned and args.group_name:
        print(colorize("Error: Cannot specify both group_name and --orphaned flag.", 'red'))
        sys.exit(1)
    
    if not args.orphaned and not args.group_name:
        print(colorize("Error: Must specify either group_name or --orphaned flag.", 'red'))
        sys.exit(1)
    
    # Determine the source role based on target
    if target_role == 'editor':
        source_role = 'contributor'
        action_desc = "Promoting contributors to editor"
    else:  # target_role == 'contributor'
        source_role = 'editor'
        action_desc = "Demoting editors to contributor"
    
    print("Loading registries (users & user groups)...")
    load_registries(verify_ssl=verify_ssl)
    
    # Get member IDs based on mode
    if args.orphaned:
        print(colorize("\nSearching for orphaned users (no workspace/folder access)...", 'cyan'))
        orphaned_data = get_orphaned_users(verify_ssl=verify_ssl)
        
        if not orphaned_data:
            print(colorize("No orphaned users found.", 'green'))
            sys.exit(0)
        
        member_ids = list(orphaned_data.keys())
        group_context = "orphaned users (not in SP_OKR_/SP_ProdMgt_ groups with zero access)"
        print(colorize(f"\nFound {len(member_ids)} orphaned user(s)", 'yellow'))
    else:
        # Find the group by name
        print(f"\nSearching for group: {args.group_name}")
        group = get_group_by_name(args.group_name)
        
        if not group:
            print(colorize(f"Error: Group '{args.group_name}' not found.", 'red'))
            sys.exit(1)
        
        group_id = group['id']
        print(colorize(f"Found group: {args.group_name}", 'green'))
        member_ids = get_group_members(group_id)
        group_context = f"group '{args.group_name}'"
        
        if not member_ids:
            print(colorize(f"No members found in {group_context}.", 'yellow'))
            sys.exit(0)
    
    print(f"Target role: {colorize(target_role, 'cyan')}")
    print(f"Action: {action_desc}")
    
    print(f"\nFound {len(member_ids)} member(s) in {group_context}:")
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
