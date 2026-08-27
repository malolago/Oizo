from oizo.controllers import Controller
from oizo.decorators import get
from starlette.requests import Request


class appController(Controller):
    prefix = "/"

    @get("test")
    async def get(_, request: Request):
        return request.url.path
