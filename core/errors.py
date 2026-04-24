from __future__ import annotations


class BiliRewardError(RuntimeError):
    """Raised when the reward flow fails."""


class BiliCookieInvalidError(BiliRewardError):
    """Raised when the current cookie is no longer valid."""


class LoginCancelledError(BiliRewardError):
    """Raised when the user cancels the QR login flow."""


class BiliRewardCancelledError(BiliRewardError):
    """Raised when the user cancels the award claim stage."""
