import inspect
from typing import get_type_hints

import uvicorn
from dishka import Provider, Scope, from_context, make_container, Container
from http_router import Router, NotFoundError

# from nanoroute import router
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from watchfiles import Change, watch
from dataclasses import dataclass
from pathlib import Path

from .modules import Module


class InternalProvider(Provider):
    request = from_context(Request, scope=Scope.REQUEST)


@dataclass
class Runtime:
    container: Container
    router: Router


class App:
    def __init__(self):
        self.__runtime: Runtime | None = None
        self.__app_module: type[Module] | None = None
        self.__watch: set[Path] = set()

    def create(self, appModule: type[Module]):
        self.__app_module = appModule

        self.__watch = {
            Path(inspect.stack()[1][1]).resolve(),
            *(Path(path).resolve() for path in self.__app_module.get_files()),
        }

        container = make_container(self.__app_module.compile(), InternalProvider())

        # self.__nanorouter = router()
        router = Router(trim_last_slash=True)

        for route in self.__app_module.get_routes():
            # self.__nanorouter.route(
            #     route.method,
            #     route.path,
            # )(self.auto_inject(route.handler))
            router.route(route.path, methods=[route.method])(
                self.auto_inject(route.handler)
            )

        self.__runtime = Runtime(
            container=container,
            router=router,
        )

    def auto_inject(self, handler):

        signature = inspect.signature(handler)
        hints = get_type_hints(handler)

        async def wrapper(request_container, **kwargs):

            dependencies = {}

            for name in signature.parameters:
                # Paramètre déjà résolu par nanoroute
                if name in kwargs:
                    continue

                annotation = hints.get(name)

                if annotation is None:
                    continue

                dependencies[name] = request_container.get(annotation)

            result = handler(
                None,
                **kwargs,
                **dependencies,
            )

            if inspect.isawaitable(result):
                result = await result

            return result

        return wrapper

    async def app(self, scope, receive, send):

        assert scope["type"] == "http"

        runtime = self.__runtime
        if runtime is None:
            raise RuntimeError("App.create() must be called before starting the server")

        request = Request(scope, receive)

        try:
            # handler, kwargs = self.__nanorouter.lookup(
            #     request.method,
            #     request.url.path,
            # )
            route = runtime.router(path=request.url.path, method=request.method)
            if route.target is None:
                raise NotFoundError
            handler, kwargs = (route.target, route.params or {})
        except NotFoundError:
            return await PlainTextResponse(
                None,
                status_code=404,
            )(scope, receive, send)

        with runtime.container(context={Request: request}) as request_container:
            result = await handler(
                request_container,
                **kwargs,
            )

        if isinstance(result, Response):
            return await result(scope, receive, send)
        return await JSONResponse(result)(scope, receive, send)

    def listen(self, host="127.0.0.1", port=8000):
        print(self.__module__)
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            interface="asgi3",
        )


if __name__ == "__main__":
    app = App()
    app.listen()
