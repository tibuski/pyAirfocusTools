# pyAirfocusTools

Secure, modular CLI toolset for interacting with the Airfocus API.

## Requirements

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

1. **Install uv**:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Configure API credentials**:
   
   Create a `config` file in the project root with the following format:
   ```
   apikey = your_airfocus_api_key_here
   baseurl = https://app.airfocus.com
   ```

## Usage

All tools are executed using `uv run`:

### get_okr_compliance.py

Check OKR workspace compliance with access rules in hierarchical view.

```bash
uv run python get_okr_compliance.py
uv run python get_okr_compliance.py --all
uv run python get_okr_compliance.py --no-verify-ssl
```

**Options:**
- `--all`: Display all OKR workspaces (default: only shows workspaces with validation issues)
- `--no-verify-ssl`: Disable SSL certificate verification

**Display Behavior:**
- Default mode: Only displays workspaces with validation issues
  - Shows only lines with "(Wrong)" flags
  - Shows full parent hierarchy up to root (workspace names only, without details)
- `--all` mode: Displays all OKR workspaces with complete details

**OKR Workspace Detection:**
- Identifies workspaces by namespace field (e.g., "app:okr") or itemType containing 'okr'

**Output Format:**
- Hierarchy using '..' prefix (no dots for root level, all lines have dots)
- Order: Color → Item Key → Access Rights
- IDs resolved to human-readable names
- Current user excluded from output

**Validation (RED highlighting):**
- Direct user access: Line shown in workspace color + " (Wrong)" in RED
- Default permission ≠ 'Comment': Line shown in workspace color + " (Wrong)" in RED
- Item Key not starting with 'OKR' or empty: Line shown in workspace color + " (Wrong)" in RED
- Color invalid (not in {yellow, orange, great, blue} or empty): Entire line " (Wrong)" in RED
- Groups not starting with 'SP_OKR_' (except "Airfocus Admins"): Line shown in workspace color + " (Wrong)" in RED
- Groups ending with '_F' without 'Full' access: Line shown in workspace color + " (Wrong)" in RED
- Groups ending with '_W' without 'Write' access: Line shown in workspace color + " (Wrong)" in RED
- Workspace names: Shown in their designated color + " (Wrong)" in RED appended if any rule above applies

**Color Display:**
- Workspace names and their details appear in designated color (yellow/orange/green/blue)
- Color mapping: yellow → yellow, orange → orange, great → green, blue → blue
- Invalid items have " (Wrong)" appended in RED after the colored text

### get_prodmgt_compliance.py

Check Product Management workspace compliance with access rules in a hierarchical view. Product Management workspaces are organized using folder-based hierarchy.

```bash
uv run python get_prodmgt_compliance.py
uv run python get_prodmgt_compliance.py --all
uv run python get_prodmgt_compliance.py --no-verify-ssl
```

**Options:**
- `--all`: Display all Product Management workspaces and folders (default: only shows items with validation issues)
- `--no-verify-ssl`: Disable SSL certificate verification

**Display Behavior:**
- Default mode: Only displays workspaces/folders with validation issues
  - Shows only lines with "(Wrong)" flags
  - Shows full parent hierarchy up to root (names only, without details)
- `--all` mode: Displays all Product Management workspaces and folders with complete details

**Product Management Workspace Detection:**
- Identifies workspaces as Product Management if they are NOT OKR workspaces (inverts OKR detection logic)
- OKR workspaces are identified by namespace field containing 'okr' or itemType containing 'okr'

**Hierarchy Structure:**
- Uses folder-based organization (workspace groups) instead of parent-child relationships
- Folders displayed with 📁 icon prefix in yellow color
- Workspaces properly nested within folders based on workspace group assignments
- Orphaned workspaces (not in any folder) shown at root level
- Efficient batch fetching: All folders and their workspaces retrieved in single API call

**Output Format:**
- Hierarchy using '..' prefix (no dots for root level, all lines have dots)
- Folders: 📁 icon + folder name in yellow
- Workspaces: Order is Color → Item Key → Default Access → Access Rights (Groups/Users)
- IDs resolved to human-readable names
- Current user excluded from output

**Validation (RED highlighting):**
- **Note:** Color, Item Key, and Default Access are displayed for information only - no validation performed
- **Folders and Workspaces both validated for:**
  - Direct user access: Line shown in yellow (folders) or workspace color + " (Wrong)" in RED
  - Groups not starting with 'SP_ProdMgt_' (except "Airfocus Admins"): Line shown in yellow/workspace color + " (Wrong)" in RED
  - Groups ending with '_F_U' without 'Full' access: Line shown in yellow/workspace color + " (Wrong)" in RED
  - Groups ending with '_W_U' without 'Write' access: Line shown in yellow/workspace color + " (Wrong)" in RED
  - Groups ending with '_C_U' without 'Comment' access: Line shown in yellow/workspace color + " (Wrong)" in RED
- Folder/Workspace names: Shown in their designated color + " (Wrong)" in RED appended if any validation rule above applies

**Color Display:**
- Folders: Yellow with 📁 icon (representing Windows folder color)
- Workspace names and details: Appear in designated color (yellow/orange/green/blue)
- Color mapping: yellow → yellow, orange → orange, great → green, blue → blue
- Invalid items have " (Wrong)" appended in RED after the colored text

### get_group_contributors.py

Get all contributors in SP_OKR_ and SP_ProdMgt_ groups (excluding *_C_U) or a specific group.

```bash
uv run python get_group_contributors.py [group_name] [--no-verify-ssl]
```

**Arguments:**
- `group_name`: Optional - Name of a specific group to check (default: all SP_OKR_ and SP_ProdMgt_ groups, excluding *_C_U)

**Options:**
- `--no-verify-ssl`: Disable SSL certificate verification

**Output:**
- Groups contributors by user group name
- Shows full name of each contributor
- Only displays groups that have contributors
- Excludes SP_ProdMgt_ groups ending with _C_U when using default mode

### set_role.py

Set role (editor or contributor) for members in a specified user group. Does not modify admin users.

```bash
uv run python set_role.py <group_name> --role <editor|contributor> [--no-verify-ssl]
```

**Arguments:**
- `group_name`: Name of the user group (required)

**Options:**
- `--role`: Target role to set - either 'editor' or 'contributor' (required)
- `--no-verify-ssl`: Disable SSL certificate verification

**Behavior:**
- Displays all planned changes and skipped users before execution
- Prompts for confirmation (y/n) before applying any changes
- If `--role editor`: Updates users with 'contributor' role to 'editor'
- If `--role contributor`: Updates users with 'editor' role to 'contributor'
- Skips users who already have the target role
- **NEVER modifies users with 'admin' role**
- Skips users with any other role

**Output:**
- Shows each user being processed with their current role
- Displays summary with success/skip/error counts
- Color-coded status: GREEN (success), YELLOW (skipped), RED (failed)

### get_license_usage.py

Analyze license usage across Airfocus platform with breakdown by OKR and Product Management groups.

```bash
uv run python get_license_usage.py [--orphaned-editors] [--debug] [--no-verify-ssl]
```

**Options:**
- `--orphaned-editors`: List all editors who are not part of SP_OKR_ or SP_ProdMgt_ groups, including their group memberships and workspace access
- `--debug`: Show debug information about user and group counts
- `--no-verify-ssl`: Disable SSL certificate verification

**Analysis:**
1. **Total Licenses**: Queries `/api/team` endpoint for seat data (total, used, free)
2. **Administrators**: Counts all users with 'admin' role
3. **OKR Licensed Users**: Counts unique members across all groups starting with `SP_OKR_`
4. **Product Management Licensed Users**: Counts unique members across groups starting with `SP_ProdMgt_` (excluding groups ending with `_C_U`)
5. **Editors not in OKR/ProdMgt groups**: Counts users with 'editor' role who are not members of SP_OKR_ or SP_ProdMgt_ groups (excluding *_C_U)
6. **Shared License Users**: Identifies users appearing in both OKR and Product Management groups (counted in both but using single license)
7. **Effective License Users**: Calculates actual unique users: Admins + OKR + ProdMgt + Editors - Shared

**Output:**
- Total license allocation (total, used, free)
- License distribution by category (Administrators, OKR, ProdMgt, Editors not in OKR/ProdMgt)
- Shared license count (users in multiple categories)
- Effective license usage calculation
- Discrepancy note if API-reported usage differs from calculated effective users

**Orphaned Editors Details** (with `--orphaned-editors` flag):
- Lists each editor not in SP_OKR_ or SP_ProdMgt_ groups
- For each editor, displays:
  - **Access hierarchy**: Hierarchical view of workspace groups (folders) and workspaces the user has direct access to
    - Folders shown with 📁 icon and permission level (Full, Write, Comment, Read)
    - Workspaces nested under their folders with proper indentation
    - Orphaned workspaces (not in folders) shown at root level
    - Shows permission level for each folder and workspace
    - Properly handles nested folder structures recursively
    - Only shows folders/workspaces where user has direct (non-group) permissions
- Uses '..' indentation following hierarchy conventions (more dots = deeper nesting)
- Color-coded: Yellow for section headers, Cyan for "Access hierarchy:", Magenta for "no access" states
- Helps identify why editors are consuming licenses outside OKR/ProdMgt groups

**Performance:**
- Optimized for large datasets (tested with 75+ orphaned editors)
- Fetches all workspaces and folders once upfront
- Builds access mappings in memory (no per-user API calls)
- Typical execution time: ~5-10 seconds for full hierarchy analysis

### set_field_options.py

Manage custom field options for Airfocus select/dropdown fields via CLI. Supports viewing, adding, and reordering options.

```bash
# View current options (displays and saves to file)
uv run python set_field_options.py --field <FIELD_NAME>

# View with option IDs
uv run python set_field_options.py --field <FIELD_NAME> --show-ids

# Add new options from a file
uv run python set_field_options.py --field <FIELD_NAME> --input <FILE>

# Reorder existing options based on file order
uv run python set_field_options.py --field <FIELD_NAME> --input <FILE> --reorder

# Disable SSL verification
uv run python set_field_options.py --field <FIELD_NAME> --no-verify-ssl
```

**Arguments:**
- `--field FIELD_NAME` (required): The name of the field to manage.
- `--input FILE` (optional): Path to a text file containing options (one per line).
- `--reorder` (optional): Reorder existing options based on the order in the input file (requires `--input`).
- `--show-ids` (optional): Display option IDs alongside option names.
- `--no-verify-ssl` (optional): Disable SSL certificate verification.

**Modes of Operation:**

1. **View Mode** (only `--field`):
   - Fetches all current options for the field
   - Displays them to console (numbered list)
   - Saves them to `field_[fieldname]_options.txt` (UTF-8, one per line)
   - With `--show-ids`: Shows option IDs in format `Name [ID: xyz]`

2. **Add Mode** (`--field` + `--input`):
   - Fetches and saves current options
   - Reads new options from input file
   - Compares and identifies new options (not already present)
   - Displays new options and prompts for confirmation
   - Adds only new options to the field (preserves existing option IDs)

3. **Reorder Mode** (`--field` + `--input` + `--reorder`):
   - Reorders existing options based on the order in the input file
   - Options not in the input file are appended at the end
   - Preserves all option IDs (no IDs are changed)
   - Displays the new order and prompts for confirmation
   - Warns about options in input file that don't exist in the field

**Important Notes:**
- Only works with select/dropdown field types
- Option IDs are preserved when reordering (safe operation)
- New options get automatically generated IDs (sequential)
- The output file always contains only option names (easy to edit and reuse)
- All operations require confirmation before making changes

**Output:**
- Console display of current options (numbered, with optional IDs)
- Summary of actions taken (options fetched, options added, options reordered, file written)
- File saved to `field_[fieldname]_options.txt` (field name without spaces)

## Architecture

**`utils.py`** - Core library:
- **Registry Pattern**: Pre-fetch all users and user groups at startup for efficient lookups
- **Performance Optimization**: Batch API calls and in-memory filtering to minimize API requests
- Key functions:
- `load_config()`: Parse config file
- `load_registries()`: Pre-fetch users and user groups (Registry Pattern)
- `api_get()` / `make_api_request()`: Centralized API calls with SSL option
- `get_usergroup_name()`: Resolve user group IDs to names
- `get_username_from_id()`: Resolve user IDs to names
- `get_user_role()`: Get user role from registry
- `get_groups_by_prefix()`: Get all groups starting with a prefix
- `get_group_members()`: Get all user IDs in a group
- `get_group_by_name()`: Find group by exact name
- `set_user_role()`: Update user's role (admin/editor/contributor)
- `get_team_info()`: Get team information including license seat data
- `get_unique_members_by_prefix()`: Get unique user IDs across groups matching prefix
- `get_groups_matching_pattern()`: Get groups by prefix with optional suffix exclusion
- `get_users_not_in_groups()`: Get users not in any group, optionally filtered by role
- `get_users_not_in_specific_groups()`: Get users not in groups matching specific prefixes, optionally filtered by role
- `build_workspace_hierarchy()`: Build workspace tree structure using parent-child relationships (for OKR workspaces)
- `build_folder_hierarchy()`: Build folder-based workspace tree with batch folder fetching (for Product Management workspaces)
- `get_field_by_name()`: Retrieve full field configuration by name
- `get_field_options()`: Fetch field options (as names or full objects with IDs)
- `add_field_options()`: Add new options to a field (preserves existing option IDs)
- `reorder_field_options()`: Reorder field options (preserves all option IDs)
- `supports_field_options()`: Check if field type supports options
- `colorize()`: ANSI color formatting

**`config`** - Configuration file (key = value format)

**User Groups Discovery:**
- **User Groups (Global Teams)**: Fetched via undocumented `POST /api/team/user-groups/search` endpoint
- Group names resolved to actual names from API (e.g., SP_OKR_ERA_F, SP_OKR_ERA_W)
- **Workspace Groups**: Collections of workspaces (different entity, not currently used)

## Available Tools

| Tool | Description |
|------|-------------|
| `get_okr_compliance.py` | Check OKR workspace compliance with access rules in hierarchical view |
| `get_prodmgt_compliance.py` | Check Product Management workspace compliance with access rules in hierarchical view |
| `get_group_contributors.py` | Get all contributors in SP_OKR_/SP_ProdMgt_ groups or a specific group |
| `set_role.py` | Set role (editor or contributor) for group members (protects admins) |
| `get_license_usage.py` | Analyze license usage across OKR and Product Management groups |
| `set_field_options.py` | Manage custom field options for Airfocus fields via CLI |

## Security

- **No hardcoded credentials**: All sensitive data is stored in the `config` file
- **Config file ignored**: The `config` file is git-ignored by default
- **Bearer token authentication**: Uses secure API key authentication
- **No ID exposure**: User and group IDs are always resolved to names in output

## Development

### Adding New Tools

1. Create a new Python file in the project root
2. Import shared functions from `utils.py`
3. Use `make_api_request()` for all API calls
4. Use helper functions to resolve IDs to names
5. Make the script executable: `chmod +x your_tool.py`
6. Update this README with tool documentation

### API Reference

API endpoints follow the OpenAPI specification in `openapi.json`. Always refer to this file or [https://developer.airfocus.com/](https://developer.airfocus.com/) for endpoint details.

## Troubleshooting

**"Configuration file not found"**
- Ensure you've created a `config` file in the project root
- Copy `config.example` to `config` and fill in your credentials

**"API request failed"**
- Verify your API key is correct in the `config` file
- Check your internet connection
- Ensure the `base_url` is correct

**"No OKR workspaces found"**
- You may not have any workspaces with OKR namespace
- Try `--all` flag to see all workspaces
- Check if you have permission to view workspaces

## License

This is an internal tool. Refer to your organization's policies for usage guidelines.
