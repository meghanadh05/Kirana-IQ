"""FastAPI dependencies: who is calling, which store, and what they may do.

Tenancy is enforced here and nowhere else. A route asks for `store` and gets a
`StoreContext` only after the caller's membership has been read from the
database — a store id in a header or path is a *claim*, never a grant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Callable

from fastapi import Depends, Header, Path

from app.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.models import store as store_model
from app.models import user as user_model
from app.security import decode_access_token

# Highest first. A role satisfies a requirement when it sits at or above it.
ROLE_RANK = {"CASHIER": 1, "MANAGER": 2, "OWNER": 3}


@dataclass(frozen=True)
class StoreContext:
    """A validated (user, store, role) triple. The unit of authorisation."""

    store_id: int
    user_id: int
    role: str
    store: dict[str, Any]
    user: dict[str, Any]

    def may(self, minimum_role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[minimum_role]


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Resolve the bearer token to a live, active user record."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Not authenticated")

    payload = decode_access_token(authorization.split(" ", 1)[1].strip())
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid authentication token") from exc

    # Re-read the user rather than trusting the token body: a deactivated
    # account must stop working before its token expires.
    user = user_model.get_by_id(user_id)
    if user is None or not user["is_active"]:
        raise AuthenticationError("Account is no longer active")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def get_store_context(
    user: CurrentUser,
    store_id: Annotated[int | None, Header(alias="X-Store-Id")] = None,
) -> StoreContext:
    """Resolve the active store from the `X-Store-Id` header.

    When the header is absent and the user belongs to exactly one store, that
    store is used — the common single-store case should not require the client
    to echo an id on every request.
    """
    if store_id is None:
        stores = store_model.list_for_user(user["id"])
        if not stores:
            raise PermissionDeniedError(
                "You do not have a store yet. Create one to continue."
            )
        if len(stores) > 1:
            raise PermissionDeniedError(
                "Multiple stores available; send the X-Store-Id header."
            )
        store_id = stores[0]["id"]

    return build_store_context(user, store_id)


def build_store_context(user: dict[str, Any], store_id: int) -> StoreContext:
    membership = store_model.get_membership(store_id, user["id"])
    if membership is None:
        # 403 rather than 404: the caller is authenticated, and whether the
        # store exists at all is not their business.
        raise PermissionDeniedError("You do not have access to this store")

    store = store_model.get(store_id)
    if store is None:
        raise NotFoundError(f"Store {store_id} not found")

    return StoreContext(
        store_id=store_id,
        user_id=user["id"],
        role=membership["role"],
        store=store,
        user=user,
    )


def get_path_store_context(
    user: CurrentUser,
    store_id: Annotated[int, Path()],
) -> StoreContext:
    """Same check, for routes that carry the store id in the path."""
    return build_store_context(user, store_id)


Store = Annotated[StoreContext, Depends(get_store_context)]
PathStore = Annotated[StoreContext, Depends(get_path_store_context)]


def require_role(minimum_role: str) -> Callable[[StoreContext], StoreContext]:
    """Dependency factory: reject callers below `minimum_role` in this store.

    Hiding a button in the UI is presentation. This is the enforcement.
    """

    def dependency(context: Store) -> StoreContext:
        if not context.may(minimum_role):
            raise PermissionDeniedError(
                f"This action requires the {minimum_role} role; "
                f"your role in this store is {context.role}."
            )
        return context

    return dependency


def require_path_role(minimum_role: str) -> Callable[[StoreContext], StoreContext]:
    """`require_role` for routes whose store id comes from the path."""

    def dependency(context: PathStore) -> StoreContext:
        if not context.may(minimum_role):
            raise PermissionDeniedError(
                f"This action requires the {minimum_role} role; "
                f"your role in this store is {context.role}."
            )
        return context

    return dependency


ManagerStore = Annotated[StoreContext, Depends(require_role("MANAGER"))]
OwnerStore = Annotated[StoreContext, Depends(require_role("OWNER"))]
PathManagerStore = Annotated[StoreContext, Depends(require_path_role("MANAGER"))]
PathOwnerStore = Annotated[StoreContext, Depends(require_path_role("OWNER"))]
