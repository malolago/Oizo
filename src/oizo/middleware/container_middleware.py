from dishka import Container
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send


class ContainerMiddleware:
    def __init__(self, app: ASGIApp, container: Container):
        self.app = app
        self.container = container

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        response = Response()
        response.raw_headers.clear()

        with self.container(
            context={Request: request, Response: response}
        ) as request_container:

            scope["dishka_container"] = request_container
            scope["dishka_response"] = response

            await self.app(scope, receive, send)
