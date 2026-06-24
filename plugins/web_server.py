"""
plugins/web_server.py

Minimal aiohttp web server — required for platforms like Heroku / Railway
that need an HTTP listener to consider the process healthy.
"""

from aiohttp import web


routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "file-sharing-bot"})


@routes.get("/health")
async def health_check(request: web.Request) -> web.Response:
    return web.json_response({"status": "healthy"})


async def web_server() -> web.Application:
    app = web.Application(client_max_size=30_000_000)
    app.add_routes(routes)
    return app
