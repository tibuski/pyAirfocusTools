#!/usr/bin/env python3
"""
List all OKR workspaces with their access rights in a hierarchical view.

This tool traverses the workspace hierarchy, identifies OKR-related workspaces,
and displays their access permissions for users and groups.
"""

import argparse
import sys
from typing import Any, Dict, List, Set

from utils import (
    load_registries,
    make_api_request,
    get_username_from_id,
    get_groupname_from_id,
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


def get_all_workspaces() -> List[Dict[str, Any]]:
    """
    Retrieve all workspaces from the API.
    
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
            params={'offset': offset, 'limit': limit}
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
    depth: int = 0
) -> List[str]:
    """
    Format workspace access information as lines of text.
    
    Args:
        workspace: Workspace object
        current_user_id: ID of the current authenticated user
        depth: Depth level in hierarchy (used for '..' prefix)
    
    Returns:
        List of formatted lines
    """
    lines = []
    
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
    
    # Display in RED if it has user access
    if has_user_access:
        ws_name = colorize(ws_name, 'red')
    
    lines.append(f"{prefix}{ws_name}")
    
    # Get permissions from embedded data
    group_permissions = embedded.get('userGroupPermissions', {})
    default_permission = workspace.get('defaultPermission')
    
    # Detail indent uses spaces (not '..' prefix) - 2 spaces per depth level
    detail_indent = "  " * (depth + 1)
    
    # First: Color - RED if not yellow, orange, great, or blue
    if item_color:
        valid_colors = ['yellow', 'orange', 'great', 'blue']
        color_display = item_color
        if item_color not in valid_colors:
            color_display = colorize(item_color, 'red')
        lines.append(f"{detail_indent}Color: {color_display}")
    
    # Second: Item Key - RED if doesn't start with 'OKR'
    if item_key:
        key_display = item_key
        if not item_key.startswith('OKR'):
            key_display = colorize(item_key, 'red')
        lines.append(f"{detail_indent}Item Key: {key_display}")
    
    # Third: Access Rights - Add default permission if exists - RED if not 'comment'
    if default_permission:
        perm_display = format_permission(default_permission)
        if default_permission != 'comment':
            perm_display = colorize(perm_display, 'red')
        lines.append(f"{detail_indent}Default: {perm_display}")
    
    # Add user permissions first (excluding current user)
    user_perms_filtered = {
        uid: perm for uid, perm in user_permissions.items()
        if uid != current_user_id
    }
    
    if user_perms_filtered:
        lines.append(f"{detail_indent}Users:")
        for user_id, permission in sorted(user_perms_filtered.items()):
            user_name = get_username_from_id(user_id)
            perm_str = format_permission(permission)
            lines.append(f"{detail_indent}  • {user_name}: {perm_str}")
    
    # Add group permissions after users
    if group_permissions:
        lines.append(f"{detail_indent}Groups:")
        for group_id, permission in sorted(group_permissions.items()):
            group_name = get_groupname_from_id(group_id)
            perm_str = format_permission(permission)
            
            # Check if group name/permission mismatch - highlight in RED
            highlight = False
            if group_name.endswith('_F') and permission != 'full':
                highlight = True
            elif group_name.endswith('_W') and permission != 'write':
                highlight = True
            
            if highlight:
                group_name = colorize(group_name, 'red')
                perm_str = colorize(perm_str, 'red')
            
            lines.append(f"{detail_indent}  • {group_name}: {perm_str}")
    
    return lines


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
        show_all: If True, show all workspaces; if False, only OKR workspaces
    """
    workspace = node['workspace']
    
    # Determine if we should show this workspace
    should_show = show_all or is_okr_workspace(workspace)
    
    # Check if any children are OKR workspaces (for filtering)
    has_okr_children = any(
        is_okr_workspace(child['workspace']) or has_okr_descendants(child, set())
        for child in node.get('children', [])
    )
    
    # Show this workspace if it's OKR or has OKR descendants (or show_all is True)
    if should_show or has_okr_children:
        lines = format_workspace_access(
            workspace,
            current_user_id,
            depth
        )
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
        help='Include all workspaces, not just OKR workspaces'
    )
    args = parser.parse_args()
    
    print("Loading registries (users & groups)...")
    load_registries()
    
    print("Fetching workspaces...")
    workspaces = get_all_workspaces()
    
    print("Identifying current user...")
    current_user_id = get_current_user_id()
    
    print("Building hierarchy...")
    hierarchy = build_workspace_hierarchy(workspaces)
    
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
