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

### get_group_contributors.py

Get all contributors in SP_OKR_ and SP_ProdMgt_ groups or a specific group.

```bash
uv run python get_group_contributors.py [group_name] [--no-verify-ssl]
```

**Arguments:**
- `group_name`: Optional - Name of a specific group to check (default: all SP_OKR_ and SP_ProdMgt_ groups)

**Options:**
- `--no-verify-ssl`: Disable SSL certificate verification

**Output:**
- Groups contributors by user group name
- Shows full name of each contributor
- Only displays groups that have contributors

### set_editor_role.py

Set editor role for contributors in a specified user group. Does not modify admin users.

```bash
uv run python set_editor_role.py <group_name> [--dry-run] [--no-verify-ssl]
```

**Arguments:**
- `group_name`: Name of the user group (required)

**Options:**
- `--dry-run`: Show what would be done without making changes
- `--no-verify-ssl`: Disable SSL certificate verification

**Behavior:**
- Only updates users with 'contributor' role
- Skips users who are already 'editor'
- **NEVER modifies users with 'admin' role**
- Skips users with any other role

**Output:**
- Shows each user being processed with their current role
- Displays summary with success/skip/error counts
- Color-coded status: GREEN (success), YELLOW (skipped), RED (failed)

### get_license_usage.py

Analyze license usage across Airfocus platform with breakdown by OKR and Product Management groups.

```bash
uv run python get_license_usage.py [--orphaned-editors] [--no-verify-ssl]
```

**Options:**
- `--orphaned-editors`: List all editors who are not part of SP_OKR_ or SP_ProdMgt_ groups (below the analysis summary)
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
- Optional: List of orphaned editors (when `--orphaned-editors` flag is used)

## Architecture

**`utils.py`** - Core library:
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
- `build_workspace_hierarchy()`: Build workspace tree structure
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
| `get_group_contributors.py` | Get all contributors in SP_OKR_/SP_ProdMgt_ groups or a specific group |
| `set_editor_role.py` | Set editor role for contributors in a specified group (protects admins) |
| `get_license_usage.py` | Analyze license usage across OKR and Product Management groups |

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
