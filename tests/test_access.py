import httpx
import pytest

from pydanticai_poc.access import Role, User, can_access_source, current_user
from pydanticai_poc.app import create_app
from pydanticai_poc.research import ResearchService
from pydanticai_poc.sources import fixture_sources


def test_local_user_has_all_application_roles():
    user = current_user()
    assert user.roles == frozenset(Role)
    assert can_access_source(user, "nrwbank")


@pytest.mark.parametrize("roles", [frozenset(), frozenset({Role.INTERN})])
def test_source_rules_and_unconfigured_sources(roles):
    user = User("test", "Test", roles)
    assert can_access_source(user, "wikipedia")
    assert can_access_source(user, "openlibrary")
    assert can_access_source(user, "nrwbank") == (Role.INTERN in roles)
    assert not can_access_source(user, "unconfigured")


@pytest.mark.parametrize("internal", [False, True])
async def test_real_role_policy_filters_catalog_and_rejects_forged_roles(
    service: ResearchService, internal: bool
):
    # The role check does not need a live model or a network source.
    service.sources["nrwbank"] = fixture_sources()["wikipedia"]
    service.sources["unconfigured"] = fixture_sources()["wikipedia"]
    app = create_app(service.settings, service)
    user = User("test", "Testnutzer", frozenset({Role.INTERN}) if internal else frozenset())
    app.dependency_overrides[current_user] = lambda: user
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            me = (await client.get("/api/me")).json()
            assert me["roles"] == (["intern"] if internal else [])
            ids = [row["id"] for row in (await client.get("/api/sources")).json()]
            assert "wikipedia" in ids
            assert "openlibrary" in ids
            assert ("nrwbank" in ids) == internal
            assert "unconfigured" not in ids
            session = (await client.post("/api/conversations")).json()["conversation_id"]
            payload = {
                "conversation_id": session,
                "message": "Wer war Kafka?",
                "source_ids": ["nrwbank"],
                "roles": ["intern"],
                "user_id": "local",
            }
            response = await client.post(
                "/api/chat", json=payload, headers={"X-Roles": "intern", "X-User": "local"}
            )
            assert response.status_code == (200 if internal else 403)
            assert service.active_run is None
            if not internal:
                assert not service.conversations[session].turns
            # Omitting selection still scopes the run to authorized sources only.
            response = await client.post(
                "/api/chat", json={"conversation_id": session, "message": "Kafka"}
            )
            assert response.status_code == 200
            assert service.conversations[session].source_ids == tuple(sorted(ids))
