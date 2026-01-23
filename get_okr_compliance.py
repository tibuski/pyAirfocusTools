#!/usr/bin/env python3
"""
Check OKR workspace compliance with access rules in a hierarchical view.

This tool traverses the workspace hierarchy, identifies OKR-related workspaces,
and validates their access permissions against defined rules.
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
    
    OKR workspaces are identified by checking the namespace field.
    The Item Key validation (should start with 'OKR') is a separate
    validation rule applied to OKR workspaces.
    
    Args:
        workspace: Workspace object from API
    
    Returns:
        True if workspace is OKR-related
    """
    # Check namespace field for OKR indicator
    namespace = workspace.get('namespace', '')
    
    # namespace can be a string like "app:okr"
    if isinstance(namespace, str) and 'okr' in namespace.lower():
        return True
    
    # Or it might be a dict with typeId
    if isinstance(namespace, dict):
        type_id = namespace.get('typeId', '')
        if 'okr' in type_id.lower():
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
        has_red_flag = True
    
    # Map item colors to terminal colors
    color_mapping = {
        'yellow': 'yellow',
        'orange': 'orange',
        'great': 'green',
        'blue': 'blue'
    }
    if item_color and item_color in color_mapping:
        workspace_color = color_mapping[item_color]
    
    # We'll determine if workspace has errors later and append (Wrong) to workspace name if needed
    # For now, just store the workspace name line - we'll finalize it after checking all rules
    workspace_name_line = f"{prefix}{ws_name}"
    
    # Get permissions from embedded data
    group_permissions = embedded.get('userGroupPermissions', {})
    default_permission = workspace.get('defaultPermission')
    
    # Detail indent: ALL lines have dots - add one more level of dots for details
    detail_indent = ".." * (depth + 1)
    
    # First: Color - If invalid color, entire line in RED. Otherwise workspace color.
    valid_colors = ['yellow', 'orange', 'great', 'blue']
    color_line = f"{detail_indent}Color: {item_color if item_color else '(empty)'}"
    is_red = not item_color or item_color not in valid_colors
    if is_red:
        # Invalid color - entire line in RED including (Wrong)
        color_line = colorize(f"{color_line} (Wrong)", 'red')
        has_red_flag = True
    elif workspace_color:
        # Valid color - show in workspace color
        color_line = colorize(color_line, workspace_color)
    
    if show_all or is_red:
        lines.append(color_line)
    
    # Second: Item Key - Show in workspace color, append (Wrong) in RED if invalid
    key_line = f"{detail_indent}Item Key: {item_key if item_key else '(empty)'}"
    is_red = not item_key or not item_key.startswith('OKR')
    if is_red:
        # Show line in workspace color, then append (Wrong) in RED
        if workspace_color:
            key_line = colorize(key_line, workspace_color) + colorize(" (Wrong)", 'red')
        else:
            key_line = colorize(f"{key_line} (Wrong)", 'red')
        has_red_flag = True
    elif workspace_color:
        key_line = colorize(key_line, workspace_color)
    
    if show_all or is_red:
        lines.append(key_line)
    
    # Third: Access Rights - Show in workspace color, append (Wrong) in RED if not 'comment'
    if default_permission:
        perm_display = format_permission(default_permission)
        default_line = f"{detail_indent}Default: {perm_display}"
        is_red = default_permission != 'comment'
        if is_red:
            # Show line in workspace color, then append (Wrong) in RED
            if workspace_color:
                default_line = colorize(default_line, workspace_color) + colorize(" (Wrong)", 'red')
            else:
                default_line = colorize(f"{default_line} (Wrong)", 'red')
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
            # Users in workspaces - show in workspace color, append (Wrong) in RED
            user_line = f"{sub_indent}{user_name}: {perm_str}"
            if workspace_color:
                user_line = colorize(user_line, workspace_color) + colorize(" (Wrong)", 'red')
            else:
                user_line = colorize(f"{user_line} (Wrong)", 'red')
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
            
            # Check if group name/permission mismatch - show in workspace color + (Wrong) in RED
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
                # Show line in workspace color, then append (Wrong) in RED
                if workspace_color:
                    group_line = colorize(group_line, workspace_color) + colorize(" (Wrong)", 'red')
                else:
                    group_line = colorize(f"{group_line} (Wrong)", 'red')
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
    
    # Finalize workspace name line: show in workspace color, append (Wrong) in RED if has_red_flag
    if workspace_color:
        workspace_name_line = colorize(workspace_name_line, workspace_color)
        if has_red_flag:
            workspace_name_line = workspace_name_line + colorize(" (Wrong)", 'red')
    elif has_red_flag:
        workspace_name_line = colorize(f"{workspace_name_line} (Wrong)", 'red')
    
    # Prepend workspace name to the beginning of lines
    lines.insert(0, workspace_name_line)
    
    return lines, has_red_flag


def has_errors_in_subtree(
    node: Dict[str, Any],
    current_user_id: str,
    visited: Set[str] = None
) -> bool:
    """
    Check if this node or any descendant has validation errors.
    
    Args:
        node: Node to check
        current_user_id: ID of current user
        visited: Set of visited workspace IDs to detect cycles
    
    Returns:
        True if node or any descendant has errors
    """
    if visited is None:
        visited = set()
    
    ws_id = node['workspace']['id']
    if ws_id in visited:
        return False
    visited.add(ws_id)
    
    # Check if current workspace is OKR and has errors
    if is_okr_workspace(node['workspace']):
        _, has_red_flag = format_workspace_access(
            node['workspace'],
            current_user_id,
            depth=0,
            show_all=False
        )
        if has_red_flag:
            return True
    
    # Check children recursively
    for child in node.get('children', []):
        if has_errors_in_subtree(child, current_user_id, visited):
            return True
    
    return False


def print_okr_hierarchy(
    node: Dict[str, Any],
    current_user_id: str,
    depth: int = 0,
    show_all: bool = False,
    parent_has_error: bool = False
):
    """
    Recursively print OKR workspace hierarchy using '..' for depth levels.
    
    Args:
        node: Node with 'workspace' and 'children'
        current_user_id: ID of the current authenticated user
        depth: Current depth level in hierarchy
        show_all: If True, show all workspaces; if False, only show workspaces with RED flags
        parent_has_error: If True, parent workspace has errors so we should show this node
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
        
        # Check if any descendant has errors (needed for showing parent hierarchy)
        descendant_has_error = any(
            has_errors_in_subtree(child, current_user_id, set())
            for child in node.get('children', [])
        )
        
        # Display logic per Instructions.txt line 94:
        # "By default, only display workspaces with (Wrong). Within those workspaces, 
        # only display the lines with (Wrong). Display their full hierarchy path up to 
        # the root (workspace names only, without details)."
        #
        # Implementation:
        # - If show_all: display everything (--all flag overrides filtering)
        # - If has_red_flag: display all lines with (Wrong) for this workspace
        # - If parent_has_error or descendant_has_error: display only workspace name
        #   This ensures the full hierarchy path is visible when any workspace in the
        #   tree has errors, allowing users to see the complete path to problematic workspaces
        if show_all:
            for line in lines:
                print(line)
        elif has_red_flag:
            # Show only lines with (Wrong) - already filtered by format_workspace_access when show_all=False
            for line in lines:
                print(line)
        elif parent_has_error or descendant_has_error:
            # Parent or descendant has error, so show just workspace name (first line) to show hierarchy path
            print(lines[0])
        
        # Recursively print children - pass down if current or parent has error
        children = node.get('children', [])
        for child in children:
            print_okr_hierarchy(
                child,
                current_user_id,
                depth + 1,
                show_all,
                parent_has_error=parent_has_error or has_red_flag or descendant_has_error
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
        description='Check OKR workspace compliance with access rules in a hierarchical view.'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Display all OKR workspaces (default: only show workspaces with (Wrong) flags, displaying only error lines and parent hierarchy)'
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
            print_okr_hierarchy(root, current_user_id, depth=0, show_all=True, parent_has_error=False)
        else:
            # Only show if workspace or descendants are OKR
            if is_okr_workspace(root['workspace']) or has_okr_descendants(root, set()):
                found_okr = True
                print_okr_hierarchy(root, current_user_id, depth=0, show_all=False, parent_has_error=False)
    
    if not found_okr:
        print("No OKR workspaces found.")
    
    print("="*60)


if __name__ == '__main__':
    main()
