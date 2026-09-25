from typing import Any, Protocol

from dishka import Container
from dishka.exceptions import GraphMissingFactoryError
from starlette.requests import Request


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
        return annotation is not None

    async def resolve(
        self, request: Request, container: Container, name: str, annotation: Any
    ) -> Any:
        try:
            return container.get(annotation)
        except GraphMissingFactoryError:
            return None  # Ou lever une exception spécifique si requis
