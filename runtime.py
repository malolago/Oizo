from dishka import make_container
from typing import Type
from modules import Module


def create(appModule: Type[Module]):
    module = appModule()
    routes = module.get_routes()
    container = make_container(*module.get_providers())


from starlette.responses import PlainTextResponse


async def app(scope, receive, send):
    assert scope["type"] == "http"
    response = PlainTextResponse("Hello, world!")
    await response(scope, receive, send)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
