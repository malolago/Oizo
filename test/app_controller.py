from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.schemas import SchemaGenerator

from oizo.controllers import Controller
from oizo.decorators import Get


class appController(Controller):
    prefix = "/"

    @Get("/{id}/a")
    async def get(
        _,
        request: Request,
        response: Response,
        app: Starlette,
    ):
        print(
            SchemaGenerator(
                {"openapi": "3.0.0", "info": {"title": "Example API", "version": "1.0"}}
            ).get_endpoints(routes=app.routes)
        )

    @Get("/test/a")
    async def get2(_, response: Response):
        return PlainTextResponse("???")
