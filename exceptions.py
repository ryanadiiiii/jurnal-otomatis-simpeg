"""Custom exception classes for SIMPEG automation errors."""

class ConfigurationError(Exception):
    """Raised when configuration validation fails."""


class TemplateValidationError(Exception):
    """Raised when the journal template file is invalid."""


class LoginError(Exception):
    """Raised when login cannot be completed."""


class CaptchaRecognitionError(Exception):
    """Raised when captcha recognition fails and manual login is required."""


class ManualLoginTimeoutError(Exception):
    """Raised when manual captcha login does not complete in time."""


class JournalPageError(Exception):
    """Raised when the journal page cannot be opened or parsed."""


class DuplicateJournalError(Exception):
    """Raised when a duplicate journal entry is detected before submission."""


class JournalEntryError(Exception):
    """Raised when a journal entry cannot be filled correctly."""


class JournalSubmissionError(Exception):
    """Raised when journal submission cannot be verified."""
