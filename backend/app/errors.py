"""Domain exceptions and their HTTP mapping.

Services raise these instead of `HTTPException`, so business rules stay
independent of FastAPI and every route gets the same status codes for the same
kind of failure. `app.main` registers the handlers.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for errors that map onto a specific HTTP status."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class AuthenticationError(DomainError):
    """Missing, expired or invalid credentials."""

    status_code = 401


class PermissionDeniedError(DomainError):
    """Authenticated, but not allowed to touch this store or perform this action."""

    status_code = 403


class NotFoundError(DomainError):
    """The requested entity does not exist inside the caller's store."""

    status_code = 404


class ConflictError(DomainError):
    """Duplicate key, or a state transition the entity does not allow."""

    status_code = 409


class ValidationError(DomainError):
    """The request is well formed but violates a business rule."""

    status_code = 422


class ModelUnavailableError(DomainError):
    """Forecasting was asked for before a model exists for this store."""

    status_code = 503
