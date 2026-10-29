"""Typed error hierarchy. Errors are structured and never swallowed silently."""


class VerityError(Exception):
    """Base class for all VERITY errors; carries a machine-readable code."""

    default_code = "verity_error"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code


class InputError(VerityError):
    """The caller supplied invalid input (empty, too long, unsupported language)."""

    default_code = "input_error"


class ExternalServiceError(VerityError):
    """An external HTTP service failed or returned an unusable response."""

    default_code = "external_service_error"


class DataError(VerityError):
    """A storage or data-file problem."""

    default_code = "data_error"


class ModelError(VerityError):
    """A model (belief network, classifier, index) is missing or inconsistent."""

    default_code = "model_error"
