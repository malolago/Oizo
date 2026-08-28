import importlib
import inspect
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_type_hints

import anyio
import uvicorn
from dishka import Container, Provider, Scope, from_context, make_container
from pydantic import ValidationError

# from http_router import Router, NotFoundError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from watchfiles import awatch

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
    def __init__(self):
        self.__container: Container | None = None
        self.__app_module: type[Module] | None = None
        self.__watch: set[Path] = set()
        self.__app: Starlette = Starlette(
            exception_handlers={ValidationError: validation_exception_handler}  # type: ignore[arg-type]
        )

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

        # registry = self.__app_module.get_registry()  # type: ignore

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

        # Liste des résolveurs (tu pourrais même les injecter ou les configurer dans Module)
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

        async def wrapper(request: Request, **kwargs: Any) -> Any:
            request_container = request.scope["dishka_container"]
            response = request.scope["dishka_response"]

            dependencies: dict[str, Any] = {}
            parameters = list(signature.parameters.items())

            for index, (name, parameter) in enumerate(parameters):

                # first parameter is the Request
                if index == 0 or name in kwargs:
                    continue

                annotation = hints.get(name)

                for resolver in resolvers:
                    if resolver.can_resolve(name, annotation):
                        resolved_value = await resolver.resolve(
                            request, request_container, name, annotation
                        )
                        if resolved_value is not None:
                            dependencies[name] = resolved_value
                        break  # On passe au paramètre suivant dès qu'un résolveur a fonctionné

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

            return result

        return wrapper

    def _purge_and_reload_module(self):
        """Purge tous les modules surveillés de sys.modules pour forcer la relecture disque."""
        if not self.__app_module:
            return

        root_module_name = self.__app_module.__module__
        class_name = self.__app_module.__name__

        # Canonicalisation des chemins surveillés
        watched_paths = {p.resolve() for p in self.__watch}

        # 1. Identification de TOUS les modules en cache correspondant aux fichiers surveillés
        modules_to_purge = []
        for mod_name, mod in list(sys.modules.items()):
            mod_file = getattr(mod, "__file__", None)
            if mod_file:
                try:
                    if Path(mod_file).resolve() in watched_paths:
                        modules_to_purge.append(mod_name)
                except Exception as err:  # noqa: BLE001
                    logger.error(err)

        # S'assurer que le module racine est aussi ciblé
        if root_module_name in sys.modules and root_module_name not in modules_to_purge:
            modules_to_purge.append(root_module_name)

        # 2. Suppression explicite du cache Python
        for mod_name in modules_to_purge:
            sys.modules.pop(mod_name, None)

        # 3. Ré-importation propre : Python ré-exécutera tous les fichiers .py purgés
        fresh_module = importlib.import_module(root_module_name)
        self.__app_module = getattr(fresh_module, class_name)

    async def _watch_loop(self):
        """Surveille les modifications, ferme le container, purge le cache et recrée l'app."""
        if not self.__watch:
            return

        watch_paths = [str(p) for p in self.__watch]
        logger.info(f"Watching for {len(watch_paths)} files.")

        async for changes in awatch(*watch_paths):
            logger.info("Detected change. Reloading...")

            # 1. Fermeture propre du conteneur Dishka
            if self.__container:
                try:
                    self.__container.close()
                except Exception as err:  # noqa: BLE001
                    logger.error(f"Container closing error : {err}")

            # 2. Purge du cache sys.modules et ré-importation
            try:
                self._purge_and_reload_module()
            except Exception as err:  # noqa: BLE001
                logger.error(f"Modules reloading error : {err}")
                continue

            # 3. Recompilation du conteneur et des routes
            try:
                assert self.__app_module
                self.create(self.__app_module)
                logger.info("Runtime successfully recreated. Watching for changes...")
            except Exception as err:  # noqa: BLE001
                logger.error(f"Runtime compilation error : {err}")

    async def serve(self, host: str, port: int):
        config = uvicorn.Config(
            app=self.__app,
            host=host,
            port=port,
            interface="asgi3",
            log_level="info",
        )
        server = uvicorn.Server(config)

        async with anyio.create_task_group() as tg:
            tg.start_soon(server.serve)
            tg.start_soon(self._watch_loop)

    def listen(self, host="127.0.0.1", port=8000):
        anyio.run(self.serve, host, port)


if __name__ == "__main__":
    app = App()
    app.listen()
