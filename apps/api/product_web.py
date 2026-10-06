from __future__ import annotations

from pathlib import PurePosixPath

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope


class ProductStaticFiles(StaticFiles):
    """Serve the built Product SPA without turning missing assets into HTML."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or not _is_client_route(path):
                raise
        else:
            if response.status_code != 404 or not _is_client_route(path):
                return response
        return await super().get_response("index.html", scope)


def _is_client_route(path: str) -> bool:
    name = PurePosixPath(path).name
    return not PurePosixPath(name).suffix
