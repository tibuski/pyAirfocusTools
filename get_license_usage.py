#!/usr/bin/env python3
"""
Analyze license usage across the Airfocus platform.

Provides a breakdown of:
- Total licenses (total, used, free)
- OKR licensed users (members of SP_OKR_* groups)
- Product Management licensed users (members of SP_ProdMgt_* groups, excluding *_C_U)
- Editors not in any group (licensed users not part of any group)
- Shared license users (users in both OKR and ProdMgt groups)
- Effective license users (actual unique users across all categories)
"""

import argparse
import sys
from typing import Dict, Set

from utils import (
    load_registries,
    get_team_info,
    get_unique_members_by_prefix,
    get_users_not_in_groups,
    get_users_not_in_specific_groups,
    get_username_from_id,
    colorize
)


def analyze_license_usage(verify_ssl: bool = True, debug: bool = False) -> Dict[str, any]:
    """
    Analyze license usage across OKR and Product Management groups.
    
    Args:
        verify_ssl: Whether to verify SSL certificates (default: True)
        debug: Enable debug output (default: False)
    
    Returns:
        Dictionary containing license analysis data
    """
    # Load registries (users and groups)
    load_registries(verify_ssl=verify_ssl)
    
    # Get team info with license seat data
    team_info = get_team_info(verify_ssl=verify_ssl)
    seats = team_info.get('state', {}).get('seats', {}).get('any', {})
    
    # Get unique members for OKR groups (SP_OKR_*)
    okr_users = get_unique_members_by_prefix('SP_OKR_')
    
    # Get unique members for Product Management groups (SP_ProdMgt_* but NOT *_C_U)
    prodmgt_users = get_unique_members_by_prefix('SP_ProdMgt_', exclude_suffix='_C_U')
    
    # Get editors who are not in SP_OKR_ or SP_ProdMgt_ groups (excluding *_C_U)
    editors_not_in_groups = get_users_not_in_specific_groups(
        prefixes=['SP_OKR_', 'SP_ProdMgt_'],
        exclude_suffix='_C_U',
        role='editor'
    )
    
    # Count administrators (users with 'admin' role)
    from utils import _user_registry
    admin_count = sum(1 for user in _user_registry.values() if user.get('role') == 'admin')
    
    # Debug output
    if debug:
        from utils import _user_registry, _group_registry
        total_users = len(_user_registry)
        total_groups = len(_group_registry)
        
        # Count users by role
        role_counts = {}
        users_in_any_group = set()
        users_in_okr_or_prodmgt = okr_users.union(prodmgt_users)
        
        for group in _group_registry.values():
            users_in_any_group.update(group.get('userIds', []))
        
        for user_id, user in _user_registry.items():
            role = user.get('role', 'unknown')
            role_counts[role] = role_counts.get(role, 0) + 1
        
        print(colorize(f"\n=== DEBUG INFO ===", 'magenta'))
        print(f"Total users in registry: {total_users}")
        print(f"Total groups in registry: {total_groups}")
        print(f"Users by role: {role_counts}")
        print(f"Total users in at least one group: {len(users_in_any_group)}")
        print(f"Total users in SP_OKR_ or SP_ProdMgt_ groups: {len(users_in_okr_or_prodmgt)}")
        print(f"Editors not in SP_OKR_/SP_ProdMgt_ groups: {len(editors_not_in_groups)}")
        print()
    
    # Find users who are in both OKR and ProdMgt (shared licenses)
    shared_users = okr_users.intersection(prodmgt_users)
    
    # Calculate effective license users (unique across all categories)
    # Editors not in groups are already separate, so we add them
    # Add admins to the calculation
    effective_users = okr_users.union(prodmgt_users).union(editors_not_in_groups)
    # Note: effective_users already includes admins if they're in OKR/ProdMgt groups or are editors not in groups
    # We need to add admin count separately as they may not be in any of these categories
    
    return {
        'seats': seats,
        'admin_count': admin_count,
        'okr_count': len(okr_users),
        'prodmgt_count': len(prodmgt_users),
        'editors_not_in_groups_count': len(editors_not_in_groups),
        'editors_not_in_groups': editors_not_in_groups,  # Return the actual set
        'shared_count': len(shared_users),
        'effective_count': len(effective_users) + admin_count  # Add admins to effective count
    }


def display_license_summary(analysis: Dict[str, any]):
    """
    Display the license usage summary in a clear format.
    
    Args:
        analysis: Dictionary containing license analysis data
    """
    seats = analysis['seats']
    
    print(colorize("\n=== License Usage Analysis ===\n", 'cyan'))
    
    # Total licenses section
    print(colorize("Total Licenses:", 'yellow'))
    print(f"  Total:     {seats.get('total', 0)}")
    print(f"  Used:      {seats.get('used', 0)}")
    print(f"  Free:      {seats.get('free', 0)}")
    
    print(colorize("\nLicense Distribution:", 'yellow'))
    print(f"  Administrators:                   {analysis['admin_count']}")
    print(f"  SP_OKR Groups Editors:              {analysis['okr_count']}")
    print(f"  SP_ProdMgt Groups Editors:          {analysis['prodmgt_count']}")
    print(f"  Duplicates (counted in both):     {analysis['shared_count']}")
    print(f"  Editors not in SP_OKR/SP_ProdMgt: {analysis['editors_not_in_groups_count']}")
    
    print(colorize("\nEffective License Usage:", 'green'))
    print(f"  Unique Users (Admin + OKR + ProdMgt + Editors): {analysis['effective_count']}")
    print(f"  Calculation: {analysis['admin_count']} + {analysis['okr_count']} + {analysis['prodmgt_count']} + {analysis['editors_not_in_groups_count']} - {analysis['shared_count']} = {analysis['effective_count']}")
    
    # Show discrepancy if any
    api_used = seats.get('used', 0)
    if api_used != analysis['effective_count']:
        diff = api_used - analysis['effective_count']
        print(colorize(f"\nNote: API reports {api_used} used licenses, difference of {diff}", 'magenta'))
        print(colorize("      (This may include users not in SP_OKR_/SP_ProdMgt_ groups)", 'magenta'))
    
    print()


def display_orphaned_editors(editors_not_in_groups: set):
    """
    Display a list of editors who are not in SP_OKR_ or SP_ProdMgt_ groups.
    
    Args:
        editors_not_in_groups: Set of user IDs for editors not in OKR/ProdMgt groups
    """
    if not editors_not_in_groups:
        print(colorize("\nNo orphaned editors found.", 'green'))
        return
    
    print(colorize(f"\n=== Orphaned Editors (Not in SP_OKR_/SP_ProdMgt_): {len(editors_not_in_groups)} ===\n", 'yellow'))
    
    # Sort by username for consistent output
    editor_names = sorted([get_username_from_id(user_id) for user_id in editors_not_in_groups])
    
    for name in editor_names:
        print(f"  - {name}")
    
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze license usage across Airfocus OKR and Product Management groups.'
    )
    parser.add_argument(
        '--orphaned-editors',
        action='store_true',
        help='List all editors who are not part of any group'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Disable SSL certificate verification'
    )
    
    args = parser.parse_args()
    verify_ssl = not args.no_verify_ssl
    
    try:
        analysis = analyze_license_usage(verify_ssl=verify_ssl, debug=args.debug)
        display_license_summary(analysis)
        
        # If --orphaned-editors flag is set, display the list
        if args.orphaned_editors:
            editors_not_in_groups = analysis.get('editors_not_in_groups', set())
            display_orphaned_editors(editors_not_in_groups)
            
    except Exception as e:
        print(colorize(f"Error: {e}", 'red'))
        sys.exit(1)


if __name__ == '__main__':
    main()
