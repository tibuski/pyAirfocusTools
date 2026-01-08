#!/usr/bin/env python3
"""
Extract all unique user group IDs from workspaces.
"""

from utils import make_api_request

def main():
    print("Fetching all workspaces...")
    
    all_workspaces = []
    offset = 0
    limit = 1000
    
    while True:
        response = make_api_request(
            '/api/workspaces/search',
            method='POST',
            data={'archived': False},
            params={'offset': offset, 'limit': limit}
        )
        
        items = response.get('items', [])
        all_workspaces.extend(items)
        
        total_items = response.get('totalItems', 0)
        if offset + len(items) >= total_items or len(items) == 0:
            break
        
        offset += len(items)
    
    print(f"Found {len(all_workspaces)} workspaces")
    
    # Extract all user group IDs
    user_group_ids = set()
    for ws in all_workspaces:
        permissions = ws.get('_embedded', {}).get('userGroupPermissions', {})
        user_group_ids.update(permissions.keys())
    
    print(f"\nFound {len(user_group_ids)} unique user group IDs:\n")
    
    for group_id in sorted(user_group_ids):
        print(f"usergroup_{group_id} = ")

if __name__ == '__main__':
    main()
