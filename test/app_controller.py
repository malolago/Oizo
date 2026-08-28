from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from oizo.controllers import Controller
from oizo.decorators import Get, Post
from oizo.utils.params import Params
from oizo.utils.query import QS


class DTO(Params, QS):
    id: str
    q: int


class appController(Controller):
    prefix = "/"

    @Post("/{id}/a")
    async def get(_, request: Request, response: Response, params: DTO):
        print(params)

        return response

    @Get("/test/a")
    async def get2(_, response: Response):
        return PlainTextResponse("???")
