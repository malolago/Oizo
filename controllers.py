import inspect
from typing import Callable
from dataclasses import dataclass

CONTROLLER_META = "__controller__"
ROUTE_META = "__route__"


@dataclass
class Route:
    method: str
    path: str
    handler: Callable


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
        routes = []

        for _, method in inspect.getmembers(cls, inspect.isfunction):
            route = getattr(method, "__route__", None)

            if route:
                routes.append(
                    Route(
                        method=route.method,
                        path=cls.prefix + route.path,
                        handler=method,
                    )
                )

        return routes
