# import anyio
import asyncio
import importlib
import inspect
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_type_hints

import uvicorn
from dishka import Container, Provider, Scope, from_context, make_container
from pydantic import ValidationError

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import Lifespan

from oizo.middleware.bodyparser_middleware import BodyParserMiddleware
from oizo.middleware.consumer import MiddlewareConsumer
from oizo.middleware.container_middleware import ContainerMiddleware
from oizo.middleware.injection_middleware import InjectionMiddleware
from oizo.resolver import DishkaResolver, ParameterResolver, PydanticResolver

from .modules import Module


class InternalProvider(Provider):
    request = from_context(Request, scope=Scope.REQUEST)
    response = from_context(Response, scope=Scope.REQUEST)
    app = from_context(Starlette, scope=Scope.APP)


logger = logging.getLogger("uvicorn.error")


async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


class App:
    def __init__(self, lifespan: Lifespan | None = None):
        self.__container: Container | None = None
        self.__app_module: type[Module] | None = None
        self.__watch: set[Path] = set()
        self.__shutdown_event = asyncio.Event()
        self.__app: Starlette = Starlette(
            lifespan=lifespan,
            exception_handlers={ValidationError: validation_exception_handler},  # type: ignore[arg-type]
        )
        self.__middlewares = []

    def use(self, *middlewares):
        for mw in middlewares:
            self.__watch.add(Path(inspect.getfile(mw)).resolve())
            self.__middlewares.append(mw)

    def create(self, appModule: type[Module]):
        self.__app_module = appModule

        consumer = MiddlewareConsumer()
        self.__app_module.configure(consumer)

        middlewares_provider = Provider(Scope.APP)
        middlewares_provider.provide_all(*consumer.all_middlewares)

        self.__watch = {
            Path(inspect.stack()[1][1]).resolve(),
            *(Path(path).resolve() for path in self.__app_module.get_files()),
            *(
                Path(inspect.getfile(path)).resolve()
                for path in consumer.all_middlewares
            ),
        }

        self.__container = make_container(
            self.__app_module.compile(),
            InternalProvider(),
            middlewares_provider,
            context={Starlette: self.__app},
        )

        self.__app.router.routes.clear()
        self.__app.user_middleware.clear()
        self.__app.middleware_stack = None

        self.__app.add_middleware(
            ContainerMiddleware,
            container=self.__container,
        )
        self.__app.add_middleware(BodyParserMiddleware)
        [self.__app.add_middleware(mw) for mw in dict.fromkeys(self.__middlewares)]

        for mount in self.__app_module.get_routes():
            routes = []

            for route in mount.routes:
                route_middlewares = consumer.get_middlewares(
                    route.path,
                    route.method,
                )

                middlewares = [
                    Middleware(
                        InjectionMiddleware,
                        middleware_type=middleware_type,
                    )
                    for middleware_type in route_middlewares
                ]

                routes.append(
                    Route(
                        path=route.path,
                        endpoint=self.auto_inject(route.handler),
                        methods=[route.method],
                        middleware=middlewares,
                    )
                )

            self.__app.router.routes.append(
                Mount(
                    path=mount.prefix,
                    routes=routes,
                )
            )

    def auto_inject(
        self,
        handler: Callable[..., Any],
    ) -> Callable[..., Any]:

        signature = inspect.signature(handler)

        resolvers: list[ParameterResolver] = [
            PydanticResolver(),
            DishkaResolver(),
        ]

        try:
            hints = get_type_hints(handler)
        except Exception:  # noqa: BLE001
            hints = {
                name: parameter.annotation
                for name, parameter in signature.parameters.items()
                if parameter.annotation is not inspect.Parameter.empty
            }

        async def wrapper(request: Request, **kwargs: Any) -> Response:
            request_container = request.scope["dishka_container"]
            response = request.scope["dishka_response"]

            dependencies: dict[str, Any] = {}
            parameters = list(signature.parameters.items())

            for index, (name, parameter) in enumerate(parameters):
                if index == 0 or name in kwargs:
                    continue

                annotation = hints.get(name)

                for resolver in resolvers:
                    if resolver.can_resolve(name, annotation):
                        resolved_value = await resolver.resolve(
                            request,
                            request_container,
                            name,
                            annotation,
                        )

                        if resolved_value is not None:
                            dependencies[name] = resolved_value

                        break

            result = handler(
                None,
                **kwargs,
                **dependencies,
            )

            if inspect.isawaitable(result):
                result = await result

            if result is None:
                result = response

            elif isinstance(result, Response):
                if response.status_code != 200:
                    result.status_code = response.status_code

                if response.background is not None:
                    result.background = response.background

                result_header_names = {name.lower() for name, _ in result.raw_headers}

                result.raw_headers.extend(
                    header
                    for header in response.raw_headers
                    if (
                        header[0].lower() == b"set-cookie"
                        or header[0].lower() not in result_header_names
                    )
                )

            else:
                result = JSONResponse(
                    content=result,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    background=response.background,
                )

            return result

        return wrapper

    def _purge_and_reload_module(self):
        if not self.__app_module:
            return

        root_module_name = self.__app_module.__module__
        class_name = self.__app_module.__name__

        watched_paths = {p.resolve() for p in self.__watch}

        modules_to_purge = []
        for mod_name, mod in list(sys.modules.items()):
            mod_file = getattr(mod, "__file__", None)
            if mod_file:
                try:
                    if Path(mod_file).resolve() in watched_paths:
                        modules_to_purge.append(mod_name)
                except Exception as err:  # noqa: BLE001
                    logger.error(err)

        if root_module_name in sys.modules and root_module_name not in modules_to_purge:
            modules_to_purge.append(root_module_name)

        for mod_name in modules_to_purge:
            sys.modules.pop(mod_name, None)

        fresh_module = importlib.import_module(root_module_name)
        self.__app_module = getattr(fresh_module, class_name)

    async def _watch_loop(self):
        if not self.__watch:
            return

        from watchfiles import awatch

        watch_paths = [str(p) for p in self.__watch]
        logger.info(f"Watching for {len(watch_paths)} files.")

        async for changes in awatch(*watch_paths):
            logger.info("Detected change. Reloading...")

            if self.__container:
                try:
                    self.__container.close()
                except Exception as err:  # noqa: BLE001
                    logger.error(f"Container closing error : {err}")

            try:
                self._purge_and_reload_module()
            except Exception as err:  # noqa: BLE001
                logger.error(f"Modules reloading error : {err}")
                continue

            try:
                assert self.__app_module
                self.create(self.__app_module)
                logger.info("Runtime successfully recreated. Watching for changes...")
            except Exception as err:  # noqa: BLE001
                logger.error(f"Runtime compilation error : {err}")

    async def serve(self, debug: bool, host: str, port: int):
        config = uvicorn.Config(
            app=self.__app,
            host=host,
            port=port,
            interface="asgi3",
            log_level="info",
        )

        server = uvicorn.Server(config)

        if not debug:
            await server.serve()
            return

        watcher_task = asyncio.create_task(
            self._watch_loop(),
            name="oizo-file-watcher",
        )

        try:
            await server.serve()

        finally:
            logger.info("Stopping Oizo...")

            self.__shutdown_event.set()
            watcher_task.cancel()

            try:
                await watcher_task
            except asyncio.CancelledError:
                pass

            if self.__container:
                try:
                    self.__container.close()
                except Exception as err:  # noqa: BLE001
                    logger.error(f"Container closing error: {err}")

            logger.info("Oizo stopped.")

    def listen(self, debug=True, host="127.0.0.1", port=8000):
        try:
            asyncio.run(self.serve(debug, host, port))
        except KeyboardInterrupt:
            logger.info("Oizo stopped.")


if __name__ == "__main__":
    app = App()
    app.listen()
