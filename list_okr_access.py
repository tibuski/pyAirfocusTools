#!/usr/bin/env python3
"""
List all OKR workspaces with their access rights in a hierarchical view.

This tool traverses the workspace hierarchy, identifies OKR-related workspaces,
and displays their access permissions for users and user groups.
"""

import argparse
import sys
from typing import Any, Dict, List, Set

from utils import (
    load_registries,
    make_api_request,
    get_username_from_id,
    get_usergroup_name,
    get_current_user_id,
    format_permission,
    build_workspace_hierarchy,
    colorize
)


def is_okr_workspace(workspace: Dict[str, Any]) -> bool:
    """
    Determine if a workspace is OKR-related.
    
    Args:
        workspace: Workspace object from API
    
    Returns:
        True if workspace is OKR-related
    """
    # Check namespace field for OKR indicator
    namespace = workspace.get('namespace', '')
    
    # namespace can be a string like "app:okr"
    if isinstance(namespace, str) and 'okr' in namespace:
        return True
    
    # Or it might be a dict with typeId
    if isinstance(namespace, dict):
        type_id = namespace.get('typeId', '')
        if 'okr' in type_id:
            return True
    
    # Also check item type for OKR keywords
    item_type = workspace.get('itemType', '')
    if 'okr' in item_type.lower():
        return True
    
    return False


def get_all_workspaces(verify_ssl: bool = True) -> List[Dict[str, Any]]:
    """
    Retrieve all workspaces from the API.
    
    Args:
        verify_ssl: Whether to verify SSL certificates (default: True)
    
    Returns:
        List of workspace objects
    """
    all_workspaces = []
    offset = 0
    limit = 1000
    
    while True:
        response = make_api_request(
            '/api/workspaces/search',
            method='POST',
            data={
                'archived': False,
                'sort': {'type': 'name', 'direction': 'asc'}
            },
            params={'offset': offset, 'limit': limit},
            verify_ssl=verify_ssl
        )
        
        items = response.get('items', [])
        all_workspaces.extend(items)
        
        total_items = response.get('totalItems', 0)
        if offset + limit >= total_items:
            break
        
        offset += limit
    
    return all_workspaces


def format_workspace_access(
    workspace: Dict[str, Any],
    current_user_id: str,
    depth: int = 0,
    show_all: bool = False
) -> tuple[List[str], bool]:
    """
    Format workspace access information as lines of text.
    
    Args:
        workspace: Workspace object
        current_user_id: ID of the current authenticated user
        depth: Depth level in hierarchy (used for '..' prefix)
        show_all: If True, show all lines; if False, only show workspace name and RED lines
    
    Returns:
        Tuple of (list of formatted lines, has_red_flag boolean)
    """
    lines = []
    has_red_flag = False
    
    # Check if workspace has user permissions (excluding current user)
    embedded = workspace.get('_embedded', {})
    user_permissions = embedded.get('permissions', {})
    has_user_access = any(uid != current_user_id for uid in user_permissions.keys())
    
    # Build prefix using '..' for each depth level
    prefix = ".." * depth
    
    # Workspace name
    ws_name = workspace.get('name', 'Unnamed')
    item_key = workspace.get('alias', '')
    item_color = workspace.get('itemColor', '')
    
    # Determine workspace color for all its properties
    workspace_color = None
    if has_user_access:
        workspace_color = 'red'
        has_red_flag = True
    else:
        # Map item colors to terminal colors
        color_mapping = {
            'yellow': 'yellow',
            'orange': 'orange',
            'great': 'green',
            'blue': 'blue'
        }
        if item_color and item_color in color_mapping:
            workspace_color = color_mapping[item_color]
    
    # Build the full line with prefix and apply color
    full_line = f"{prefix}{ws_name}"
    if workspace_color:
        full_line = colorize(full_line, workspace_color)
    
    lines.append(full_line)
    
    # Get permissions from embedded data
    group_permissions = embedded.get('userGroupPermissions', {})
    default_permission = workspace.get('defaultPermission')
    
    # Detail indent: ALL lines have dots - add one more level of dots for details
    detail_indent = ".." * (depth + 1)
    
    # First: Color - RED whole line if not yellow, orange, great, or blue, or if empty
    valid_colors = ['yellow', 'orange', 'great', 'blue']
    color_line = f"{detail_indent}Color: {item_color if item_color else '(empty)'}"
    is_red = not item_color or item_color not in valid_colors
    if is_red:
        color_line = colorize(color_line, 'red')
        has_red_flag = True
    elif workspace_color:
        color_line = colorize(color_line, workspace_color)
    
    if show_all or is_red:
        lines.append(color_line)
    
    # Second: Item Key - RED whole line if doesn't start with 'OKR' or is empty
    key_line = f"{detail_indent}Item Key: {item_key if item_key else '(empty)'}"
    is_red = not item_key or not item_key.startswith('OKR')
    if is_red:
        key_line = colorize(key_line, 'red')
        has_red_flag = True
    elif workspace_color:
        key_line = colorize(key_line, workspace_color)
    
    if show_all or is_red:
        lines.append(key_line)
    
    # Third: Access Rights - RED whole line if not 'comment'
    if default_permission:
        perm_display = format_permission(default_permission)
        default_line = f"{detail_indent}Default: {perm_display}"
        is_red = default_permission != 'comment'
        if is_red:
            default_line = colorize(default_line, 'red')
            has_red_flag = True
        elif workspace_color:
            default_line = colorize(default_line, workspace_color)
        
        if show_all or is_red:
            lines.append(default_line)
    
    # Add user permissions first (excluding current user)
    user_perms_filtered = {
        uid: perm for uid, perm in user_permissions.items()
        if uid != current_user_id
    }
    
    if user_perms_filtered:
        # Always show users section when there are users (it's a RED flag issue)
        users_header = f"{detail_indent}Users:"
        if workspace_color:
            users_header = colorize(users_header, workspace_color)
        lines.append(users_header)
        # Sub-items get another level of dots
        sub_indent = ".." * (depth + 2)
        for user_id, permission in sorted(user_perms_filtered.items()):
            user_name = get_username_from_id(user_id)
            perm_str = format_permission(permission)
            # Users in workspaces should always appear in RED
            user_line = f"{sub_indent}{user_name}: {perm_str}"
            user_line = colorize(user_line, 'red')
            lines.append(user_line)
    
    # Add group permissions after users
    if group_permissions:
        if show_all:
            groups_header = f"{detail_indent}Groups:"
            if workspace_color:
                groups_header = colorize(groups_header, workspace_color)
            lines.append(groups_header)
        
        # Sub-items get another level of dots
        sub_indent = ".." * (depth + 2)
        for group_id, permission in sorted(group_permissions.items()):
            group_name = get_usergroup_name(group_id)
            perm_str = format_permission(permission)
            
            # Check if group name/permission mismatch - highlight in RED
            highlight = False
            
            # Groups must start with SP_OKR_ OR be "Airfocus Admins"
            if not group_name.startswith('SP_OKR_') and group_name != 'Airfocus Admins':
                highlight = True
                has_red_flag = True
            # Groups ending with _F should have Full access
            elif group_name.endswith('_F') and permission != 'full':
                highlight = True
                has_red_flag = True
            # Groups ending with _W should have Write access
            elif group_name.endswith('_W') and permission != 'write':
                highlight = True
                has_red_flag = True
            
            group_line = f"{sub_indent}{group_name}: {perm_str}"
            
            if highlight:
                group_line = colorize(group_line, 'red')
            elif workspace_color:
                group_line = colorize(group_line, workspace_color)
            
            if show_all or highlight:
                if not show_all and highlight:
                    # Add Groups header only when showing RED group for first time
                    if f"{detail_indent}Groups:" not in lines:
                        groups_header = f"{detail_indent}Groups:"
                        if workspace_color:
                            groups_header = colorize(groups_header, workspace_color)
                        lines.append(groups_header)
                lines.append(group_line)
    
    return lines, has_red_flag


def print_okr_hierarchy(
    node: Dict[str, Any],
    current_user_id: str,
    depth: int = 0,
    show_all: bool = False
):
    """
    Recursively print OKR workspace hierarchy using '..' for depth levels.
    
    Args:
        node: Node with 'workspace' and 'children'
        current_user_id: ID of the current authenticated user
        depth: Current depth level in hierarchy
        show_all: If True, show all workspaces; if False, only show workspaces with RED flags
    """
    workspace = node['workspace']
    
    # Determine if we should show this workspace
    should_show_okr = is_okr_workspace(workspace)
    
    # Check if any children are OKR workspaces (for filtering)
    has_okr_children = any(
        is_okr_workspace(child['workspace']) or has_okr_descendants(child, set())
        for child in node.get('children', [])
    )
    
    # Show this workspace if it's OKR or has OKR descendants
    if should_show_okr or has_okr_children:
        lines, has_red_flag = format_workspace_access(
            workspace,
            current_user_id,
            depth,
            show_all
        )
        
        # Display if show_all OR has RED flags
        if show_all or has_red_flag:
            for line in lines:
                print(line)
        
        # Recursively print children
        children = node.get('children', [])
        for child in children:
            print_okr_hierarchy(
                child,
                current_user_id,
                depth + 1,
                show_all
            )
        
        # Add empty line after root-level workspaces
        if depth == 0:
            print()


def has_okr_descendants(node: Dict[str, Any], visited: Set[str] = None) -> bool:
    """
    Check if a node has any OKR workspace descendants.
    Uses memoization and cycle detection to prevent recursion issues.
    
    Args:
        node: Node to check
        visited: Set of already visited workspace IDs to detect cycles
    
    Returns:
        True if node or any descendant is OKR workspace
    """
    if visited is None:
        visited = set()
    
    ws_id = node['workspace']['id']
    
    # Detect cycles
    if ws_id in visited:
        return False
    
    visited.add(ws_id)
    
    if is_okr_workspace(node['workspace']):
        return True
    
    return any(has_okr_descendants(child, visited) for child in node.get('children', []))


def main():
    """Main entry point for the tool."""
    parser = argparse.ArgumentParser(
        description='List OKR workspaces with their access rights in a hierarchical view.'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Display all workspaces regardless of validation issues (default: only show workspaces with RED flags)'
    )
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Disable SSL certificate verification'
    )
    args = parser.parse_args()
    
    verify_ssl = not args.no_verify_ssl
    
    print("Loading registries (users & user groups)...")
    load_registries(verify_ssl=verify_ssl)
    
    print("Fetching workspaces...")
    workspaces = get_all_workspaces(verify_ssl=verify_ssl)
    
    print("Identifying current user...")
    current_user_id = get_current_user_id(verify_ssl=verify_ssl)
    
    print("Building hierarchy...")
    hierarchy = build_workspace_hierarchy(workspaces, verify_ssl=verify_ssl)
    
    print("\n" + "="*60)
    print("OKR WORKSPACES ACCESS REPORT")
    print("="*60 + "\n")
    
    # Process each root workspace
    found_okr = False
    roots = hierarchy['roots']
    for root in roots:
        # For --all flag, show everything
        if args.all:
            found_okr = True
            print_okr_hierarchy(root, current_user_id, depth=0, show_all=True)
        else:
            # Only show if workspace or descendants are OKR
            if is_okr_workspace(root['workspace']) or has_okr_descendants(root, set()):
                found_okr = True
                print_okr_hierarchy(root, current_user_id, depth=0, show_all=False)
    
    if not found_okr:
        print("No OKR workspaces found.")
    
    print("="*60)


if __name__ == '__main__':
    main()
