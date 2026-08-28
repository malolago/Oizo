import json
from typing import Protocol, Any
from dishka.exceptions import GraphMissingFactoryError
from starlette.requests import Request
from dishka import Container
import inspect
from pydantic import BaseModel

from oizo.utils.params import Params
from oizo.utils.body import Body
from oizo.utils.query import QS


class ParameterResolver(Protocol):
    def can_resolve(self, name: str, annotation: Any) -> bool:
        """Détermine si ce résolveur peut prendre en charge ce paramètre."""
        ...

    async def resolve(
        self, request: Request, container: Container, name: str, annotation: Any
    ) -> Any:
        """Construit et retourne la valeur du paramètre."""
        ...


class DishkaResolver:
    def can_resolve(self, name: str, annotation: Any) -> bool:
        # Dishka peut tenter de résoudre tout ce qui a une annotation valide
        return annotation is not None and not (
            inspect.isclass(annotation) and issubclass(annotation, BaseModel)
        )

    async def resolve(
        self, request: Request, container: Container, name: str, annotation: Any
    ) -> Any:
        try:
            return container.get(annotation)
        except GraphMissingFactoryError:
            return None  # Ou lever une exception spécifique si requis


class PydanticResolver:
    def can_resolve(self, name: str, annotation: Any) -> bool:
        return inspect.isclass(annotation) and issubclass(annotation, BaseModel)

    async def resolve(
        self, request: Request, container: Container, name: str, annotation: Any
    ) -> Any:
        request_data = {}
        matched = False
        if issubclass(annotation, Params):
            request_data.update(request.path_params)
            matched = True
        if issubclass(annotation, QS):
            request_data.update(request.query_params)
            matched = True
        if (
            issubclass(annotation, Body)
            and request.headers.get("content-type") == "application/json"
        ):
            # try:
            request_data.update(await request.json())
            matched = True
        # except json.JSONDecodeError:

        if not matched:
            request_data = {**request.path_params, **request.query_params}

            if request.headers.get("content-type") == "application/json":
                try:
                    request_data.update(await request.json())
                except json.JSONDecodeError:
                    pass

        print(request_data)
        # Laisse Pydantic lever la ValidationError naturellement
        return annotation(**request_data)
