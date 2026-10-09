"""Application roles and source policies, independent of a future AD login."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class Role(StrEnum):
    INTERN = "intern"


@dataclass(frozen=True)
class User:
    id: str
    display_name: str
    roles: frozenset[Role] = frozenset()


# Empty requirements mean accessible to everyone. Unconfigured sources stay hidden.
# All listed roles are required; add each new source explicitly here.
SOURCE_ROLES = MappingProxyType(
    {
        "wikipedia": frozenset[Role](),
        "openlibrary": frozenset[Role](),
        "nrwbank": frozenset({Role.INTERN}),
    }
)


def can_access_source(user: User, source_id: str) -> bool:
    required = SOURCE_ROLES.get(source_id)
    return required is not None and required <= user.roles


def current_user() -> User:
    """Trusted local identity. Replace with authenticated identity and AD role mapping.

    Roles never come from browser fields or unverified request headers.
    This local POC intentionally has no login or user switching.
    """
    return User(id="local", display_name="Lokaler Nutzer", roles=frozenset(Role))
