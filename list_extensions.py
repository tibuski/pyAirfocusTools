#!/usr/bin/env python3
"""
List all available extensions (apps) from Airfocus.
Displays extension IDs and names for use with set_workspace_extension.py.
"""

import argparse
import json
import sys

import utils


def main():
    """Main entry point for the list_extensions tool."""
    parser = argparse.ArgumentParser(
        description='List all available extensions (apps) from Airfocus',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all OKR extensions
  uv run python list_extensions.py --extension-type okr

  # List extensions without SSL verification
  uv run python list_extensions.py --extension-type okr --no-verify-ssl
        """
    )
    
    parser.add_argument(
        '--extension-type',
        required=True,
        help='The type of extension to list (e.g., "okr", "objectives")'
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
    
    # Fetch extensions
    print(f"Fetching {args.extension_type} extensions...")
    
    try:
        response = utils.make_api_request(
            f'/api/workspaces/extensions/apps/{args.extension_type}/list',
            method='GET',
            verify_ssl=verify_ssl
        )
        
        items = response.get('items', [])
        
        if not items:
            print(f"No {args.extension_type} extensions found.")
            sys.exit(0)
        
        # Display results
        print(f"\n{'='*60}")
        print(f"Available {args.extension_type.upper()} Extensions")
        print(f"{'='*60}\n")
        
        for i, item in enumerate(items, 1):
            print(f"Extension {i}:")
            print(json.dumps(item, indent=2))
            print()
        
        print(f"{'='*60}")
        print(f"Total: {len(items)} extension(s) found")
        print(f"\nUse the ID with set_workspace_extension.py:")
        print(f"  uv run python set_workspace_extension.py --app-id <ID> --folder <FOLDER> --extension-type {args.extension_type}")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
