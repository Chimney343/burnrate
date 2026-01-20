"""Tests for garmin.auth module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.lib.providers.garmin.auth import GarminAuthenticator, authenticate_garmin


class TestGarminAuthenticator:
    """Test suite for GarminAuthenticator class."""

    def test_init(self):
        """Test initialization stores credentials."""
        auth = GarminAuthenticator("user", "pass", "/tmp/t", None)
        assert auth.email == "user"
        assert auth.password == "pass"

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_get_client_stored_tokens(self, mock_garmin_class):
        """Test successful authentication using stored tokens."""
        mock_api = MagicMock()
        mock_garmin_class.return_value = mock_api
        mock_logger = Mock()

        auth = GarminAuthenticator(
            email="test@example.com",
            password="password",
            token_store="/tmp/tokens.json",
            logger_instance=mock_logger,
        )

        client = auth.get_client()
        assert client is mock_api
        assert auth._api is mock_api
        mock_logger.info.assert_any_call("Authenticated using stored tokens")

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_get_client_missing_creds(self, mock_garmin_class):
        """Test auth fails when missing credentials."""
        mock_api = MagicMock()
        mock_api.login.side_effect = FileNotFoundError("No tokens")
        mock_garmin_class.return_value = mock_api
        mock_logger = Mock()

        auth = GarminAuthenticator(
            email="",
            password="",
            token_store="/tmp/tokens.json",
            logger_instance=mock_logger,
        )

        client = auth.get_client()
        assert client is None
        mock_logger.error.assert_any_call("Garmin credentials not found - set GARMIN_EMAIL and GARMIN_PASSWORD")

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_get_client_login_flow(self, mock_garmin_class):
        """Test successful login flow with password."""
        mock_api = MagicMock()
        # First login call fails on tokens (FileNotFound), so the constructor for credential login is called.
        # Wait, my implementation calls Garmin() for tokens, then Garmin(email, pass) for credentials.
        # Mocking this is tricky because Garmin() is called twice with different args.
        
        # Simpler approach: Mock different return values for the class instantiation
        
        token_api = MagicMock()
        token_api.login.side_effect = FileNotFoundError 
        
        cred_api = MagicMock()
        cred_api.login.return_value = ("valid", None)

        mock_garmin_class.side_effect = [token_api, cred_api]

        mock_logger = Mock()

        auth = GarminAuthenticator(
            email="test@example.com",
            password="password",
            token_store="/tmp/tokens.json",
            logger_instance=mock_logger,
        )

        with patch("pathlib.Path.mkdir"): # prevent actual mkdir
             client = auth.get_client()

        assert client is cred_api
        cred_api.garth.dump.assert_called()

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_compat_function(self, mock_garmin_class):
        """Test that authenticate_garmin wrapper still works."""
        mock_api = MagicMock()
        mock_garmin_class.return_value = mock_api
        
        result = authenticate_garmin("u", "p", "t")
        assert result is mock_api
