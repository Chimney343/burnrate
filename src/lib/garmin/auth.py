"""Garmin authentication and token management."""

import logging
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)
from garth.exc import GarthHTTPError, GarthException

logger = logging.getLogger(__name__)


class GarminAuthenticator:
    """Handles authentication lifecycle for Garmin Connect."""

    def __init__(
        self,
        email: str,
        password: str,
        token_store: str,
        logger_instance=None,
    ):
        """Initialize authenticator.

        Args:
            email: Garmin email address
            password: Garmin password
            token_store: Path to store authentication tokens
            logger_instance: Logger instance (uses module logger if None)
        """
        self.email = email
        self.password = password
        self.token_store = Path(token_store).expanduser()
        self.logger = logger_instance or logger
        self._api: Garmin | None = None

    def get_client(self, force_refresh: bool = False) -> Garmin | None:
        """Get authenticated client, logging in if necessary.

        Args:
            force_refresh: If True, re-authenticate even if client exists

        Returns:
            Authenticated Garmin client or None if authentication fails
        """
        if self._api and not force_refresh:
            return self._api

        self._login()
        return self._api

    def _login(self) -> None:
        """Attempt token-based auth, then credential auth with MFA support."""
        self.logger.info(f"Attempting to load stored tokens from {self.token_store}")
        try:
            api = Garmin()
            api.login(str(self.token_store))
            self.logger.info("Authenticated using stored tokens")
            self._api = api
            return
        except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError, GarminConnectConnectionError):
            self.logger.info("No valid stored tokens, attempting credential login")
        except Exception as e:
            self.logger.warning(f"Failed to load stored tokens: {e}")

        if not self.email or not self.password:
            self.logger.error("Garmin credentials not found - set GARMIN_EMAIL and GARMIN_PASSWORD")
            return

        self.logger.info("Authenticating with credentials")
        try:
            api = Garmin(
                email=self.email,
                password=self.password,
                is_cn=False,
                return_on_mfa=True,
            )

            result1, result2 = api.login()

            if result1 == "needs_mfa":
                self.logger.info("MFA required")
                mfa_code = input("Enter MFA code: ").strip()
                try:
                    api.resume_login(result2, mfa_code)
                    self.logger.info("MFA authentication successful")
                except (GarthHTTPError, GarthException) as e:
                    self.logger.error(f"MFA authentication failed: {e}")
                    return

            self.token_store.parent.mkdir(parents=True, exist_ok=True)
            api.garth.dump(str(self.token_store))
            self.logger.info(f"Tokens saved to {self.token_store}")
            self.logger.info("Authenticated with Garmin")
            self._api = api

        except (
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
            GarthHTTPError,
            GarthException,
        ) as e:
            self.logger.error(f"Authentication failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected authentication error: {e}")


def authenticate_garmin(
    email: str,
    password: str,
    token_store: str,
    logger_instance=None,
) -> Garmin | None:
    """Authenticate with Garmin and return API client.

    Maintained for backward compatibility. Use GarminAuthenticator class instead.

    Args:
        email: Garmin email address
        password: Garmin password
        token_store: Path to store authentication tokens
        logger_instance: Logger instance (uses module logger if None)

    Returns:
        Authenticated Garmin API client or None if authentication fails
    """
    auth = GarminAuthenticator(email, password, token_store, logger_instance)
    return auth.get_client()
