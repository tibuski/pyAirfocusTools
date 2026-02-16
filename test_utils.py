"""
Unit tests for utils.py using Python's built-in unittest framework.
No external dependencies required (no pytest).

Run tests with:
    uv run python -m unittest test_utils.py -v
    or
    python -m unittest test_utils.py -v
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import sys
import json
from pathlib import Path
from io import StringIO


class TestLoadConfig(unittest.TestCase):
    """Test configuration loading functionality."""

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="apikey = test_key\nbaseurl = https://test.airfocus.com\n")
    def test_load_config_success(self, mock_file, mock_exists):
        """Test successful config loading with valid data."""
        mock_exists.return_value = True
        
        import utils
        config = utils.load_config()
        
        self.assertEqual(config['apikey'], 'test_key')
        self.assertEqual(config['baseurl'], 'https://test.airfocus.com')

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="# Comment line\n\napikey = key123\nbaseurl = https://api.test.com\n")
    def test_load_config_ignores_comments_and_blanks(self, mock_file, mock_exists):
        """Test that config parser ignores comments and blank lines."""
        mock_exists.return_value = True
        
        import utils
        config = utils.load_config()
        
        self.assertEqual(config['apikey'], 'key123')
        self.assertEqual(config['baseurl'], 'https://api.test.com')

    @patch('pathlib.Path.exists')
    @patch('sys.exit')
    def test_load_config_missing_file(self, mock_exit, mock_exists):
        """Test error handling when config file doesn't exist."""
        mock_exists.return_value = False
        mock_exit.side_effect = SystemExit
        
        import utils
        with self.assertRaises(SystemExit):
            utils.load_config()

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="apikey = test_key\n")
    @patch('sys.exit')
    def test_load_config_missing_required_keys(self, mock_exit, mock_file, mock_exists):
        """Test error handling when required keys are missing."""
        mock_exists.return_value = True
        mock_exit.side_effect = SystemExit
        
        import utils
        with self.assertRaises(SystemExit):
            utils.load_config()


class TestIsOkrWorkspace(unittest.TestCase):
    """Test OKR workspace detection logic."""

    def setUp(self):
        """Set up test fixtures."""
        import utils
        self.is_okr_workspace = utils.is_okr_workspace

    def test_okr_by_namespace_string(self):
        """Test OKR detection with string namespace containing 'okr'."""
        workspace = {"namespace": "app:okr", "itemType": "objective"}
        self.assertTrue(self.is_okr_workspace(workspace))

    def test_okr_by_namespace_dict(self):
        """Test OKR detection with dict namespace containing 'okr'."""
        workspace = {"namespace": {"typeId": "okr"}, "itemType": "feature"}
        self.assertTrue(self.is_okr_workspace(workspace))

    def test_okr_by_itemtype(self):
        """Test OKR detection by item type containing 'okr'."""
        workspace = {"namespace": "app:default", "itemType": "okr-key-result"}
        self.assertTrue(self.is_okr_workspace(workspace))

    def test_not_okr_workspace(self):
        """Test non-OKR workspace detection."""
        workspace = {"namespace": "app:default", "itemType": "feature"}
        self.assertFalse(self.is_okr_workspace(workspace))

    def test_okr_case_insensitive(self):
        """Test OKR detection is case-insensitive."""
        workspace = {"namespace": "app:OKR", "itemType": ""}
        self.assertTrue(self.is_okr_workspace(workspace))

    def test_empty_workspace(self):
        """Test handling of empty workspace dictionary."""
        workspace = {}
        self.assertFalse(self.is_okr_workspace(workspace))

    def test_missing_fields(self):
        """Test handling of workspace with missing namespace and itemType."""
        workspace = {"id": "ws-123", "name": "Test"}
        self.assertFalse(self.is_okr_workspace(workspace))


class TestRegistryPattern(unittest.TestCase):
    """Test the registry pattern for caching users, groups, and workspaces."""

    def setUp(self):
        """Set up test fixtures and reset registry state."""
        import utils
        # Reset registry state before each test
        utils._user_registry = {}
        utils._group_registry = {}
        utils._workspace_registry = {}
        utils._registries_loaded = False

    def tearDown(self):
        """Clean up after each test."""
        import utils
        utils._user_registry = {}
        utils._group_registry = {}
        utils._workspace_registry = {}
        utils._registries_loaded = False

    @patch('utils.make_api_request')
    def test_load_registries_populates_users(self, mock_api):
        """Test that load_registries populates user registry."""
        mock_api.side_effect = [
            # Users response
            [
                {"userId": "user-1", "fullName": "Alice Admin", "email": "alice@test.com", "role": "admin"},
                {"userId": "user-2", "fullName": "Bob Editor", "email": "bob@test.com", "role": "editor"},
            ],
            # User groups response
            {"items": []},
            # Workspaces response
            {"items": [], "totalItems": 0},
        ]
        
        import utils
        utils.load_registries()
        
        self.assertEqual(len(utils._user_registry), 2)
        self.assertIn("user-1", utils._user_registry)
        self.assertEqual(utils._user_registry["user-1"]["fullName"], "Alice Admin")

    @patch('utils.make_api_request')
    def test_load_registries_populates_groups(self, mock_api):
        """Test that load_registries populates group registry."""
        mock_api.side_effect = [
            [],  # Users
            {
                "items": [
                    {
                        "id": "grp-1",
                        "name": "SP_OKR_ERA_F",
                        "description": "OKR Full",
                        "archived": False,
                        "_embedded": {"userIds": ["user-1", "user-2"]},
                    }
                ]
            },
            {"items": [], "totalItems": 0},  # Workspaces
        ]
        
        import utils
        utils.load_registries()
        
        self.assertEqual(len(utils._group_registry), 1)
        self.assertIn("grp-1", utils._group_registry)
        self.assertEqual(utils._group_registry["grp-1"]["name"], "SP_OKR_ERA_F")
        self.assertEqual(len(utils._group_registry["grp-1"]["userIds"]), 2)

    @patch('utils.make_api_request')
    def test_load_registries_populates_workspaces(self, mock_api):
        """Test that load_registries populates workspace registry."""
        mock_api.side_effect = [
            [],  # Users
            {"items": []},  # Groups
            {
                "items": [
                    {"id": "ws-1", "name": "OKR Main", "namespace": "app:okr"},
                    {"id": "ws-2", "name": "Product", "namespace": "app:default"},
                ],
                "totalItems": 2,
            },
        ]
        
        import utils
        utils.load_registries()
        
        self.assertEqual(len(utils._workspace_registry), 2)
        self.assertIn("ws-1", utils._workspace_registry)
        self.assertEqual(utils._workspace_registry["ws-1"]["name"], "OKR Main")

    @patch('utils.make_api_request')
    def test_load_registries_idempotent(self, mock_api):
        """Test that calling load_registries twice doesn't make duplicate API calls."""
        mock_api.side_effect = [
            [],  # Users
            {"items": []},  # Groups
            {"items": [], "totalItems": 0},  # Workspaces
        ]
        
        import utils
        utils.load_registries()
        first_call_count = mock_api.call_count
        
        utils.load_registries()
        second_call_count = mock_api.call_count
        
        self.assertEqual(first_call_count, second_call_count)

    @patch('utils.make_api_request')
    def test_load_registries_pagination(self, mock_api):
        """Test that load_registries handles workspace pagination."""
        mock_api.side_effect = [
            [],  # Users
            {"items": []},  # Groups
            # First page of workspaces
            {
                "items": [{"id": f"ws-{i}", "name": f"Workspace {i}"} for i in range(100)],
                "totalItems": 150,
            },
            # Second page of workspaces
            {
                "items": [{"id": f"ws-{i}", "name": f"Workspace {i}"} for i in range(100, 150)],
                "totalItems": 150,
            },
        ]
        
        import utils
        utils.load_registries()
        
        self.assertEqual(len(utils._workspace_registry), 150)


class TestRegistryLookups(unittest.TestCase):
    """Test registry lookup functions."""

    def setUp(self):
        """Set up test fixtures."""
        import utils
        utils._user_registry = {
            "user-1": {"userId": "user-1", "fullName": "Alice Admin", "email": "alice@test.com", "role": "admin"},
            "user-2": {"userId": "user-2", "fullName": "Bob Editor", "email": "bob@test.com", "role": "editor"},
            "user-3": {"userId": "user-3", "email": "carol@test.com", "role": "contributor"},
        }
        utils._group_registry = {
            "grp-1": {"id": "grp-1", "name": "SP_OKR_ERA_F", "userIds": ["user-1", "user-2"]},
            "grp-2": {"id": "grp-2", "name": "SP_ProdMgt_CMS_F_U", "userIds": ["user-2"]},
        }
        utils._workspace_registry = {
            "ws-1": {"id": "ws-1", "name": "OKR Main", "namespace": "app:okr"},
            "ws-2": {"id": "ws-2", "name": "CMS Product", "namespace": "app:default"},
        }
        utils._registries_loaded = True

    def tearDown(self):
        """Clean up after each test."""
        import utils
        utils._user_registry = {}
        utils._group_registry = {}
        utils._workspace_registry = {}
        utils._registries_loaded = False

    def test_get_username_from_id_with_fullname(self):
        """Test getting username when fullName is available."""
        import utils
        username = utils.get_username_from_id("user-1")
        self.assertEqual(username, "Alice Admin")

    def test_get_username_from_id_with_email_only(self):
        """Test getting username when only email is available."""
        import utils
        username = utils.get_username_from_id("user-3")
        self.assertEqual(username, "carol@test.com")

    def test_get_username_from_id_unknown(self):
        """Test getting username for unknown user ID."""
        import utils
        username = utils.get_username_from_id("user-999")
        self.assertEqual(username, "user-999")

    def test_get_usergroup_name_known(self):
        """Test getting user group name for known group."""
        import utils
        group_name = utils.get_usergroup_name("grp-1")
        self.assertEqual(group_name, "SP_OKR_ERA_F")

    def test_get_usergroup_name_unknown(self):
        """Test getting user group name for unknown group."""
        import utils
        group_name = utils.get_usergroup_name("grp-999")
        self.assertEqual(group_name, "grp-999")

    def test_get_workspace_name_from_id_known(self):
        """Test getting workspace name for known workspace."""
        import utils
        ws_name = utils.get_workspace_name_from_id("ws-1")
        self.assertEqual(ws_name, "OKR Main")

    def test_get_workspace_name_from_id_unknown(self):
        """Test getting workspace name for unknown workspace."""
        import utils
        ws_name = utils.get_workspace_name_from_id("ws-999")
        self.assertEqual(ws_name, "ws-999")

    def test_get_workspace_id_from_name_exact_match(self):
        """Test finding workspace by exact name match."""
        import utils
        ws_id = utils.get_workspace_id_from_name("OKR Main")
        self.assertEqual(ws_id, "ws-1")

    def test_get_workspace_id_from_name_case_insensitive(self):
        """Test finding workspace by name is case-insensitive."""
        import utils
        ws_id = utils.get_workspace_id_from_name("okr main")
        self.assertEqual(ws_id, "ws-1")

    def test_get_workspace_id_from_name_not_found(self):
        """Test finding workspace returns empty string when not found."""
        import utils
        ws_id = utils.get_workspace_id_from_name("Nonexistent")
        self.assertEqual(ws_id, "")

    def test_get_user_role(self):
        """Test getting user role."""
        import utils
        self.assertEqual(utils.get_user_role("user-1"), "admin")
        self.assertEqual(utils.get_user_role("user-2"), "editor")
        self.assertEqual(utils.get_user_role("user-3"), "contributor")

    def test_get_user_role_unknown(self):
        """Test getting role for unknown user."""
        import utils
        self.assertEqual(utils.get_user_role("user-999"), "")

    def test_get_groups_by_prefix(self):
        """Test getting groups by name prefix."""
        import utils
        okr_groups = utils.get_groups_by_prefix("SP_OKR_")
        self.assertEqual(len(okr_groups), 1)
        self.assertEqual(okr_groups[0]["name"], "SP_OKR_ERA_F")

    def test_get_group_members(self):
        """Test getting group members."""
        import utils
        members = utils.get_group_members("grp-1")
        self.assertEqual(set(members), {"user-1", "user-2"})

    def test_get_group_members_unknown(self):
        """Test getting members for unknown group."""
        import utils
        members = utils.get_group_members("grp-999")
        self.assertEqual(members, [])

    def test_get_group_by_name(self):
        """Test finding group by exact name."""
        import utils
        group = utils.get_group_by_name("SP_OKR_ERA_F")
        self.assertIsNotNone(group)
        self.assertEqual(group["id"], "grp-1")

    def test_get_group_by_name_not_found(self):
        """Test finding group returns None when not found."""
        import utils
        group = utils.get_group_by_name("Nonexistent Group")
        self.assertIsNone(group)


class TestSetUserRole(unittest.TestCase):
    """Test user role setting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        import utils
        utils._user_registry = {
            "user-1": {"userId": "user-1", "fullName": "Alice", "role": "editor"},
        }
        utils._registries_loaded = True

    def tearDown(self):
        """Clean up after each test."""
        import utils
        utils._user_registry = {}
        utils._registries_loaded = False

    @patch('utils.make_api_request')
    def test_set_user_role_success(self, mock_api):
        """Test successfully setting a user role."""
        mock_api.return_value = {}
        
        import utils
        result = utils.set_user_role("user-1", "admin")
        
        self.assertTrue(result)
        self.assertEqual(utils._user_registry["user-1"]["role"], "admin")
        mock_api.assert_called_once()

    def test_set_user_role_invalid(self):
        """Test setting an invalid role."""
        import utils
        result = utils.set_user_role("user-1", "superadmin")
        self.assertFalse(result)

    @patch('utils.make_api_request')
    def test_set_user_role_api_failure(self, mock_api):
        """Test handling API failure when setting role."""
        mock_api.side_effect = Exception("API Error")
        
        import utils
        result = utils.set_user_role("user-1", "admin")
        self.assertFalse(result)


class TestColorMapping(unittest.TestCase):
    """Test workspace color mapping constant."""

    def test_color_mapping_exists(self):
        """Test that color mapping constant exists and has expected values."""
        import utils
        self.assertIn("yellow", utils.WORKSPACE_COLOR_MAPPING)
        self.assertIn("orange", utils.WORKSPACE_COLOR_MAPPING)
        self.assertIn("great", utils.WORKSPACE_COLOR_MAPPING)
        self.assertIn("blue", utils.WORKSPACE_COLOR_MAPPING)

    def test_color_mapping_values(self):
        """Test color mapping values are correct."""
        import utils
        self.assertEqual(utils.WORKSPACE_COLOR_MAPPING["yellow"], "yellow")
        self.assertEqual(utils.WORKSPACE_COLOR_MAPPING["orange"], "orange")
        self.assertEqual(utils.WORKSPACE_COLOR_MAPPING["great"], "green")
        self.assertEqual(utils.WORKSPACE_COLOR_MAPPING["blue"], "blue")


class TestGetAllWorkspaces(unittest.TestCase):
    """Test getting all workspaces from registry."""

    def setUp(self):
        """Set up test fixtures."""
        import utils
        utils._workspace_registry = {
            "ws-1": {"id": "ws-1", "name": "Workspace 1"},
            "ws-2": {"id": "ws-2", "name": "Workspace 2"},
        }
        utils._registries_loaded = True

    def tearDown(self):
        """Clean up after each test."""
        import utils
        utils._workspace_registry = {}
        utils._registries_loaded = False

    def test_get_all_workspaces(self):
        """Test getting all workspaces returns correct list."""
        import utils
        workspaces = utils.get_all_workspaces()
        self.assertEqual(len(workspaces), 2)
        workspace_ids = {ws["id"] for ws in workspaces}
        self.assertEqual(workspace_ids, {"ws-1", "ws-2"})


class TestMakeApiRequest(unittest.TestCase):
    """Test API request functionality."""

    @patch('utils.load_config')
    @patch('requests.request')
    def test_make_api_request_get_success(self, mock_request, mock_config):
        """Test successful GET API request."""
        mock_config.return_value = {
            "apikey": "test_key",
            "baseurl": "https://test.airfocus.com"
        }
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_request.return_value = mock_response
        
        import utils
        result = utils.make_api_request("/api/test")
        
        self.assertEqual(result, {"result": "success"})
        mock_request.assert_called_once()

    @patch('utils.load_config')
    @patch('requests.request')
    def test_make_api_request_post_with_data(self, mock_request, mock_config):
        """Test POST API request with data."""
        mock_config.return_value = {
            "apikey": "test_key",
            "baseurl": "https://test.airfocus.com"
        }
        mock_response = MagicMock()
        mock_response.json.return_value = {"created": True}
        mock_response.content = b'{"created": true}'
        mock_request.return_value = mock_response
        
        import utils
        result = utils.make_api_request(
            "/api/create",
            method="POST",
            data={"name": "Test"}
        )
        
        self.assertEqual(result, {"created": True})

    @patch('utils.load_config')
    @patch('requests.request')
    def test_make_api_request_ssl_verify(self, mock_request, mock_config):
        """Test that verify_ssl parameter is passed correctly."""
        mock_config.return_value = {
            "apikey": "test_key",
            "baseurl": "https://test.airfocus.com"
        }
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response
        
        import utils
        utils.make_api_request("/api/test", verify_ssl=False)
        
        call_kwargs = mock_request.call_args[1]
        self.assertFalse(call_kwargs['verify'])

    @patch('utils.load_config')
    @patch('requests.request')
    def test_make_api_request_handles_errors(self, mock_request, mock_config):
        """Test API request error handling."""
        import requests
        mock_config.return_value = {
            "apikey": "test_key",
            "baseurl": "https://test.airfocus.com"
        }
        mock_request.side_effect = requests.exceptions.RequestException("Connection error")
        
        import utils
        with self.assertRaises(Exception) as context:
            utils.make_api_request("/api/test")
        
        self.assertIn("API request failed", str(context.exception))


class TestGetCurrentUserId(unittest.TestCase):
    """Test getting current user ID."""

    @patch('utils.make_api_request')
    def test_get_current_user_id(self, mock_api):
        """Test getting current user ID from profile."""
        mock_api.return_value = {"id": "current-user-123"}
        
        import utils
        user_id = utils.get_current_user_id()
        
        self.assertEqual(user_id, "current-user-123")
        mock_api.assert_called_once_with("/api/profile", verify_ssl=True)


if __name__ == '__main__':
    unittest.main()
