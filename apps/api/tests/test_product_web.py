from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.product_web import ProductStaticFiles


@pytest.mark.asyncio
async def test_product_spa_falls_back_for_client_routes_but_not_missing_assets(
    tmp_path,
) -> None:
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>SecFusion Product Fixture</title>",
        encoding="utf-8",
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")

    app = FastAPI()
    app.mount(
        "/product",
        ProductStaticFiles(directory=tmp_path, html=True),
        name="product-web",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        deep_link = await client.get("/product/intelligence?cve=CVE-2026-42424")
        asset = await client.get("/product/assets/app.js")
        missing_asset = await client.get("/product/assets/missing.js")

    assert deep_link.status_code == 200
    assert "SecFusion Product Fixture" in deep_link.text
    assert asset.status_code == 200
    assert "console.log" in asset.text
    assert missing_asset.status_code == 404
