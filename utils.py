"""
Shared utility functions for Airfocus API tools.
Provides configuration loading, API requests, and helper functions.
"""

import json
import sys
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Dict, Optional

import requests

# Increase recursion limit for deep workspace hierarchies and large datasets
# Set high enough to handle enterprise-scale deployments (16k+ users)
sys.setrecursionlimit(50000)


def load_config() -> Dict[str, str]:
    """
    Load configuration from the 'config' file in the project root.
    Returns a dictionary with configuration values.
    """
    config_path = Path(__file__).parent / "config"
    
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        print("Please create a 'config' file with required settings.")
        sys.exit(1)
    
    config = {}
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    
    required_keys = ['apikey', 'baseurl']
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        print(f"Error: Missing required configuration keys: {', '.join(missing_keys)}")
        sys.exit(1)
    
    return config


def make_api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Make an authenticated API request to Airfocus.
    
    Args:
        endpoint: API endpoint path (e.g., '/api/workspaces/search')
        method: HTTP method (GET, POST, etc.)
        data: Request body data for POST requests
        params: Query parameters
        verify_ssl: Whether to verify SSL certificates (default: True)
    
    Returns:
        Parsed JSON response
    """
    config = load_config()
    baseurl = config['baseurl'].rstrip('/')
    url = f"{baseurl}{endpoint}"
    
    headers = {
        'Authorization': f"Bearer {config['apikey']}",
        'Content-Type': 'application/json'
    }
    
    # Suppress SSL warnings if verify_ssl is False
    if not verify_ssl:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            params=params,
            verify=verify_ssl
        )
        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        sys.exit(1)


# Alias for clarity (as per instructions)
api_get = make_api_request


# Registry Pattern: Pre-fetch all users and groups at startup
_user_registry: Dict[str, Dict[str, Any]] = {}
_group_registry: Dict[str, Dict[str, Any]] = {}  # User Groups (Global Teams) from config
_registries_loaded: bool = False


def load_registries(verify_ssl: bool = True):
    """
    Pre-fetch all users and user groups from the API once and cache them.
    This implements the Registry Pattern to avoid multiple API calls.
    Call this function once at the start of your tool.
    
    CRITICAL: Uses the undocumented POST /api/team/user-groups/search endpoint
    to fetch User Groups (Global Teams) with their actual names.
    
    Args:
        verify_ssl: Whether to verify SSL certificates (default: True)
    """
    global _user_registry, _group_registry, _registries_loaded
    
    if _registries_loaded:
        return
    
    # Fetch all users
    users = make_api_request('/api/team/users', verify_ssl=verify_ssl)
    _user_registry = {user['userId']: user for user in users}
    
    # Fetch all user groups using the undocumented endpoint
    # POST /api/team/user-groups/search (not in OpenAPI spec but exists)
    user_groups_response = make_api_request(
        '/api/team/user-groups/search',
        method='POST',
        data={},
        verify_ssl=verify_ssl
    )
    
    # Build the user groups registry with actual names from the API
    user_groups = user_groups_response.get('items', [])
    _group_registry = {
        group['id']: {
            'id': group['id'],
            'name': group.get('name', 'Unknown Group'),
            'description': group.get('description', ''),
            'archived': group.get('archived', False),
            'userIds': group.get('_embedded', {}).get('userIds', [])
        }
        for group in user_groups
    }
    
    _registries_loaded = True


def get_username_from_id(user_id: str) -> str:
    """
    Resolve a user ID to a human-readable name using the registry.
    
    Args:
        user_id: UUID of the user
    
    Returns:
        User's name (or email as fallback, or ID if not found)
    """
    if not _registries_loaded:
        load_registries()
    
    user = _user_registry.get(user_id)
    if user:
        return user.get('fullName') or user.get('email') or user_id
    return user_id


def get_usergroup_name(group_id: str) -> str:
    """
    Resolve a user group ID to a human-readable name using the registry.
    
    Uses the pre-fetched registry from POST /api/team/user-groups/search
    to return the actual User Group name as seen in the Airfocus UI.
    
    Args:
        group_id: UUID of the user group
    
    Returns:
        Group's name (e.g., SP_OKR_ERA_F_U, MT_ERA_Management_U)
    """
    if not _registries_loaded:
        load_registries()
    
    # Check user groups from the API
    group = _group_registry.get(group_id)
    if group:
        return group.get('name', 'Unknown Group')
    
    # Group not in registry - return ID (shouldn't happen)
    return group_id


# Alias for backward compatibility
get_groupname_from_id = get_usergroup_name


def get_user_role(user_id: str) -> str:
    """
    Get the role of a user from the registry.
    
    Args:
        user_id: UUID of the user
    
    Returns:
        User's role (admin, contributor, or editor), or empty string if not found
    """
    if not _registries_loaded:
        load_registries()
    
    user = _user_registry.get(user_id)
    if user:
        return user.get('role', '')
    return ''


def get_groups_by_prefix(prefix: str) -> list:
    """
    Get all user groups whose name starts with the given prefix.
    
    Args:
        prefix: The prefix to filter group names by
    
    Returns:
        List of group dictionaries matching the prefix
    """
    if not _registries_loaded:
        load_registries()
    
    return [
        group for group in _group_registry.values()
        if group.get('name', '').startswith(prefix)
    ]


def get_current_user_id(verify_ssl: bool = True) -> str:
    """
    Get the current authenticated user's ID from their profile.
    
    Args:
        verify_ssl: Whether to verify SSL certificates (default: True)
    
    Returns:
        User ID of the authenticated user
    """
    profile = make_api_request('/api/profile', verify_ssl=verify_ssl)
    return profile.get('id', '')


def build_workspace_hierarchy(workspaces: list, verify_ssl: bool = True) -> Dict[str, Any]:
    """
    Build a hierarchical tree structure from a flat list of workspaces using the
    workspace-relations API to determine parent-child relationships.
    
    Args:
        workspaces: List of workspace objects from the API
        verify_ssl: Whether to verify SSL certificates (default: True)
    
    Returns:
        Dictionary with 'roots' (list of root nodes) and 'map' (workspace_id -> node)
        Each node has structure: {'workspace': workspace_data, 'children': [child_nodes]}
    """
    # Create a mapping of workspace ID to workspace data
    workspace_map = {ws['id']: ws for ws in workspaces}
    
    # Fetch workspace relations from the API
    response = make_api_request(
        '/api/workspaces/workspace-relations/search',
        method='POST',
        data={},
        verify_ssl=verify_ssl
    )
    
    relations = response.get('items', [])
    
    # Build parent-child mapping
    children_map = {}  # parentId -> [childIds]
    parent_map = {}    # childId -> parentId
    
    for relation in relations:
        parent_id = relation.get('parentId')
        child_id = relation.get('childId')
        
        if parent_id and child_id:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(child_id)
            parent_map[child_id] = parent_id
    
    # Find root workspaces (those without parents)
    root_ids = [ws_id for ws_id in workspace_map.keys() if ws_id not in parent_map]
    
    # Build hierarchy with cycle detection
    def build_node(ws_id: str, visited: set = None) -> Dict[str, Any]:
        """Build a node with its children recursively, with cycle detection."""
        if visited is None:
            visited = set()
        
        # Detect cycles
        if ws_id in visited:
            ws_name = workspace_map[ws_id].get('name', 'Unknown')
            print(f"Warning: Circular reference detected for workspace '{ws_name}' ({ws_id}) - workspace references itself as its own child")
            return {
                'workspace': workspace_map[ws_id],
                'children': []
            }
        
        visited.add(ws_id)
        
        node = {
            'workspace': workspace_map[ws_id],
            'children': []
        }
        
        # Add children recursively
        if ws_id in children_map:
            for child_id in children_map[ws_id]:
                if child_id in workspace_map:
                    child_node = build_node(child_id, visited.copy())
                    node['children'].append(child_node)
        
        return node
    
    # Build roots
    roots = []
    node_map = {}
    for root_id in root_ids:
        if root_id in workspace_map:
            node = build_node(root_id)
            roots.append(node)
            node_map[root_id] = node
    
    return {
        'roots': roots,
        'map': node_map
    }


def format_permission(permission: str) -> str:
    """Format a permission value for display."""
    permission_map = {
        'none': 'None',
        'read': 'Read',
        'comment': 'Comment',
        'write': 'Write',
        'full': 'Full'
    }
    return permission_map.get(permission, permission)


def colorize(text: str, color: str) -> str:
    """
    Apply ANSI color codes to text.
    
    Args:
        text: Text to colorize
        color: Color name (red, green, yellow, blue, magenta, cyan, white, orange)
    
    Returns:
        Text wrapped in ANSI color codes
    """
    color_map = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'orange': '\033[38;5;208m',  # 256-color orange
        'reset': '\033[0m'
    }
    
    color_code = color_map.get(color.lower(), '')
    reset_code = color_map['reset']
    
    if color_code:
        return f"{color_code}{text}{reset_code}"
    return text
