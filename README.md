# pyAirfocusTools

Secure, modular CLI toolset for interacting with the Airfocus API.

## Requirements

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

1. **Clone or download this repository**

2. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies**:
   ```bash
   uv sync
   ```

4. **Configure API credentials**:
   
   Create a `config` file in the project root with your API key:
   ```ini
   apikey = your_airfocus_api_key_here
   base_url = https://app.airfocus.com
   
   # User Group Mappings (optional but recommended)
   # User groups are not exposed via the public API, so add them manually here
   # Find group IDs in workspace permissions, then add mappings like:
   usergroup_<UUID> = Group Name
   ```

   You can find your API key in your Airfocus account settings.
   
   **Note**: User groups (collections of users) are not accessible via the Airfocus API. 
   If workspaces have user group permissions, you'll need to manually add the mappings 
   to the config file in the format shown above. Otherwise, they'll display as 
   "(Unknown Group: xxx...)". Workspace groups (collections of workspaces) are 
   automatically fetched from the API.

## Usage

All tools are executed using `uv run` to ensure they use the correct virtual environment.

### List OKR Workspaces Access

Display all OKR-related workspaces with their access permissions in a hierarchical view.

```bash
uv run python list_okr_access.py
```

**Options:**
- `--all`: Include all workspaces, not just OKR workspaces

**Features:**
- Hierarchical view of workspaces (using '..' for depth levels, no dots for root level)
- Displays workspace name, item key, and color
- Resolves user and group IDs to human-readable names
- Excludes the current authenticated user from the output
- RED highlighting for:
  - Workspaces with direct user access (should use groups instead)
  - Default permissions not set to 'Comment'
  - Groups ending with '_F' without 'Full' access
  - Groups ending with '_W' without 'Write' access

## Available Tools

| Tool | Description |
|------|-------------|
| `list_okr_access.py` | List OKR workspaces with access rights in hierarchical view |

## Architecture

### Project Structure

```
pyAirfocusTools/
├── config              # API credentials and settings (git-ignored)
├── config.example      # Template for config file
├── utils.py            # Shared utility functions
├── list_okr_access.py  # OKR workspace access listing tool
├── pyproject.toml      # Project dependencies
├── README.md           # This file
└── openapi.json        # API specification
```

### Core Modules

**`utils.py`** - Shared library providing:
- `load_config()` - Parse configuration file
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
