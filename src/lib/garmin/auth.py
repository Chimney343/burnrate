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


def authenticate_garmin(
    email: str,
    password: str,
    token_store: str,
    logger_instance=None,
) -> Garmin | None:
    """Authenticate with Garmin and return API client.

    Args:
        email: Garmin email address
        password: Garmin password
        token_store: Path to store authentication tokens
        logger_instance: Logger instance (uses module logger if None)

    Returns:
        Authenticated Garmin API client or None if authentication fails
    """
    log = logger_instance or logger

    try:
        # Expand token store path
        token_store = Path(token_store).expanduser()

        # Try to load from stored tokens first
        log.info(f"Attempting to load stored tokens from {token_store}...")
        try:
            api = Garmin()
            api.login(str(token_store))
            log.info("✓ Successfully authenticated using stored tokens")
            return api
        except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
            log.info("No valid stored tokens found, attempting credential login...")

        # If no stored tokens, try with credentials
        if not email or not password:
            log.error("Garmin credentials not found in configuration")
            log.error("Please set GARMIN_EMAIL and GARMIN_PASSWORD in .env file")
            return None

        log.info("Authenticating with email and password...")
        api = Garmin(
            email=email,
            password=password,
            is_cn=False,
            return_on_mfa=True,
        )

        result1, result2 = api.login()

        # Handle MFA if required
        if result1 == "needs_mfa":
            log.info("Multi-factor authentication required")
            mfa_code = input("Please enter your MFA code: ").strip()

            try:
                api.resume_login(result2, mfa_code)
                log.info("✓ MFA authentication successful")
            except (GarthHTTPError, GarthException) as e:
                log.error(f"MFA authentication failed: {e}")
                return None

        # Save tokens for future use
        token_store.parent.mkdir(parents=True, exist_ok=True)
        api.garth.dump(str(token_store))
        log.info(f"✓ Tokens saved to {token_store}")

        log.info("✓ Successfully authenticated with Garmin")
        return api

    except (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarthHTTPError,
        GarthException,
    ) as e:
        log.error(f"Authentication failed: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected authentication error: {e}")
        return None
