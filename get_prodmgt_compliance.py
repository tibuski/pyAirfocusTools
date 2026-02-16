#!/usr/bin/env python3
"""
Check Product Management workspace compliance with access rules in a hierarchical view.

This tool traverses the workspace hierarchy, identifies Product Management workspaces
(all non-OKR workspaces), and validates their access permissions against defined rules.
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
    build_folder_hierarchy,
    colorize,
    is_okr_workspace,
    get_all_workspaces,
    WORKSPACE_COLOR_MAPPING,
)


def is_prodmgt_workspace(workspace: Dict[str, Any]) -> bool:
    """
    Determine if a workspace is Product Management related.

    Product Management workspaces are all workspaces that are NOT OKR workspaces.
    This reuses the OKR detection logic and inverts it.

    Args:
        workspace: Workspace object from API

    Returns:
        True if workspace is NOT an OKR workspace (i.e., Product Management)
    """
    return not is_okr_workspace(workspace)


def format_workspace_access(
    workspace: Dict[str, Any],
    current_user_id: str,
    depth: int = 0,
    show_all: bool = False,
    verify_ssl: bool = True,
) -> tuple[List[str], bool]:
    """
    Format workspace access information as lines of text.

    Args:
        workspace: Workspace object
        current_user_id: ID of the current authenticated user
        depth: Depth level in hierarchy (used for '..' prefix)
        show_all: If True, show all lines; if False, only show workspace name and RED lines
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Tuple of (list of formatted lines, has_red_flag boolean)
    """
    lines = []
    has_red_flag = False

    # Check if workspace has user permissions (excluding current user)
    embedded = workspace.get("_embedded", {})
    user_permissions = embedded.get("permissions", {})
    has_user_access = any(uid != current_user_id for uid in user_permissions.keys())

    # Build prefix using '..' for each depth level
    prefix = ".." * depth

    # Workspace name
    ws_name = workspace.get("name", "Unnamed")
    item_key = workspace.get("alias", "")
    item_color = workspace.get("itemColor", "")

    # Determine workspace color for all its properties
    workspace_color = None
    if has_user_access:
        has_red_flag = True

    # Map item colors to terminal colors
    if item_color and item_color in WORKSPACE_COLOR_MAPPING:
        workspace_color = WORKSPACE_COLOR_MAPPING[item_color]

    workspace_name_line = f"{prefix}{ws_name}"

    # Get permissions from embedded data
    group_permissions = embedded.get("userGroupPermissions", {})
    default_permission = workspace.get("defaultPermission")

    # Detail indent: ALL lines have dots - add one more level of dots for details
    detail_indent = ".." * (depth + 1)

    # First: Color - Display only, no validation. Still used for coloring workspace details.
    color_line = f"{detail_indent}Color: {item_color if item_color else '(empty)'}"
    if workspace_color:
        color_line = colorize(color_line, workspace_color)

    if show_all:
        lines.append(color_line)

    # Second: Item Key - Display only, no validation
    key_line = f"{detail_indent}Item Key: {item_key if item_key else '(empty)'}"
    if workspace_color:
        key_line = colorize(key_line, workspace_color)

    if show_all:
        lines.append(key_line)

    # Third: Default Access - Display only, no validation
    if default_permission:
        perm_display = format_permission(default_permission)
        default_line = f"{detail_indent}Default: {perm_display}"
        if workspace_color:
            default_line = colorize(default_line, workspace_color)

        if show_all:
            lines.append(default_line)

    # Add user permissions first (excluding current user)
    user_perms_filtered = {
        uid: perm for uid, perm in user_permissions.items() if uid != current_user_id
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
                user_line = colorize(user_line, workspace_color) + colorize(
                    " (Wrong)", "red"
                )
            else:
                user_line = colorize(f"{user_line} (Wrong)", "red")
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

            # Groups must start with SP_ProdMgt_ OR be "Airfocus Admins"
            if (
                not group_name.startswith("SP_ProdMgt_")
                and group_name != "Airfocus Admins"
            ):
                highlight = True
                has_red_flag = True
            # Groups ending with _F_U should have Full access
            elif group_name.endswith("_F_U") and permission != "full":
                highlight = True
                has_red_flag = True
            # Groups ending with _W_U should have Write access
            elif group_name.endswith("_W_U") and permission != "write":
                highlight = True
                has_red_flag = True
            # Groups ending with _C_U should have Comment access
            elif group_name.endswith("_C_U") and permission != "comment":
                highlight = True
                has_red_flag = True

            group_line = f"{sub_indent}{group_name}: {perm_str}"

            if highlight:
                # Show line in workspace color, then append (Wrong) in RED
                if workspace_color:
                    group_line = colorize(group_line, workspace_color) + colorize(
                        " (Wrong)", "red"
                    )
                else:
                    group_line = colorize(f"{group_line} (Wrong)", "red")
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
            workspace_name_line = workspace_name_line + colorize(" (Wrong)", "red")
    elif has_red_flag:
        workspace_name_line = colorize(f"{workspace_name_line} (Wrong)", "red")

    # Prepend workspace name to the beginning of lines
    lines.insert(0, workspace_name_line)

    return lines, has_red_flag


def format_folder_access(
    folder_data: Dict[str, Any],
    current_user_id: str,
    depth: int = 0,
    show_all: bool = False,
    verify_ssl: bool = True,
) -> tuple[List[str], bool]:
    """
    Format folder access information as lines of text.

    Args:
        folder_data: Folder object with _embedded data (from build_folder_hierarchy)
        current_user_id: ID of the current authenticated user
        depth: Depth level in hierarchy (used for '..' prefix)
        show_all: If True, show all lines; if False, only show folder name and RED lines
        verify_ssl: Whether to verify SSL certificates (not used, kept for consistency)

    Returns:
        Tuple of (list of formatted lines, has_red_flag boolean)
    """
    lines = []
    has_red_flag = False

    # Build prefix using '..' for each depth level
    prefix = ".." * depth

    # Folder name with icon - use yellow-orange color (we'll use 'yellow' as closest match)
    folder_name = folder_data.get("name", "Unnamed")
    folder_name_line = f"{prefix}📁 {folder_name}"
    folder_name_line = colorize(folder_name_line, "yellow")

    # Get permissions from embedded data (already fetched by build_folder_hierarchy)
    embedded = folder_data.get("_embedded", {})
    user_permissions = embedded.get("permissions", {})
    group_permissions = embedded.get("userGroupPermissions", {})

    # Check if folder has user permissions (excluding current user)
    has_user_access = any(uid != current_user_id for uid in user_permissions.keys())
    if has_user_access:
        has_red_flag = True

    # Detail indent: ALL lines have dots - add one more level of dots for details
    detail_indent = ".." * (depth + 1)

    # Add user permissions first (excluding current user)
    user_perms_filtered = {
        uid: perm for uid, perm in user_permissions.items() if uid != current_user_id
    }

    if user_perms_filtered:
        # Always show users section when there are users (it's a RED flag issue)
        users_header = f"{detail_indent}Users:"
        users_header = colorize(users_header, "yellow")
        lines.append(users_header)
        # Sub-items get another level of dots
        sub_indent = ".." * (depth + 2)
        for user_id, permission in sorted(user_perms_filtered.items()):
            user_name = get_username_from_id(user_id)
            perm_str = format_permission(permission)
            # Users in folders - show in yellow, append (Wrong) in RED
            user_line = f"{sub_indent}{user_name}: {perm_str}"
            user_line = colorize(user_line, "yellow") + colorize(" (Wrong)", "red")
            lines.append(user_line)

    # Add group permissions after users
    if group_permissions:
        if show_all:
            groups_header = f"{detail_indent}Groups:"
            groups_header = colorize(groups_header, "yellow")
            lines.append(groups_header)

        # Sub-items get another level of dots
        sub_indent = ".." * (depth + 2)
        for group_id, permission in sorted(group_permissions.items()):
            group_name = get_usergroup_name(group_id)
            perm_str = format_permission(permission)

            # Check if group name/permission mismatch - show in yellow + (Wrong) in RED
            highlight = False

            # Groups must start with SP_ProdMgt_ OR be "Airfocus Admins"
            if (
                not group_name.startswith("SP_ProdMgt_")
                and group_name != "Airfocus Admins"
            ):
                highlight = True
                has_red_flag = True
            # Groups ending with _F_U should have Full access
            elif group_name.endswith("_F_U") and permission != "full":
                highlight = True
                has_red_flag = True
            # Groups ending with _W_U should have Write access
            elif group_name.endswith("_W_U") and permission != "write":
                highlight = True
                has_red_flag = True
            # Groups ending with _C_U should have Comment access
            elif group_name.endswith("_C_U") and permission != "comment":
                highlight = True
                has_red_flag = True

            group_line = f"{sub_indent}{group_name}: {perm_str}"

            if highlight:
                # Show line in yellow, then append (Wrong) in RED
                group_line = colorize(group_line, "yellow") + colorize(
                    " (Wrong)", "red"
                )
            else:
                group_line = colorize(group_line, "yellow")

            if show_all or highlight:
                if not show_all and highlight:
                    # Add Groups header only when showing RED group for first time
                    if f"{detail_indent}Groups:" not in lines:
                        groups_header = f"{detail_indent}Groups:"
                        groups_header = colorize(groups_header, "yellow")
                        lines.append(groups_header)
                lines.append(group_line)

    # Finalize folder name line: append (Wrong) in RED if has_red_flag
    if has_red_flag:
        folder_name_line = folder_name_line + colorize(" (Wrong)", "red")

    # Prepend folder name to the beginning of lines
    lines.insert(0, folder_name_line)

    return lines, has_red_flag


def has_errors_in_node(
    node: Dict[str, Any],
    current_user_id: str,
    verify_ssl: bool = True,
    _cache: Dict[str, bool] = None,
) -> bool:
    """
    Check if this node (folder or workspace) or any descendant has validation errors.
    Uses a cache to avoid re-calling format_workspace_access() / format_folder_access()
    for nodes that have already been checked.

    Args:
        node: Node to check (can be folder or workspace node)
        current_user_id: ID of current user
        verify_ssl: Whether to verify SSL certificates
        _cache: Optional cache of node_id -> has_red_flag results

    Returns:
        True if node or any descendant has errors
    """
    if _cache is None:
        _cache = {}

    # Check if current node is a folder
    if node.get("is_folder"):
        folder_data = node.get("folder_data", {})
        folder_id = folder_data.get("id", "")

        if folder_id in _cache:
            has_red_flag = _cache[folder_id]
        else:
            _, has_red_flag = format_folder_access(
                folder_data,
                current_user_id,
                depth=0,
                show_all=False,
                verify_ssl=verify_ssl,
            )
            _cache[folder_id] = has_red_flag
        if has_red_flag:
            return True

        # Check workspaces in this folder
        for ws_node in node.get("workspaces", []):
            workspace = ws_node["workspace"]
            ws_id = workspace.get("id", "")
            if is_prodmgt_workspace(workspace):
                if ws_id in _cache:
                    has_red_flag = _cache[ws_id]
                else:
                    _, has_red_flag = format_workspace_access(
                        workspace,
                        current_user_id,
                        depth=0,
                        show_all=False,
                        verify_ssl=verify_ssl,
                    )
                    _cache[ws_id] = has_red_flag
                if has_red_flag:
                    return True

        # Check subfolders recursively
        for child_folder in node.get("children", []):
            if has_errors_in_node(child_folder, current_user_id, verify_ssl, _cache):
                return True
    else:
        # It's a workspace node (orphaned workspace at root level)
        workspace = node["workspace"]
        ws_id = workspace.get("id", "")
        if is_prodmgt_workspace(workspace):
            if ws_id in _cache:
                has_red_flag = _cache[ws_id]
            else:
                _, has_red_flag = format_workspace_access(
                    workspace,
                    current_user_id,
                    depth=0,
                    show_all=False,
                    verify_ssl=verify_ssl,
                )
                _cache[ws_id] = has_red_flag
            if has_red_flag:
                return True

    return False


def print_folder_hierarchy(
    node: Dict[str, Any],
    current_user_id: str,
    depth: int = 0,
    show_all: bool = False,
    parent_has_error: bool = False,
    verify_ssl: bool = True,
    _cache: Dict[str, bool] = None,
):
    """
    Recursively print folder-based hierarchy using '..' for depth levels.

    Args:
        node: Node (can be folder or workspace)
        current_user_id: ID of the current authenticated user
        depth: Current depth level in hierarchy
        show_all: If True, show all items; if False, only show items with RED flags
        parent_has_error: If True, parent has errors so we should show this node's name
        verify_ssl: Whether to verify SSL certificates
        _cache: Shared cache of node_id -> has_red_flag to avoid double formatting
    """
    if _cache is None:
        _cache = {}

    if node.get("is_folder"):
        # This is a folder node
        folder_data = node.get("folder_data", {})
        folder_id = folder_data.get("id", "")

        # Format folder access
        lines, has_red_flag = format_folder_access(
            folder_data, current_user_id, depth, show_all, verify_ssl
        )
        # Cache the result so has_errors_in_node won't re-format this folder
        _cache[folder_id] = has_red_flag

        # Check if any descendant has errors
        # Reuses the shared _cache to avoid double-calling format functions
        descendant_has_error = (
            has_errors_in_node(node, current_user_id, verify_ssl, _cache)
            and not has_red_flag
        )

        # Display logic:
        # - If show_all: display everything
        # - If has_red_flag: display all lines with (Wrong) for this folder
        # - If parent_has_error or descendant_has_error: display only folder name
        if show_all:
            for line in lines:
                print(line)
        elif has_red_flag:
            for line in lines:
                print(line)
        elif parent_has_error or descendant_has_error:
            # Show just folder name to display hierarchy path
            print(lines[0])

        # Print workspaces in this folder
        for ws_node in node.get("workspaces", []):
            workspace = ws_node["workspace"]
            ws_id = workspace.get("id", "")
            if is_prodmgt_workspace(workspace):
                ws_lines, ws_has_red_flag = format_workspace_access(
                    workspace, current_user_id, depth + 1, show_all, verify_ssl
                )
                # Cache this workspace's result
                _cache[ws_id] = ws_has_red_flag

                if show_all:
                    for line in ws_lines:
                        print(line)
                elif ws_has_red_flag:
                    for line in ws_lines:
                        print(line)
                elif parent_has_error or has_red_flag or descendant_has_error:
                    # Show just workspace name
                    print(ws_lines[0])

        # Recursively print subfolders
        for child_folder in node.get("children", []):
            print_folder_hierarchy(
                child_folder,
                current_user_id,
                depth + 1,
                show_all,
                parent_has_error=parent_has_error
                or has_red_flag
                or descendant_has_error,
                verify_ssl=verify_ssl,
                _cache=_cache,
            )

        # Add empty line after root-level folders
        if depth == 0:
            print()
    else:
        # This is an orphaned workspace node at root level
        workspace = node["workspace"]
        ws_id = workspace.get("id", "")
        if is_prodmgt_workspace(workspace):
            lines, has_red_flag = format_workspace_access(
                workspace, current_user_id, depth, show_all, verify_ssl
            )
            # Cache this workspace's result
            _cache[ws_id] = has_red_flag

            if show_all:
                for line in lines:
                    print(line)
            elif has_red_flag:
                for line in lines:
                    print(line)
            elif parent_has_error:
                # Show just workspace name
                print(lines[0])

            # Add empty line after root-level workspaces
            if depth == 0:
                print()


def main():
    """Main entry point for the tool."""
    parser = argparse.ArgumentParser(
        description="Check Product Management workspace compliance with access rules in a hierarchical view."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Display all Product Management workspaces and folders (default: only show items with (Wrong) flags, displaying only error lines and parent hierarchy)",
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        help="Disable SSL certificate verification",
    )

    args = parser.parse_args()

    verify_ssl = not args.no_verify_ssl

    try:
        print("Loading registries (users & user groups)...")
        load_registries(verify_ssl=verify_ssl)

        print("Fetching workspaces...")
        workspaces = get_all_workspaces(verify_ssl=verify_ssl)

        print("Identifying current user...")
        current_user_id = get_current_user_id(verify_ssl=verify_ssl)

        print("Building folder hierarchy...")
        hierarchy = build_folder_hierarchy(workspaces, verify_ssl=verify_ssl)

        print("\n" + "=" * 60)
        print("PRODUCT MANAGEMENT WORKSPACES ACCESS REPORT")
        print("=" * 60 + "\n")

        # Process each root node (can be folders or orphaned workspaces)
        found_items = False
        roots = hierarchy["roots"]
        for root in roots:
            found_items = True
            print_folder_hierarchy(
                root,
                current_user_id,
                depth=0,
                show_all=args.all,
                parent_has_error=False,
                verify_ssl=verify_ssl,
            )

        if not found_items:
            print("No Product Management workspaces or folders found.")

        print("=" * 60)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        print("\n" + "=" * 60, file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
