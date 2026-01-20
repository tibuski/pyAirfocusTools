#!/usr/bin/env python3
"""
List members with contributor role in SP_OKR_/SP_ProdMgt_ groups or a specific group.

By default, lists all contributors in groups starting with SP_OKR_ or SP_ProdMgt_.
Optionally, can list contributors in a specific group.
"""

import argparse
import sys
from typing import Dict, List

from utils import (
    load_registries,
    get_groups_by_prefix,
    get_group_by_name,
    get_group_members,
    get_username_from_id,
    get_user_role,
    colorize
)


def list_contributors_in_group(group_name: str, verify_ssl: bool = True) -> Dict[str, List[str]]:
    """
    Find contributors in a specific group.
    
    Args:
        group_name: Name of the group to check
        verify_ssl: Whether to verify SSL certificates (default: True)
    
    Returns:
        Dictionary with single entry: group_name -> [contributor_names]
    """
    # Load registries (users and groups)
    load_registries(verify_ssl=verify_ssl)
    
    # Find the specific group
    group = get_group_by_name(group_name)
    
    if not group:
        print(colorize(f"Error: Group '{group_name}' not found.", 'red'))
        sys.exit(1)
    
    # Get members and filter for contributors
    user_ids = get_group_members(group['id'])
    contributors = []
    
    for user_id in user_ids:
        role = get_user_role(user_id)
        if role == 'contributor':
            full_name = get_username_from_id(user_id)
            contributors.append(full_name)
    
    if contributors:
        return {group_name: sorted(contributors)}
    return {}


def list_contributors_in_okr_groups(verify_ssl: bool = True) -> Dict[str, List[str]]:
    """
    Find all SP_OKR_ and SP_ProdMgt_ groups and list their members with contributor role.
    
    Args:
        verify_ssl: Whether to verify SSL certificates (default: True)
    
    Returns:
        Dictionary mapping group name to list of contributor full names
    """
    # Load registries (users and groups)
    load_registries(verify_ssl=verify_ssl)
    
    # Get all groups starting with SP_OKR_ or SP_ProdMgt_
    okr_groups = get_groups_by_prefix('SP_OKR_')
    prodmgt_groups = get_groups_by_prefix('SP_ProdMgt_')
    
    # Combine both lists
    all_groups = okr_groups + prodmgt_groups
    
    # Dictionary to store results: group_name -> [contributor_names]
    contributors_by_group = {}
    
    for group in all_groups:
        group_name = group.get('name', 'Unknown Group')
        user_ids = group.get('userIds', [])
        
        # Find contributors in this group
        contributors = []
        for user_id in user_ids:
            role = get_user_role(user_id)
            if role == 'contributor':
                full_name = get_username_from_id(user_id)
                contributors.append(full_name)
        
        # Only add groups that have contributors
        if contributors:
            contributors_by_group[group_name] = sorted(contributors)
    
    return contributors_by_group


def display_contributors(contributors_by_group: Dict[str, List[str]], group_name: str = None):
    """
    Display contributors grouped by their user groups.
    
    Args:
        contributors_by_group: Dictionary mapping group name to list of contributor names
        group_name: Optional - specific group name being queried
    """
    if not contributors_by_group:
        if group_name:
            print(f"No contributors found in group '{group_name}'.")
        else:
            print("No contributors found in SP_OKR_ or SP_ProdMgt_ groups.")
        return
    
    # Sort groups by name for consistent display
    for grp_name in sorted(contributors_by_group.keys()):
        print(f"\n{grp_name}:")
        for contributor in contributors_by_group[grp_name]:
            print(f"  - {contributor}")


def main():
    """Main entry point for the list_contributors tool."""
    parser = argparse.ArgumentParser(
        description='List members with contributor role in SP_OKR_/SP_ProdMgt_ groups or a specific group.'
    )
    parser.add_argument(
        'group_name',
        nargs='?',
        help='Optional: specific group name to check (default: all SP_OKR_/SP_ProdMgt_ groups)'
    )
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Disable SSL certificate verification'
    )
    
    args = parser.parse_args()
    verify_ssl = not args.no_verify_ssl
    
    try:
        if args.group_name:
            # List contributors for specific group
            print(f"Fetching contributors for group: {args.group_name}")
            contributors = list_contributors_in_group(args.group_name, verify_ssl=verify_ssl)
            display_contributors(contributors, group_name=args.group_name)
        else:
            # List contributors for all SP_OKR_ and SP_ProdMgt_ groups
            print("Fetching contributors for all SP_OKR_ and SP_ProdMgt_ groups...")
            contributors = list_contributors_in_okr_groups(verify_ssl=verify_ssl)
            display_contributors(contributors)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
