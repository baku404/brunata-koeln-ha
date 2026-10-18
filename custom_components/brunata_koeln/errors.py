"""Controlled errors that never contain portal payloads or credentials."""


class BrunataError(Exception):
    """Base class for safe client errors."""


class AuthenticationError(BrunataError):
    """Credentials or session were rejected."""


class CaptchaRequired(AuthenticationError):
    """Interactive authentication is required."""


class ConnectionError(BrunataError):
    """The portal is temporarily unreachable."""


class PortalFormatError(BrunataError):
    """The portal response does not match the verified contract."""


class NoSupportedData(BrunataError):
    """No supported consumption data are available."""
