"""Tests for garmin.auth module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.lib.providers.garmin.auth import authenticate_garmin


class TestAuthenticateGarmin:
    """Test suite for authenticate_garmin function."""

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_authenticate_with_stored_tokens_success(self, mock_garmin_class):
        """Test successful authentication using stored tokens."""
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
        assert mock_logger.info.call_count >= 1
        mock_logger.info.assert_any_call(
            "Authenticated using stored tokens"
        )

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_authenticate_missing_credentials(self, mock_garmin_class):
        """Test authentication fails when credentials are missing."""
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

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_authenticate_credential_login_success(self, mock_garmin_class):
        """Test successful credential-based login."""
        mock_api = MagicMock()
        mock_api.login.return_value = ("success", None)
        mock_garmin_class.return_value = mock_api
        mock_logger = Mock()

        with patch("pathlib.Path.exists", return_value=False):
            result = authenticate_garmin(
                email="test@example.com",
                password="password123",
                token_store="/tmp/tokens.json",
                logger_instance=mock_logger,
            )

        mock_garmin_class.assert_called()

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_authenticate_with_mfa_success(self, mock_garmin_class):
        """Test successful MFA authentication."""
        mock_api = MagicMock()
        mock_api.login.side_effect = [FileNotFoundError("No tokens"), ("needs_mfa", "mfa_token")]
        mock_garmin_class.return_value = mock_api
        mock_logger = Mock()

        with patch("builtins.input", return_value="123456"):
            result = authenticate_garmin(
                email="test@example.com",
                password="password123",
                token_store="/tmp/tokens.json",
                logger_instance=mock_logger,
            )

        mock_api.resume_login.assert_called_with("mfa_token", "123456")

    @patch("src.lib.providers.garmin.auth.Garmin")
    def test_authenticate_general_exception(self, mock_garmin_class):
        """Test authentication handles general exceptions."""
        mock_garmin_class.side_effect = Exception("Network error")
        mock_logger = Mock()

        result = authenticate_garmin(
            email="test@example.com",
            password="password",
            token_store="/tmp/tokens.json",
            logger_instance=mock_logger,
        )

        assert result is None
        mock_logger.error.assert_called()
