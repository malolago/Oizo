import inspect
from typing import get_type_hints

import uvicorn
import logging
from dishka import Provider, Scope, from_context, make_container, Container
from http_router import Router, NotFoundError

# from nanoroute import router
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from watchfiles import awatch
import anyio
import sys
import importlib
from dataclasses import dataclass
from pathlib import Path

from .modules import Module


class InternalProvider(Provider):
    request = from_context(Request, scope=Scope.REQUEST)


@dataclass
class Runtime:
    container: Container
    router: Router


logger = logging.getLogger("uvicorn.error")


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
                except Exception:
                    pass

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
            logger.info(f"Detected change. Reloading...")

            # 1. Fermeture propre du conteneur Dishka
            if self.__runtime and self.__runtime.container:
                try:
                    self.__runtime.container.close()
                except Exception as err:
                    logger.error(f"Container closing error : {err}")

            # 2. Purge du cache sys.modules et ré-importation
            try:
                self._purge_and_reload_module()
            except Exception as err:
                logger.error(f"Modules reloading error : {err}")
                continue

            # 3. Recompilation du conteneur et des routes
            try:
                assert self.__app_module
                self.create(self.__app_module)
                logger.info("Runtime successfully recreated. Watching for changes...")
            except Exception as err:
                logger.error(f"Runtime compilation error : {err}")

    async def serve(self, host: str, port: int):
        config = uvicorn.Config(
            app=self.app, host=host, port=port, interface="asgi3", log_level="info"
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
