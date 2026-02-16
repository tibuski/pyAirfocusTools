#!/usr/bin/env python3
"""
Find workspace ID by workspace name.
Useful for getting UUIDs to use with set_workspace_extension.py.
"""

import argparse
import sys

import utils


def main():
    """Main entry point for the find_workspace tool."""
    parser = argparse.ArgumentParser(
        description='Find workspace ID by workspace name',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find workspace by exact name
  uv run python find_workspace.py --name "CMS"

  # Find workspace with partial name match
  uv run python find_workspace.py --name "CMS" --partial

  # Search without SSL verification
  uv run python find_workspace.py --name "CMS" --no-verify-ssl
        """
    )
    
    parser.add_argument(
        '--name',
        required=True,
        help='The workspace name to search for'
    )
    
    parser.add_argument(
        '--partial',
        action='store_true',
        help='Match partial names (case-insensitive)'
    )
    
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Ignore SSL certificate verification errors'
    )
    
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    args = parser.parse_args()
    
    verify_ssl = not args.no_verify_ssl
    
    print("Fetching workspaces...")
    
    try:
        # Get all workspaces
        response = utils.make_api_request(
            '/api/workspaces',
            method='GET',
            verify_ssl=verify_ssl
        )
        
        workspaces = response.get('items', [])
        
        if not workspaces:
            print("No workspaces found.")
            sys.exit(0)
        
        # Search for matching workspaces
        search_name = args.name.lower() if args.partial else args.name
        matches = []
        
        for ws in workspaces:
            ws_name = ws.get('name', '')
            
            if args.partial:
                if search_name in ws_name.lower():
                    matches.append(ws)
            else:
                if ws_name == args.name:
                    matches.append(ws)
        
        # Display results
        if not matches:
            match_type = "partial" if args.partial else "exact"
            print(f"\nNo workspaces found with {match_type} name: '{args.name}'")
            sys.exit(0)
        
        print(f"\n{'='*80}")
        print(f"Found {len(matches)} workspace(s):")
        print(f"{'='*80}\n")
        
        for ws in matches:
            ws_id = ws.get('id', 'N/A')
            ws_name = ws.get('name', 'N/A')
            ws_archived = ws.get('archived', False)
            status = " [ARCHIVED]" if ws_archived else ""
            
            print(f"Name: {ws_name}{status}")
            print(f"ID:   {ws_id}")
            print()
        
        print(f"{'='*80}")
        print("\nUse the ID with --objective-workspaces:")
        if len(matches) == 1:
            print(f"  --objective-workspaces \"{matches[0].get('id')}\"")
        else:
            print(f"  --objective-workspaces \"<workspace-id>\"")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
