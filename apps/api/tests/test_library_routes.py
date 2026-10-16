from httpx import ASGITransport, AsyncClient

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.application.tests.test_material_library import library_db as library_db
from apps.application.tests.test_material_library import material


async def test_public_library_contract_and_bounded_query_validation(library_db):
    factory, _ = library_db
    async with factory() as session, session.begin():
        await material(session)
    app = create_app()

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/intelligence/library?limit=1&subject=prompt-injection")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1 and payload["corpus_total"] == 1
        assert payload["items"][0]["subjects"]
        assert payload["next_offset"] is None and payload["as_of"]
        for query in [
            "limit=101",
            "offset=-1",
            "subject=invented",
            "category=invented",
            "as_of=2026-10-15T00:00:00",
        ]:
            assert (await client.get(f"/api/v1/intelligence/library?{query}")).status_code == 422
