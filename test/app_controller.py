from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from oizo.controllers import Controller
from oizo.decorators import Get


class appController(Controller):
    prefix = "/"

    @Get("/{id}/a")
    async def get(_, request: Request, response: Response):
        response.body = b"Test"

        return response

    @Get("/test/a")
    async def get2(_, response: Response):
        return PlainTextResponse("???")
