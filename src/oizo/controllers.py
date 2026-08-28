import inspect
from collections.abc import Callable
from dataclasses import dataclass

CONTROLLER_META = "__controller__"
ROUTE_META = "__route__"


@dataclass
class _Route:
    method: str
    path: str
    handler: Callable


@dataclass
class _Mount:
    prefix: str
    routes: list[_Route]


class Controller:
    prefix: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if "prefix" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must define 'prefix'")

    # def __init_subclass__(cls, prefix: str) -> None:
    #     cls.prefix = prefix

    @classmethod
    def get_routes(cls):
        routes: list[_Route] = []

        for _, method in sorted(
            inspect.getmembers(cls, inspect.isfunction),
            key=lambda x: inspect.getsourcelines(x[1])[1],
            reverse=True,
        ):
            route = getattr(method, ROUTE_META, None)

            if route:
                routes.append(
                    _Route(
                        method=route.method,
                        path=route.path,
                        handler=method,
                    )
                )

        return _Mount(cls.prefix, routes)
