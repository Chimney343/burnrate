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

        with patch("pathlib.Path.mkdir"):
             client = auth.get_client()

        assert client is cred_api
        cred_api.garth.dump.assert_called()

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_get_client_returns_cached_api(self, mock_garmin_class):
        """Test that repeated calls return cached API client."""
        mock_api = MagicMock()
        mock_garmin_class.return_value = mock_api

        auth = GarminAuthenticator(
            email="test@example.com",
            password="password",
            token_store="/tmp/tokens.json",
        )

        client1 = auth.get_client()
        client2 = auth.get_client()

        assert client1 is client2
        assert mock_garmin_class.call_count == 1

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_get_client_force_refresh(self, mock_garmin_class):
        """Test force_refresh re-authenticates."""
        mock_api1 = MagicMock()
        mock_api2 = MagicMock()
        mock_garmin_class.side_effect = [mock_api1, mock_api2]

        auth = GarminAuthenticator(
            email="test@example.com",
            password="password",
            token_store="/tmp/tokens.json",
        )

        client1 = auth.get_client()
        client2 = auth.get_client(force_refresh=True)

        assert client1 is mock_api1
        assert client2 is mock_api2

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_get_client_with_mfa_success(self, mock_garmin_class):
        """Test successful MFA authentication."""
        token_api = MagicMock()
        token_api.login.side_effect = FileNotFoundError("No tokens")
        
        cred_api = MagicMock()
        cred_api.login.return_value = ("needs_mfa", "mfa_token")

        mock_garmin_class.side_effect = [token_api, cred_api]
        mock_logger = Mock()

        auth = GarminAuthenticator(
            email="test@example.com",
            password="password123",
            token_store="/tmp/tokens.json",
            logger_instance=mock_logger,
        )

        with patch("builtins.input", return_value="123456"), patch("pathlib.Path.mkdir"):
            client = auth.get_client()

        cred_api.resume_login.assert_called_with("mfa_token", "123456")

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_get_client_general_exception(self, mock_garmin_class):
        """Test authentication handles general exceptions."""
        mock_garmin_class.side_effect = Exception("Network error")
        mock_logger = Mock()

        auth = GarminAuthenticator(
            email="test@example.com",
            password="password",
            token_store="/tmp/tokens.json",
            logger_instance=mock_logger,
        )

        client = auth.get_client()
        assert client is None


class TestAuthenticateGarminCompat:
    """Test authenticate_garmin backward compatibility function."""

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_compat_function_success(self, mock_garmin_class):
        """Test that authenticate_garmin wrapper still works."""
        mock_api = MagicMock()
        mock_garmin_class.return_value = mock_api
        
        result = authenticate_garmin("u", "p", "t")
        assert result is mock_api

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_compat_function_with_stored_tokens(self, mock_garmin_class):
        """Test authenticate_garmin with stored tokens."""
        mock_api = MagicMock()
        mock_garmin_class.return_value = mock_api
        mock_logger = Mock()

        result = authenticate_garmin(
            email="test@example.com",
            password="password",
            token_store="/tmp/tokens.json",
            logger_instance=mock_logger,
        )

        assert result is mock_api
        mock_logger.info.assert_any_call("Authenticated using stored tokens")

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_compat_function_missing_credentials(self, mock_garmin_class):
        """Test authenticate_garmin fails when credentials are missing."""
        mock_logger = Mock()
        mock_api = MagicMock()
        mock_garmin_class.return_value = mock_api
        mock_api.login.side_effect = FileNotFoundError("No tokens")

        result = authenticate_garmin(
            email="",
            password="",
            token_store="/tmp/tokens.json",
            logger_instance=mock_logger,
        )

        assert result is None
        mock_logger.error.assert_any_call(
            "Garmin credentials not found - set GARMIN_EMAIL and GARMIN_PASSWORD"
        )
