#!/usr/bin/env python3
"""
Install an extension (app) to all workspaces within a specified folder.
Supports linking objective workspaces for OKR extensions.
"""

import argparse
import sys
from typing import List, Optional

import utils
from utils import colorize


def confirm_action(message: str) -> bool:
    """
    Prompt user for confirmation.
    
    Args:
        message: The confirmation message to display
    
    Returns:
        True if user confirms, False otherwise
    """
    while True:
        response = input(f"{message} (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' or 'n'")


def main():
    """Main entry point for the set_workspace_extension tool."""
    parser = argparse.ArgumentParser(
        description='Install an extension (app) to all workspaces within a specified folder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install OKR app to all workspaces in a folder (auto-fetch app ID)
  uv run python set_workspace_extension.py --folder "Q1 Objectives" --extension-type okr

  # Install OKR app with explicit app ID
  uv run python set_workspace_extension.py --app-id abc123 --folder "Q1 Objectives" --extension-type okr

  # Install OKR app and link objective workspaces (REQUIRED for OKR)
  # Supports both workspace names and UUIDs
  uv run python set_workspace_extension.py --folder "Team Workspaces" --extension-type okr --objective-workspaces "CMS,Product Strategy"

  # Or use workspace UUIDs directly
  uv run python set_workspace_extension.py --folder "Q1 KRs" --extension-type okr --objective-workspaces "c6ab53ae-f78b-480b-aa67-c7189713f9f7,another-id"

  # Without SSL verification
  uv run python set_workspace_extension.py --folder "Q1 Objectives" --extension-type okr --no-verify-ssl

  # With debug mode to see detailed API requests/responses
  uv run python set_workspace_extension.py --folder "Q1 Objectives" --extension-type okr --debug

Available Extension Types (from GET /api/workspaces/extensions/apps):
  - portfolio (Portfolio management)
  - prioritization (Priority scoring/ranking)
  - portal (Portal functionality)
  - insights (Analytics/reporting)
  - okr (OKR/Objectives) [TESTED - confirmed working]
    * REQUIRES at least one objective workspace ID via --objective-workspaces
  - forms (Forms functionality)
  - mirror (Mirror/sync features)
  - capacity-planning (Capacity planning)
  - voting (Voting features)
  - health-check-ins (Health check-ins)

  Note: Only 'okr' has been fully tested. Other types may have different behaviors.
        """
    )
    
    parser.add_argument(
        '--app-id',
        help='The ID of the extension/app to install. If not provided, will be auto-fetched from the extension type.'
    )
    
    parser.add_argument(
        '--folder',
        required=True,
        help='The name of the workspace folder containing target workspaces'
    )
    
    parser.add_argument(
        '--extension-type',
        required=True,
        help='The type of extension (e.g., "okr", "portfolio", "insights"). Use --help to see all available types. Note: Only "okr" has been tested.'
    )
    
    parser.add_argument(
        '--objective-workspaces',
        help='Comma-separated list of objective workspace IDs or names to link (REQUIRED for OKR extension type). Supports both workspace names and UUIDs. Example: "CMS,Product Strategy"'
    )
    
    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Ignore SSL certificate verification errors'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode to show detailed API requests and responses'
    )
    
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    args = parser.parse_args()
    
    verify_ssl = not args.no_verify_ssl
    debug = args.debug
    
    if debug:
        print(colorize("🐛 DEBUG MODE ENABLED", "yellow"))
        print("="*60)
    
    # Validate OKR extension requirements
    if args.extension_type.lower() == 'okr' and not args.objective_workspaces:
        print(colorize("Error: OKR extension requires at least one objective workspace to be specified.", "red"))
        print("Use --objective-workspaces to provide one or more objective workspace IDs or names.")
        print("\nExample:")
        print(f"  uv run python set_workspace_extension.py --folder 'YourFolder' --extension-type okr --objective-workspaces 'CMS,Product Strategy'")
        sys.exit(1)
    
    # Warning for OKR extension: linked workspaces will be replaced
    if args.extension_type.lower() == 'okr' and args.objective_workspaces:
        print(colorize("\n⚠️  WARNING: OKR Extension Replacement Behavior", "red"))
        print(colorize("=" * 60, "red"))
        print(colorize("If an OKR extension is already installed on a workspace,", "red"))
        print(colorize("the linked objective workspaces will be REPLACED (not added to)", "red"))
        print(colorize("with the ones specified in --objective-workspaces.", "red"))
        print(colorize("=" * 60, "red"))
        print()
    
    # Load registries
    print(colorize("Loading registries...", "cyan"))
    utils.load_registries(verify_ssl=verify_ssl)
    
    # Get or fetch app ID
    app_id = args.app_id
    if not app_id:
        print(colorize(f"Fetching app ID for extension type '{args.extension_type}'...", "cyan"))
        try:
            app_id = utils.get_extension_app_id(args.extension_type, verify_ssl=verify_ssl)
            if not app_id:
                print(colorize(f"Error: No app found for extension type '{args.extension_type}'", "red"))
                sys.exit(1)
            print(colorize(f"✓ Found app ID: {app_id}", "green"))
            if debug:
                print(colorize(f"🐛 DEBUG: Auto-fetched app_id = {app_id}", "yellow"))
        except Exception as e:
            print(colorize(f"Error fetching app ID: {e}", "red"))
            sys.exit(1)
    elif debug:
        print(colorize(f"🐛 DEBUG: Using provided app_id = {app_id}", "yellow"))
    
    # Parse objective workspace IDs if provided
    # Supports both workspace names and UUIDs
    objective_ws_ids = None
    if args.objective_workspaces:
        raw_ids = [ws_id.strip() for ws_id in args.objective_workspaces.split(',')]
        objective_ws_ids = []
        
        for identifier in raw_ids:
            # Check if it's a UUID (contains hyphens and hex characters)
            if '-' in identifier and len(identifier) == 36:
                # Assume it's a UUID
                objective_ws_ids.append(identifier)
                if debug:
                    print(colorize(f"🐛 DEBUG: Using UUID directly: {identifier}", "yellow"))
            else:
                # Try to resolve as workspace name
                try:
                    ws_id = utils.get_workspace_id_from_name(identifier, exact_match=True)
                    if ws_id:
                        objective_ws_ids.append(ws_id)
                        if debug:
                            print(colorize(f"🐛 DEBUG: Resolved '{identifier}' to workspace ID: {ws_id}", "yellow"))
                    else:
                        print(colorize(f"Warning: Workspace '{identifier}' not found. Skipping.", "yellow"))
                except Exception as e:
                    print(colorize(f"Error resolving workspace '{identifier}': {e}", "red"))
                    sys.exit(1)
        
        if debug:
            print(colorize(f"🐛 DEBUG: Final objective_workspace_ids = {objective_ws_ids}", "yellow"))
    elif debug:
        print(colorize(f"🐛 DEBUG: No objective workspaces specified (will send empty array)", "yellow"))
    
    # Get all workspaces in the specified folder
    print(colorize(f"\nFetching workspaces in folder '{args.folder}'...", "cyan"))
    try:
        workspaces = utils.get_workspaces_in_folder(args.folder, verify_ssl=verify_ssl)
    except Exception as e:
        print(colorize(f"Error: {e}", "red"))
        sys.exit(1)
    
    if not workspaces:
        print(colorize(f"No workspaces found in folder '{args.folder}'", "yellow"))
        sys.exit(0)
    
    # Display summary
    print(f"\n{'='*60}")
    print(colorize("Extension Installation Summary", "cyan"))
    print(f"{'='*60}")
    print(f"Extension Type: {colorize(args.extension_type, 'blue')}")
    print(f"App ID: {colorize(app_id, 'blue')}")
    print(f"Target Folder: {colorize(args.folder, 'blue')}")
    print(f"Workspaces to process: {colorize(str(len(workspaces)), 'blue')}")
    print()
    
    # Display workspace names
    print(colorize("Target workspaces:", "cyan"))
    for i, ws in enumerate(workspaces, 1):
        ws_name = ws.get('name', 'Unknown')
        print(f"  {i}. {ws_name}")
    
    # Display objective workspaces if specified
    if objective_ws_ids:
        print(f"\n{colorize(f'Objective workspaces to link ({len(objective_ws_ids)}):', 'cyan')}")
        for obj_ws_id in objective_ws_ids:
            # Resolve workspace name using the registry
            obj_ws_name = utils.get_workspace_name_from_id(obj_ws_id)
            print(f"  - {colorize(obj_ws_name, 'blue')} ({obj_ws_id})")
    
    print(f"\n{'='*60}")
    
    # Confirm action
    if not confirm_action(colorize("\nProceed with extension installation?", "yellow")):
        print(colorize("Operation cancelled.", "yellow"))
        sys.exit(0)
    
    # Process each workspace
    print(colorize("\nInstalling extension on workspaces...", "cyan"))
    print(f"{'='*60}")
    
    successful = 0
    failed = 0
    errors = []
    
    for i, workspace in enumerate(workspaces, 1):
        ws_id = workspace['id']
        ws_name = workspace.get('name', 'Unknown')
        
        print(f"\n[{i}/{len(workspaces)}] Processing: {colorize(ws_name, 'blue')}")
        
        if debug:
            print(colorize(f"🐛 DEBUG: Workspace ID = {ws_id}", "yellow"))
            print(colorize(f"🐛 DEBUG: API Endpoint = POST /api/workspaces/extensions/apps/{args.extension_type}/{app_id}/linked-workspaces/{ws_id}/objective-workspaces", "yellow"))
            print(colorize(f"🐛 DEBUG: Request Body = {objective_ws_ids if objective_ws_ids else []}", "yellow"))
        
        try:
            response = utils.install_workspace_extension(
                app_id=app_id,
                workspace_id=ws_id,
                extension_type=args.extension_type,
                objective_workspace_ids=objective_ws_ids,
                verify_ssl=verify_ssl
            )
            if debug:
                import json
                print(colorize(f"🐛 DEBUG: Response = {json.dumps(response, indent=2)}", "yellow"))
            print(colorize(f"  ✓ Success", "green"))
            successful += 1
        except Exception as e:
            if debug:
                import traceback
                print(colorize(f"🐛 DEBUG: Full error traceback:", "yellow"))
                traceback.print_exc()
            print(colorize(f"  ✗ Failed: {str(e)}", "red"))
            failed += 1
            errors.append({
                'workspace': ws_name,
                'workspace_id': ws_id,
                'error': str(e)
            })
    
    # Display final summary
    print(f"\n{'='*60}")
    print(colorize("Installation Complete", "cyan"))
    print(f"{'='*60}")
    print(f"Total workspaces processed: {len(workspaces)}")
    print(f"Successful installations: {colorize(str(successful), 'green')}")
    print(f"Failed installations: {colorize(str(failed), 'red' if failed > 0 else 'white')}")
    
    # Display error details if any
    if errors:
        print(f"\n{'='*60}")
        print(colorize("Failed Installations Details:", "red"))
        print(f"{'='*60}")
        for error_info in errors:
            print(f"\nWorkspace: {colorize(error_info['workspace'], 'yellow')}")
            print(f"ID: {error_info['workspace_id']}")
            print(f"Error: {colorize(error_info['error'], 'red')}")
    
    print()
    
    # Exit with error code if any failures
    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
