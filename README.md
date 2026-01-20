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
   
   Create a `config` file in the project root:
   ```ini
   apikey = your_airfocus_api_key_here
   baseurl = https://app.airfocus.com
   ```

## Usage

All tools are executed using `uv run`:

### list_okr_access.py

List OKR workspaces with access rights in hierarchical view.

```bash
uv run python list_okr_access.py
uv run python list_okr_access.py --all
uv run python list_okr_access.py --no-verify-ssl
```

**Options:**
- `--all`: Display all workspaces (default: only shows workspaces with validation issues)
- `--no-verify-ssl`: Disable SSL certificate verification

**Output Format:**
- Hierarchy using '..' prefix (no dots for root level, all lines have dots)
- Order: Color → Item Key → Access Rights
- IDs resolved to human-readable names
- Current user excluded from output

**Validation (RED highlighting):**
- Direct user access (should use groups)
- Default permission ≠ 'Comment'
- Item Key not starting with 'OKR'
- Color not in {yellow, orange, great, blue}
- Groups not starting with 'SP_OKR_' (except "Airfocus Admins")
- Groups ending with '_F' without 'Full' access
- Groups ending with '_W' without 'Write' access

**Color Display:**
- Workspace names appear in their designated color when not flagged with RED
- Color mapping: yellow → yellow, orange → orange, great → green, blue → blue

### list_group_contributors.py

List all contributors in SP_OKR_ and SP_ProdMgt_ groups or a specific group.

```bash
# List contributors in all SP_OKR_ and SP_ProdMgt_ groups (default)
uv run python list_group_contributors.py

# List contributors in a specific group
uv run python list_group_contributors.py "SP_OKR_ERA_F"

# With SSL verification disabled
uv run python list_group_contributors.py --no-verify-ssl
uv run python list_group_contributors.py "My Group" --no-verify-ssl
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
uv run python set_editor_role.py "SP_OKR_ERA_F"
uv run python set_editor_role.py "SP_OKR_ERA_W" --dry-run
uv run python set_editor_role.py "My Group" --no-verify-ssl
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
| `list_okr_access.py` | List OKR workspaces with access rights in hierarchical view |
| `list_group_contributors.py` | List all contributors in SP_OKR_ groups or a specific group |
| `set_editor_role.py` | Set editor role for contributors in a specified group (protects admins) |
| `list_contributors.py` | List members of SP_OKR_ groups with contributor role |

- `load_registries()` - **Registry Pattern**: Pre-fetch all users and groups once at startup
- `make_api_request()` - Central API request handler with authentication
- `get_username_from_id()` - Resolve user IDs to names (uses registry)
- `get_groupname_from_id()` - Resolve group IDs to names (uses registry)
- `get_current_user_id()` - Get authenticated user's ID
- `build_workspace_hierarchy()` - Build parent-child tree structure from workspaces
- `format_permission()` - Format permission values for display
- `colorize()` - Apply ANSI color codes to text

**Registry Pattern**: All tools call `load_registries()` at startup to pre-fetch users and user groups once, storing them in memory for efficient ID-to-name resolution.

**Hierarchy Standard**: The `build_workspace_hierarchy()` function fetches workspace relations from the API and builds a recursive tree structure. Hierarchy display uses '..' for each depth level.

**`config`** - Configuration file (key=value format):
- `apikey` - Your Airfocus API key
- `base_url` - Airfocus API base URL

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
