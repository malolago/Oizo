from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.schemas import SchemaGenerator

from oizo.controllers import Controller
from oizo.decorators import Get
from oizo.utils.params import Params


class DTO(Params):
    id: str
    # q: int


class appController(Controller):
    prefix = "/"

    @Get("/{id}/a")
    async def get(_, request: Request, response: Response, params: DTO, app: Starlette):
        print(
            SchemaGenerator(
                {"openapi": "3.0.0", "info": {"title": "Example API", "version": "1.0"}}
            ).get_endpoints(routes=app.routes)
        )

        return

    @Get("/test/a")
    async def get2(_, response: Response):
        return PlainTextResponse("???")
