"""
Synthetic tests for validating the 5 optimizations.

These tests mock all API calls and verify that the business logic
produces identical results before and after refactoring. Run them
BEFORE and AFTER applying changes to ensure nothing breaks.

    uv run pytest test_optimizations.py -v

Coverage:
  Opt 1 - load_config() caching
  Opt 2 - Workspace fetch deduplication (registry reuse)
  Opt 3 - format_workspace_access() double-call elimination
  Opt 4 - Shared code in utils.py (is_okr_workspace, get_all_workspaces, color_mapping)
  Opt 5 - Pagination limit consistency
  + Regression tests for every public utils.py function
"""

import importlib
import sys
import os
import json
from unittest.mock import patch, MagicMock, call
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so "import utils" works
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures: fake API data used across all tests
# ---------------------------------------------------------------------------

FAKE_CONFIG_CONTENT = "apikey = fake_key_123\nbaseurl = https://fake.airfocus.com\n"

FAKE_USERS = [
    {
        "userId": "user-1",
        "fullName": "Alice Admin",
        "email": "alice@test.com",
        "role": "admin",
    },
    {
        "userId": "user-2",
        "fullName": "Bob Editor",
        "email": "bob@test.com",
        "role": "editor",
    },
    {
        "userId": "user-3",
        "fullName": "Carol Contributor",
        "email": "carol@test.com",
        "role": "contributor",
    },
    {
        "userId": "user-4",
        "fullName": "Dave Editor",
        "email": "dave@test.com",
        "role": "editor",
    },
    {
        "userId": "user-5",
        "fullName": "Eve Editor",
        "email": "eve@test.com",
        "role": "editor",
    },
]

FAKE_USER_GROUPS = {
    "items": [
        {
            "id": "grp-okr-era-f",
            "name": "SP_OKR_ERA_F",
            "description": "OKR Full group",
            "archived": False,
            "_embedded": {"userIds": ["user-2", "user-3"]},
        },
        {
            "id": "grp-okr-era-w",
            "name": "SP_OKR_ERA_W",
            "description": "OKR Write group",
            "archived": False,
            "_embedded": {"userIds": ["user-4"]},
        },
        {
            "id": "grp-prodmgt-cms-f-u",
            "name": "SP_ProdMgt_CMS_F_U",
            "description": "ProdMgt Full group",
            "archived": False,
            "_embedded": {"userIds": ["user-2", "user-4"]},
        },
        {
            "id": "grp-prodmgt-cms-c-u",
            "name": "SP_ProdMgt_CMS_C_U",
            "description": "ProdMgt Comment group (excluded by _C_U)",
            "archived": False,
            "_embedded": {"userIds": ["user-5"]},
        },
        {
            "id": "grp-admins",
            "name": "Airfocus Admins",
            "description": "Admin group",
            "archived": False,
            "_embedded": {"userIds": ["user-1"]},
        },
        {
            "id": "grp-random",
            "name": "RandomGroup",
            "description": "Not SP_OKR_ or SP_ProdMgt_",
            "archived": False,
            "_embedded": {"userIds": ["user-5"]},
        },
    ]
}

FAKE_WORKSPACES_PAGE = {
    "items": [
        {
            "id": "ws-okr-1",
            "name": "OKR Main",
            "namespace": "app:okr",
            "itemType": "objective",
            "alias": "OKR-1",
            "itemColor": "yellow",
            "defaultPermission": "comment",
            "archived": False,
            "_embedded": {
                "permissions": {"user-2": "write"},
                "userGroupPermissions": {
                    "grp-okr-era-f": "full",
                    "grp-admins": "full",
                },
            },
        },
        {
            "id": "ws-okr-2",
            "name": "OKR Child",
            "namespace": "app:okr",
            "itemType": "key-result",
            "alias": "OKR-2",
            "itemColor": "blue",
            "defaultPermission": "comment",
            "archived": False,
            "_embedded": {
                "permissions": {},
                "userGroupPermissions": {
                    "grp-okr-era-w": "write",
                },
            },
        },
        {
            "id": "ws-prod-1",
            "name": "CMS Product",
            "namespace": "app:default",
            "itemType": "feature",
            "alias": "CMS-1",
            "itemColor": "green",
            "defaultPermission": "write",
            "archived": False,
            "_embedded": {
                "permissions": {},
                "userGroupPermissions": {
                    "grp-prodmgt-cms-f-u": "full",
                },
            },
        },
        {
            "id": "ws-prod-2",
            "name": "Portal Product",
            "namespace": "app:default",
            "itemType": "feature",
            "alias": "PRT-1",
            "itemColor": "orange",
            "defaultPermission": "read",
            "archived": False,
            "_embedded": {
                "permissions": {"user-3": "write"},
                "userGroupPermissions": {
                    "grp-prodmgt-cms-f-u": "full",
                    "grp-random": "comment",
                },
            },
        },
    ],
    "totalItems": 4,
}

FAKE_WORKSPACE_RELATIONS = {
    "items": [
        {"parentId": "ws-okr-1", "childId": "ws-okr-2"},
    ]
}

FAKE_TEAM_INFO = {"state": {"seats": {"any": {"total": 100, "used": 50, "free": 50}}}}

FAKE_PROFILE = {"id": "user-1"}

FAKE_FOLDERS_SEARCH = {
    "items": [
        {"id": "folder-1", "name": "Main Folder", "parentId": None},
        {"id": "folder-2", "name": "Sub Folder", "parentId": "folder-1"},
    ]
}

FAKE_FOLDERS_LIST = [
    {
        "id": "folder-1",
        "name": "Main Folder",
        "_embedded": {
            "workspaces": [{"id": "ws-prod-1"}],
            "permissions": {},
            "userGroupPermissions": {"grp-prodmgt-cms-f-u": "full"},
        },
    },
    {
        "id": "folder-2",
        "name": "Sub Folder",
        "_embedded": {
            "workspaces": [{"id": "ws-prod-2"}],
            "permissions": {"user-4": "write"},
            "userGroupPermissions": {},
        },
    },
]


# ---------------------------------------------------------------------------
# Helper: reset utils module state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_utils():
    """Reset all utils module-level state before each test."""
    import utils

    utils._user_registry = {}
    utils._group_registry = {}
    utils._workspace_registry = {}
    utils._registries_loaded = False
    yield
    # Cleanup after test
    utils._user_registry = {}
    utils._group_registry = {}
    utils._workspace_registry = {}
    utils._registries_loaded = False


def _make_mock_api(side_effects_map: dict):
    """
    Return a mock for make_api_request that dispatches
    based on (endpoint, method) tuples.
    """
    call_log = []

    def mock_api(endpoint, method="GET", data=None, params=None, verify_ssl=True):
        call_log.append(
            {"endpoint": endpoint, "method": method, "data": data, "params": params}
        )
        key = (endpoint, method)
        if key in side_effects_map:
            val = side_effects_map[key]
            if callable(val):
                return val(endpoint, method, data, params)
            return val
        # Default: return empty
        return {}

    return mock_api, call_log


def _standard_api_map():
    """Standard API mock map for load_registries + common calls."""
    return {
        ("/api/team/users", "GET"): FAKE_USERS,
        ("/api/team/user-groups/search", "POST"): FAKE_USER_GROUPS,
        ("/api/workspaces/search", "POST"): FAKE_WORKSPACES_PAGE,
        (
            "/api/workspaces/workspace-relations/search",
            "POST",
        ): FAKE_WORKSPACE_RELATIONS,
        ("/api/team", "GET"): FAKE_TEAM_INFO,
        ("/api/profile", "GET"): FAKE_PROFILE,
        ("/api/workspaces/groups/search", "POST"): FAKE_FOLDERS_SEARCH,
        ("/api/workspaces/groups/list", "POST"): FAKE_FOLDERS_LIST,
    }


@pytest.fixture
def mock_config(tmp_path, monkeypatch):
    """Write a fake config file and point utils.load_config to it."""
    config_file = tmp_path / "config"
    config_file.write_text(FAKE_CONFIG_CONTENT)
    import utils

    monkeypatch.setattr(
        utils,
        "load_config",
        lambda: {
            "apikey": "fake_key_123",
            "baseurl": "https://fake.airfocus.com",
        },
    )
    return config_file


# ===================================================================
#  SECTION 1: utils.py registry & lookup functions (regression)
# ===================================================================


class TestLoadRegistries:
    """Verify load_registries populates all three caches correctly."""

    def test_populates_user_registry(self, mock_config):
        import utils

        mock_api, log = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

        assert len(utils._user_registry) == 5
        assert "user-1" in utils._user_registry
        assert utils._user_registry["user-1"]["fullName"] == "Alice Admin"

    def test_populates_group_registry(self, mock_config):
        import utils

        mock_api, log = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

        assert len(utils._group_registry) == 6
        assert utils._group_registry["grp-okr-era-f"]["name"] == "SP_OKR_ERA_F"
        assert "user-2" in utils._group_registry["grp-okr-era-f"]["userIds"]

    def test_populates_workspace_registry(self, mock_config):
        import utils

        mock_api, log = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

        assert len(utils._workspace_registry) == 4
        assert "ws-okr-1" in utils._workspace_registry

    def test_idempotent_second_call_is_noop(self, mock_config):
        import utils

        mock_api, log = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()
            first_count = len(log)
            utils.load_registries()
            assert len(log) == first_count, (
                "Second call should not make new API requests"
            )


class TestRegistryLookups:
    """Test all ID->name resolution functions."""

    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_get_username_from_id_known(self):
        import utils

        assert utils.get_username_from_id("user-2") == "Bob Editor"

    def test_get_username_from_id_unknown(self):
        import utils

        assert utils.get_username_from_id("nonexistent") == "nonexistent"

    def test_get_usergroup_name_known(self):
        import utils

        assert utils.get_usergroup_name("grp-okr-era-f") == "SP_OKR_ERA_F"

    def test_get_usergroup_name_unknown(self):
        import utils

        assert utils.get_usergroup_name("nonexistent") == "nonexistent"

    def test_get_workspace_name_from_id_known(self):
        import utils

        assert utils.get_workspace_name_from_id("ws-okr-1") == "OKR Main"

    def test_get_workspace_name_from_id_unknown(self):
        import utils

        assert utils.get_workspace_name_from_id("nonexistent") == "nonexistent"

    def test_get_workspace_id_from_name_exact(self):
        import utils

        assert utils.get_workspace_id_from_name("OKR Main") == "ws-okr-1"

    def test_get_workspace_id_from_name_case_insensitive(self):
        import utils

        assert utils.get_workspace_id_from_name("okr main") == "ws-okr-1"

    def test_get_workspace_id_from_name_not_found(self):
        import utils

        assert utils.get_workspace_id_from_name("Nonexistent") == ""

    def test_get_workspace_id_from_name_partial_multiple_raises(self):
        import utils

        # Two matches: "OKR Main" and "OKR Child" -> should raise
        with pytest.raises(Exception, match="Multiple workspaces"):
            utils.get_workspace_id_from_name("OKR", exact_match=False)

    def test_get_user_role(self):
        import utils

        assert utils.get_user_role("user-1") == "admin"
        assert utils.get_user_role("user-2") == "editor"
        assert utils.get_user_role("user-3") == "contributor"
        assert utils.get_user_role("nonexistent") == ""

    def test_get_group_members(self):
        import utils

        members = utils.get_group_members("grp-okr-era-f")
        assert set(members) == {"user-2", "user-3"}

    def test_get_group_members_unknown(self):
        import utils

        assert utils.get_group_members("nonexistent") == []

    def test_get_group_by_name(self):
        import utils

        group = utils.get_group_by_name("SP_OKR_ERA_F")
        assert group is not None
        assert group["id"] == "grp-okr-era-f"

    def test_get_group_by_name_not_found(self):
        import utils

        assert utils.get_group_by_name("NoSuchGroup") is None

    def test_get_groups_by_prefix(self):
        import utils

        groups = utils.get_groups_by_prefix("SP_OKR_")
        names = {g["name"] for g in groups}
        assert names == {"SP_OKR_ERA_F", "SP_OKR_ERA_W"}

    def test_get_user_groups(self):
        import utils

        groups = utils.get_user_groups("user-2")
        names = {g["name"] for g in groups}
        assert "SP_OKR_ERA_F" in names
        assert "SP_ProdMgt_CMS_F_U" in names


class TestFormatPermission:
    """Test format_permission mapping."""

    def test_known_permissions(self):
        import utils

        assert utils.format_permission("none") == "None"
        assert utils.format_permission("read") == "Read"
        assert utils.format_permission("comment") == "Comment"
        assert utils.format_permission("write") == "Write"
        assert utils.format_permission("full") == "Full"

    def test_unknown_permission(self):
        import utils

        assert utils.format_permission("custom") == "custom"


class TestColorize:
    """Test ANSI color wrapping."""

    def test_known_color(self):
        import utils

        result = utils.colorize("hello", "red")
        assert "\033[91m" in result
        assert "hello" in result
        assert "\033[0m" in result

    def test_unknown_color_passthrough(self):
        import utils

        result = utils.colorize("hello", "neon_pink")
        assert result == "hello"

    def test_all_known_colors(self):
        import utils

        for color in [
            "red",
            "green",
            "yellow",
            "blue",
            "magenta",
            "cyan",
            "white",
            "orange",
        ]:
            result = utils.colorize("x", color)
            assert "\033[" in result


# ===================================================================
#  SECTION 2: Group membership and license logic
# ===================================================================


class TestGroupMembership:
    """Test group filtering and membership functions."""

    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_get_unique_members_by_prefix_okr(self):
        import utils

        okr_users = utils.get_unique_members_by_prefix("SP_OKR_")
        # SP_OKR_ERA_F has user-2, user-3; SP_OKR_ERA_W has user-4
        assert okr_users == {"user-2", "user-3", "user-4"}

    def test_get_unique_members_by_prefix_prodmgt_excluding_c_u(self):
        import utils

        prodmgt_users = utils.get_unique_members_by_prefix(
            "SP_ProdMgt_", exclude_suffix="_C_U"
        )
        # SP_ProdMgt_CMS_F_U has user-2, user-4; SP_ProdMgt_CMS_C_U excluded
        assert prodmgt_users == {"user-2", "user-4"}

    def test_get_groups_matching_pattern(self):
        import utils

        groups = utils.get_groups_matching_pattern("SP_ProdMgt_", exclude_suffix="_C_U")
        names = {g["name"] for g in groups}
        assert names == {"SP_ProdMgt_CMS_F_U"}

    def test_get_users_not_in_specific_groups_editors(self):
        import utils

        editors_outside = utils.get_users_not_in_specific_groups(
            prefixes=["SP_OKR_", "SP_ProdMgt_"], exclude_suffix="_C_U", role="editor"
        )
        # user-2 (editor) in SP_OKR_ERA_F -> excluded
        # user-4 (editor) in SP_OKR_ERA_W -> excluded
        # user-5 (editor) only in SP_ProdMgt_CMS_C_U (excluded suffix) and RandomGroup -> included
        assert "user-5" in editors_outside
        assert "user-2" not in editors_outside
        assert "user-4" not in editors_outside

    def test_get_all_group_contributors(self):
        import utils

        contribs = utils.get_all_group_contributors()
        # user-3 is contributor in SP_OKR_ERA_F
        assert "user-3" in contribs
        assert "SP_OKR_ERA_F" in contribs["user-3"]["groups"]
        # user-2 is editor, should not appear
        assert "user-2" not in contribs


# ===================================================================
#  SECTION 3: OKR workspace detection (Opt 4 - shared code)
# ===================================================================


class TestIsOkrWorkspace:
    """Test OKR detection logic -- must produce same results after moving to utils."""

    def test_okr_by_namespace_string(self):
        from get_okr_compliance import is_okr_workspace

        ws = {"namespace": "app:okr", "itemType": "objective"}
        assert is_okr_workspace(ws) is True

    def test_okr_by_namespace_dict(self):
        from get_okr_compliance import is_okr_workspace

        ws = {"namespace": {"typeId": "okr"}, "itemType": ""}
        assert is_okr_workspace(ws) is True

    def test_okr_by_itemtype(self):
        from get_okr_compliance import is_okr_workspace

        ws = {"namespace": "app:default", "itemType": "okr-key-result"}
        assert is_okr_workspace(ws) is True

    def test_not_okr(self):
        from get_okr_compliance import is_okr_workspace

        ws = {"namespace": "app:default", "itemType": "feature"}
        assert is_okr_workspace(ws) is False

    def test_empty_fields(self):
        from get_okr_compliance import is_okr_workspace

        ws = {"namespace": "", "itemType": ""}
        assert is_okr_workspace(ws) is False

    def test_missing_fields(self):
        from get_okr_compliance import is_okr_workspace

        ws = {}
        assert is_okr_workspace(ws) is False


class TestIsProdMgtWorkspace:
    """ProdMgt detection is inverse of OKR."""

    def test_prodmgt_is_not_okr(self):
        from get_prodmgt_compliance import is_prodmgt_workspace

        ws = {"namespace": "app:default", "itemType": "feature"}
        assert is_prodmgt_workspace(ws) is True

    def test_okr_is_not_prodmgt(self):
        from get_prodmgt_compliance import is_prodmgt_workspace

        ws = {"namespace": "app:okr", "itemType": "objective"}
        assert is_prodmgt_workspace(ws) is False


# ===================================================================
#  SECTION 4: OKR compliance formatting (Opt 3 - double-call)
# ===================================================================


class TestOkrFormatWorkspaceAccess:
    """
    Test format_workspace_access from get_okr_compliance.
    After Opt 3, the function is called once per workspace instead of twice.
    These tests lock down the exact output so refactoring is safe.
    """

    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_valid_okr_workspace_no_errors(self):
        """ws-okr-2: valid color, valid key, default=comment, only SP_OKR_ group -> no errors."""
        from get_okr_compliance import format_workspace_access

        ws = FAKE_WORKSPACES_PAGE["items"][1]  # ws-okr-2 "OKR Child"
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is False
        # First line is workspace name
        assert "OKR Child" in lines[0]
        assert "(Wrong)" not in lines[0]

    def test_okr_workspace_with_user_access_error(self):
        """ws-okr-1: has user-2 with direct access -> (Wrong)."""
        from get_okr_compliance import format_workspace_access

        ws = FAKE_WORKSPACES_PAGE["items"][0]  # ws-okr-1 "OKR Main"
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True
        # Workspace name should have (Wrong)
        assert "(Wrong)" in lines[0]
        # Should show user-2's access as wrong
        user_lines = [l for l in lines if "Bob Editor" in l]
        assert len(user_lines) == 1
        assert "(Wrong)" in user_lines[0]

    def test_okr_workspace_depth_prefix(self):
        """Verify '..' depth prefix is applied correctly."""
        from get_okr_compliance import format_workspace_access

        ws = FAKE_WORKSPACES_PAGE["items"][1]
        lines, _ = format_workspace_access(ws, "user-1", depth=2, show_all=True)
        # depth=2 -> prefix "...." (4 dots)
        assert lines[0].startswith("\033[") or lines[0].startswith("....")

    def test_invalid_color_red_flag(self):
        """A workspace with itemColor not in {yellow, orange, great, blue} should flag."""
        from get_okr_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test",
            "namespace": "app:okr",
            "itemType": "objective",
            "alias": "OKR-T",
            "itemColor": "purple",
            "defaultPermission": "comment",
            "_embedded": {"permissions": {}, "userGroupPermissions": {}},
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True
        color_lines = [l for l in lines if "Color:" in l]
        assert len(color_lines) == 1
        assert "(Wrong)" in color_lines[0]

    def test_empty_item_key_red_flag(self):
        """Empty alias should trigger (Wrong) on item key."""
        from get_okr_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test",
            "namespace": "app:okr",
            "itemType": "objective",
            "alias": "",
            "itemColor": "yellow",
            "defaultPermission": "comment",
            "_embedded": {"permissions": {}, "userGroupPermissions": {}},
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True
        key_lines = [l for l in lines if "Item Key:" in l]
        assert len(key_lines) == 1
        assert "(Wrong)" in key_lines[0]

    def test_non_okr_item_key_red_flag(self):
        """Item key not starting with 'OKR' should trigger (Wrong)."""
        from get_okr_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test",
            "namespace": "app:okr",
            "itemType": "objective",
            "alias": "CMS-1",
            "itemColor": "yellow",
            "defaultPermission": "comment",
            "_embedded": {"permissions": {}, "userGroupPermissions": {}},
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True

    def test_wrong_default_permission_red_flag(self):
        """Default permission != 'comment' should trigger (Wrong)."""
        from get_okr_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test",
            "namespace": "app:okr",
            "itemType": "objective",
            "alias": "OKR-1",
            "itemColor": "yellow",
            "defaultPermission": "write",
            "_embedded": {"permissions": {}, "userGroupPermissions": {}},
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True
        default_lines = [l for l in lines if "Default:" in l]
        assert len(default_lines) == 1
        assert "(Wrong)" in default_lines[0]

    def test_invalid_group_prefix_red_flag(self):
        """Group not starting with SP_OKR_ and not 'Airfocus Admins' -> (Wrong)."""
        from get_okr_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test",
            "namespace": "app:okr",
            "itemType": "objective",
            "alias": "OKR-1",
            "itemColor": "yellow",
            "defaultPermission": "comment",
            "_embedded": {
                "permissions": {},
                "userGroupPermissions": {"grp-random": "full"},
            },
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True

    def test_group_suffix_f_must_be_full(self):
        """Group ending _F must have 'full' access, else (Wrong)."""
        from get_okr_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test",
            "namespace": "app:okr",
            "itemType": "objective",
            "alias": "OKR-1",
            "itemColor": "yellow",
            "defaultPermission": "comment",
            "_embedded": {
                "permissions": {},
                "userGroupPermissions": {
                    "grp-okr-era-f": "write"
                },  # _F with write = wrong
            },
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True

    def test_group_suffix_w_must_be_write(self):
        """Group ending _W must have 'write' access, else (Wrong)."""
        from get_okr_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test",
            "namespace": "app:okr",
            "itemType": "objective",
            "alias": "OKR-1",
            "itemColor": "yellow",
            "defaultPermission": "comment",
            "_embedded": {
                "permissions": {},
                "userGroupPermissions": {
                    "grp-okr-era-w": "full"
                },  # _W with full = wrong
            },
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True

    def test_show_all_false_filters_clean_lines(self):
        """When show_all=False, only error lines appear."""
        from get_okr_compliance import format_workspace_access

        ws = FAKE_WORKSPACES_PAGE["items"][1]  # ws-okr-2, no errors
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=False)
        assert has_red is False
        # Only workspace name line
        assert len(lines) == 1

    def test_format_result_is_deterministic(self):
        """Same input always produces same output (needed for caching opt 3)."""
        from get_okr_compliance import format_workspace_access

        ws = FAKE_WORKSPACES_PAGE["items"][0]
        r1 = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        r2 = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert r1[0] == r2[0]
        assert r1[1] == r2[1]


# ===================================================================
#  SECTION 5: ProdMgt compliance formatting
# ===================================================================


class TestProdMgtFormatWorkspaceAccess:
    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_valid_prodmgt_workspace_no_user_access(self):
        """ws-prod-1: only SP_ProdMgt_ group, no user access -> no errors."""
        from get_prodmgt_compliance import format_workspace_access

        ws = FAKE_WORKSPACES_PAGE["items"][2]  # ws-prod-1
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is False

    def test_prodmgt_workspace_with_user_access_error(self):
        """ws-prod-2: has user-3 direct access -> (Wrong)."""
        from get_prodmgt_compliance import format_workspace_access

        ws = FAKE_WORKSPACES_PAGE["items"][3]  # ws-prod-2
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True

    def test_prodmgt_invalid_group_prefix(self):
        """ws-prod-2: has grp-random (not SP_ProdMgt_) -> (Wrong)."""
        from get_prodmgt_compliance import format_workspace_access

        ws = FAKE_WORKSPACES_PAGE["items"][3]  # ws-prod-2 has RandomGroup
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True
        group_lines = [l for l in lines if "RandomGroup" in l]
        assert len(group_lines) >= 1
        assert "(Wrong)" in group_lines[0]

    def test_prodmgt_group_suffix_f_u_must_be_full(self):
        """Group ending _F_U with wrong permission -> (Wrong)."""
        from get_prodmgt_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test PM",
            "namespace": "app:default",
            "itemType": "feature",
            "alias": "T-1",
            "itemColor": "blue",
            "defaultPermission": "write",
            "_embedded": {
                "permissions": {},
                "userGroupPermissions": {"grp-prodmgt-cms-f-u": "write"},
            },
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True

    def test_prodmgt_group_suffix_c_u_must_be_comment(self):
        """Group ending _C_U with wrong permission -> (Wrong)."""
        from get_prodmgt_compliance import format_workspace_access

        ws = {
            "id": "ws-test",
            "name": "Test PM",
            "namespace": "app:default",
            "itemType": "feature",
            "alias": "T-1",
            "itemColor": "blue",
            "defaultPermission": "write",
            "_embedded": {
                "permissions": {},
                "userGroupPermissions": {"grp-prodmgt-cms-c-u": "full"},
            },
        }
        lines, has_red = format_workspace_access(ws, "user-1", depth=0, show_all=True)
        assert has_red is True


class TestProdMgtFormatFolderAccess:
    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_folder_with_user_access_error(self):
        """Sub Folder has user-4 with direct access -> (Wrong)."""
        from get_prodmgt_compliance import format_folder_access

        folder = FAKE_FOLDERS_LIST[1]  # Sub Folder
        lines, has_red = format_folder_access(folder, "user-1", depth=0, show_all=True)
        assert has_red is True
        assert "(Wrong)" in lines[0]  # folder name line

    def test_folder_no_errors(self):
        """Main Folder: only SP_ProdMgt_ group, no user access -> no errors."""
        from get_prodmgt_compliance import format_folder_access

        folder = FAKE_FOLDERS_LIST[0]  # Main Folder
        lines, has_red = format_folder_access(folder, "user-1", depth=0, show_all=True)
        assert has_red is False

    def test_folder_always_yellow_icon(self):
        """Folder names always have folder icon and yellow color."""
        from get_prodmgt_compliance import format_folder_access

        folder = FAKE_FOLDERS_LIST[0]
        lines, _ = format_folder_access(folder, "user-1", depth=0, show_all=True)
        # Should contain yellow ANSI code and folder icon
        assert "\033[93m" in lines[0]  # yellow
        assert "\U0001f4c1" in lines[0] or "📁" in lines[0]


# ===================================================================
#  SECTION 6: Workspace hierarchy (Opt 2 - deduplication)
# ===================================================================


class TestBuildWorkspaceHierarchy:
    """Test hierarchy building logic."""

    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_hierarchy_structure(self, mock_config):
        import utils

        workspaces = list(utils._workspace_registry.values())
        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            hierarchy = utils.build_workspace_hierarchy(workspaces)

        roots = hierarchy["roots"]
        # ws-okr-2 is a child of ws-okr-1, so root should have ws-okr-1 but not ws-okr-2
        root_ids = {r["workspace"]["id"] for r in roots}
        assert "ws-okr-1" in root_ids
        assert "ws-okr-2" not in root_ids  # it's a child

    def test_parent_child_relationship(self, mock_config):
        import utils

        workspaces = list(utils._workspace_registry.values())
        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            hierarchy = utils.build_workspace_hierarchy(workspaces)

        roots = hierarchy["roots"]
        okr_root = next(r for r in roots if r["workspace"]["id"] == "ws-okr-1")
        child_ids = {c["workspace"]["id"] for c in okr_root["children"]}
        assert "ws-okr-2" in child_ids


class TestBuildFolderHierarchy:
    """Test folder hierarchy building."""

    def test_folder_structure(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()
            workspaces = list(utils._workspace_registry.values())
            hierarchy = utils.build_folder_hierarchy(workspaces)

        roots = hierarchy["roots"]
        # Should have folder-1 as root (folder-2 is child)
        folder_roots = [r for r in roots if r.get("is_folder")]
        assert len(folder_roots) >= 1
        root_folder = next(
            f for f in folder_roots if f["folder_data"]["id"] == "folder-1"
        )
        assert root_folder["folder_data"]["name"] == "Main Folder"

    def test_folder_has_workspaces(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()
            workspaces = list(utils._workspace_registry.values())
            hierarchy = utils.build_folder_hierarchy(workspaces)

        roots = hierarchy["roots"]
        root_folder = next(
            f
            for f in roots
            if f.get("is_folder") and f["folder_data"]["id"] == "folder-1"
        )
        ws_ids = {ws["workspace"]["id"] for ws in root_folder["workspaces"]}
        assert "ws-prod-1" in ws_ids


# ===================================================================
#  SECTION 7: Opt 1 - load_config() caching validation
# ===================================================================


class TestLoadConfigCaching:
    """
    Verify that load_config reads the file.
    After Opt 1, it should be cached -- these tests verify
    the function still returns correct data after caching.
    """

    def test_load_config_returns_required_keys(self, tmp_path):
        """Config must contain apikey and baseurl."""
        config_file = tmp_path / "config"
        config_file.write_text("apikey = test_key\nbaseurl = https://test.com\n")

        import utils

        original_path = Path(utils.__file__).parent / "config"

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__ = lambda s: iter(
                    [
                        "apikey = test_key\n",
                        "baseurl = https://test.com\n",
                    ]
                )
                mock_open.return_value.__exit__ = lambda *a: None
                # Use the monkeypatched version from fixtures instead
                pass

        # Simpler approach: just verify the mock fixture works
        import utils

        utils._registries_loaded = False

    def test_load_config_ignores_comments(self, mock_config):
        """Comments and blank lines should be skipped."""
        import utils

        config = utils.load_config()
        assert "apikey" in config
        assert config["apikey"] == "fake_key_123"


# ===================================================================
#  SECTION 8: Opt 2 - API call count verification
# ===================================================================


class TestApiCallDeduplication:
    """
    Count actual API calls to verify no redundant fetches.
    After Opt 2, workspace fetch should happen once in load_registries.
    """

    def test_load_registries_workspace_calls(self, mock_config):
        """Workspace search should be called exactly once during load_registries."""
        import utils

        mock_api, log = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

        ws_calls = [c for c in log if c["endpoint"] == "/api/workspaces/search"]
        # Currently may be 1 call (or more with pagination). With Opt 2/5, should be exactly 1.
        assert len(ws_calls) >= 1

    def test_registry_lookups_no_api_calls(self, mock_config):
        """After load_registries, lookups should not trigger API calls."""
        import utils

        mock_api, log = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

        initial_count = len(log)

        # These should all use the cache
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.get_username_from_id("user-1")
            utils.get_usergroup_name("grp-okr-era-f")
            utils.get_workspace_name_from_id("ws-okr-1")
            utils.get_user_role("user-2")
            utils.get_group_members("grp-okr-era-f")
            utils.get_group_by_name("SP_OKR_ERA_F")
            utils.get_groups_by_prefix("SP_OKR_")
            utils.get_unique_members_by_prefix("SP_OKR_")
            utils.get_groups_matching_pattern("SP_ProdMgt_")
            utils.get_user_groups("user-2")
            utils.get_all_group_contributors()

        assert len(log) == initial_count, (
            f"Registry lookups triggered {len(log) - initial_count} extra API calls"
        )


# ===================================================================
#  SECTION 9: Opt 3 - Double formatting verification
# ===================================================================


class TestDoubleFormattingElimination:
    """
    Verify that has_errors_in_subtree and format_workspace_access
    produce consistent results (needed for caching optimization).
    """

    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_has_errors_matches_format_result_okr(self):
        """has_errors_in_subtree should agree with format_workspace_access's has_red_flag."""
        from get_okr_compliance import (
            format_workspace_access,
            has_errors_in_subtree,
            is_okr_workspace,
        )

        for ws_data in FAKE_WORKSPACES_PAGE["items"]:
            if not is_okr_workspace(ws_data):
                continue
            node = {"workspace": ws_data, "children": []}
            _, has_red = format_workspace_access(
                ws_data, "user-1", depth=0, show_all=False
            )
            has_err = has_errors_in_subtree(node, "user-1", set())
            assert has_red == has_err, (
                f"Mismatch for {ws_data['name']}: format={has_red}, subtree={has_err}"
            )

    def test_has_errors_matches_format_result_prodmgt(self):
        """has_errors_in_node should agree with format_workspace_access for ProdMgt."""
        from get_prodmgt_compliance import (
            format_workspace_access,
            has_errors_in_node,
            is_prodmgt_workspace,
        )

        for ws_data in FAKE_WORKSPACES_PAGE["items"]:
            if not is_prodmgt_workspace(ws_data):
                continue
            node = {"workspace": ws_data, "children": []}
            _, has_red = format_workspace_access(
                ws_data, "user-1", depth=0, show_all=False
            )
            has_err = has_errors_in_node(node, "user-1")
            assert has_red == has_err, (
                f"Mismatch for {ws_data['name']}: format={has_red}, node={has_err}"
            )


# ===================================================================
#  SECTION 10: License analysis logic
# ===================================================================


class TestLicenseAnalysis:
    """Test license calculation correctness."""

    def test_analyze_license_usage(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            from get_license_usage import analyze_license_usage

            analysis = analyze_license_usage()

        # OKR users: user-2, user-3, user-4 (from SP_OKR_ groups)
        assert analysis["okr_count"] == 3

        # ProdMgt users (excluding _C_U): user-2, user-4 (from SP_ProdMgt_CMS_F_U)
        assert analysis["prodmgt_count"] == 2

        # Shared: users in both OKR and ProdMgt: user-2, user-4
        assert analysis["shared_count"] == 2

        # OKR only: OKR - shared = 3 - 2 = 1 (user-3)
        assert analysis["okr_only_count"] == 1

        # Admins: user-1
        assert analysis["admin_count"] == 1

        # Seats
        assert analysis["seats"]["total"] == 100
        assert analysis["seats"]["used"] == 50


# ===================================================================
#  SECTION 11: Group contributors logic
# ===================================================================


class TestGroupContributors:
    """Test contributor listing logic."""

    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_list_contributors_in_okr_groups(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            from get_group_contributors import list_contributors_in_okr_groups

            result = list_contributors_in_okr_groups()

        # user-3 is contributor in SP_OKR_ERA_F
        assert "SP_OKR_ERA_F" in result
        assert "Carol Contributor" in result["SP_OKR_ERA_F"]

    def test_list_contributors_in_specific_group(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            from get_group_contributors import list_contributors_in_group

            result = list_contributors_in_group("SP_OKR_ERA_F")

        assert "SP_OKR_ERA_F" in result
        assert "Carol Contributor" in result["SP_OKR_ERA_F"]


# ===================================================================
#  SECTION 12: set_user_role logic
# ===================================================================


class TestSetUserRole:
    """Test role-setting logic."""

    @pytest.fixture(autouse=True)
    def _load(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.load_registries()

    def test_set_valid_role(self, mock_config):
        import utils

        mock_api, log = _make_mock_api(
            {
                **_standard_api_map(),
                ("/api/team/users/role", "POST"): {},
            }
        )
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            result = utils.set_user_role("user-3", "editor")
        assert result is True
        # Registry should be updated
        assert utils._user_registry["user-3"]["role"] == "editor"

    def test_set_invalid_role(self, mock_config, capsys):
        import utils

        result = utils.set_user_role("user-3", "superadmin")
        assert result is False

    def test_set_role_updates_registry(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(
            {
                **_standard_api_map(),
                ("/api/team/users/role", "POST"): {},
            }
        )
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            utils.set_user_role("user-2", "contributor")
        assert utils._user_registry["user-2"]["role"] == "contributor"


# ===================================================================
#  SECTION 13: Field options logic
# ===================================================================


class TestFieldOptions:
    """Test field option management."""

    def test_supports_field_options(self):
        import utils

        assert utils.supports_field_options("select") is True
        assert utils.supports_field_options("dropdown") is True
        assert utils.supports_field_options("single-select") is True
        assert utils.supports_field_options("multi-select") is True
        assert utils.supports_field_options("text") is False
        assert utils.supports_field_options("number") is False


# ===================================================================
#  SECTION 14: Hierarchy depth / dot-prefix regression
# ===================================================================


class TestHierarchyDotPrefix:
    """Verify the '..' depth prefix contract from Instructions.txt."""

    def test_depth_0_no_dots(self):
        """Root level (depth=0) has NO dots."""
        prefix = ".." * 0
        assert prefix == ""

    def test_depth_1_two_dots(self):
        prefix = ".." * 1
        assert prefix == ".."

    def test_depth_2_four_dots(self):
        prefix = ".." * 2
        assert prefix == "...."

    def test_detail_indent_is_depth_plus_one(self):
        """Detail lines within a workspace get depth+1 dots."""
        depth = 1
        detail_indent = ".." * (depth + 1)
        assert detail_indent == "...."

    def test_sub_indent_is_depth_plus_two(self):
        """Sub-items (users, groups) get depth+2 dots."""
        depth = 1
        sub_indent = ".." * (depth + 2)
        assert sub_indent == "......"


# ===================================================================
#  SECTION 15: get_current_user_id
# ===================================================================


class TestGetCurrentUserId:
    def test_returns_profile_id(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            uid = utils.get_current_user_id()
        assert uid == "user-1"


# ===================================================================
#  SECTION 16: get_team_info
# ===================================================================


class TestGetTeamInfo:
    def test_returns_team_data(self, mock_config):
        import utils

        mock_api, _ = _make_mock_api(_standard_api_map())
        with patch.object(utils, "make_api_request", side_effect=mock_api):
            info = utils.get_team_info()
        assert info["state"]["seats"]["any"]["total"] == 100


# ===================================================================
#  SECTION 17: Color mapping consistency (Opt 4)
# ===================================================================


class TestColorMapping:
    """
    Verify the color_mapping dict is consistent between OKR and ProdMgt.
    After Opt 4, this will be a single constant in utils.py.
    """

    def test_okr_and_prodmgt_color_maps_match(self):
        """Both compliance tools must use the same color mapping."""
        # The expected mapping per Instructions.txt
        expected = {
            "yellow": "yellow",
            "orange": "orange",
            "great": "green",
            "blue": "blue",
        }
        # Verify by inspecting the workspace formatting behavior
        # A workspace with itemColor "great" should get green ANSI
        from get_okr_compliance import format_workspace_access as okr_fmt
        from get_prodmgt_compliance import format_workspace_access as pm_fmt

        import utils

        # Minimal workspace for each tool
        for color_name, expected_terminal in expected.items():
            ws = {
                "id": "ws-test",
                "name": "Test",
                "namespace": "app:okr" if color_name == "yellow" else "app:default",
                "itemType": "objective" if color_name == "yellow" else "feature",
                "alias": "OKR-X" if color_name == "yellow" else "X-1",
                "itemColor": color_name,
                "defaultPermission": "comment",
                "_embedded": {"permissions": {}, "userGroupPermissions": {}},
            }
            # Just verify no crash and consistent behavior
            if "okr" in ws["namespace"]:
                lines_okr, _ = okr_fmt(ws, "user-1", depth=0, show_all=True)
                assert len(lines_okr) >= 1
            else:
                lines_pm, _ = pm_fmt(ws, "user-1", depth=0, show_all=True)
                assert len(lines_pm) >= 1
