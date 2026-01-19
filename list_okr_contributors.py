#!/usr/bin/env python3
"""
List all members of groups starting with SP_OKR_ that have the role of contributor.

This tool identifies all user groups whose names start with 'SP_OKR_', retrieves
their members, and displays those members who have the 'contributor' role,
grouped by their respective user groups.
"""

import argparse
import sys
from typing import Dict, List

from utils import (
    load_registries,
    get_groups_by_prefix,
    get_username_from_id,
    get_user_role
)


def list_contributors_in_okr_groups(verify_ssl: bool = True) -> Dict[str, List[str]]:
    """
    Find all SP_OKR_ groups and list their members with contributor role.
    
    Args:
        verify_ssl: Whether to verify SSL certificates (default: True)
    
    Returns:
        Dictionary mapping group name to list of contributor full names
    """
    # Load registries (users and groups)
    load_registries(verify_ssl=verify_ssl)
    
    # Get all groups starting with SP_OKR_
    okr_groups = get_groups_by_prefix('SP_OKR_')
    
    # Dictionary to store results: group_name -> [contributor_names]
    contributors_by_group = {}
    
    for group in okr_groups:
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


def display_contributors(contributors_by_group: Dict[str, List[str]]):
    """
    Display contributors grouped by their user groups.
    
    Args:
        contributors_by_group: Dictionary mapping group name to list of contributor names
    """
    if not contributors_by_group:
        print("No contributors found in SP_OKR_ groups.")
        return
    
    # Sort groups by name for consistent display
    for group_name in sorted(contributors_by_group.keys()):
        print(f"\n{group_name}:")
        for contributor in contributors_by_group[group_name]:
            print(f"  - {contributor}")


def main():
    """Main entry point for the list_contributors tool."""
    parser = argparse.ArgumentParser(
        description='List all members of SP_OKR_ groups with contributor role.'
    )
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Disable SSL certificate verification'
    )
    
    args = parser.parse_args()
    verify_ssl = not args.no_verify_ssl
    
    try:
        contributors = list_contributors_in_okr_groups(verify_ssl=verify_ssl)
        display_contributors(contributors)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
