from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware

from oizo.providers import Provider


class TestService(Provider): ...


class appMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Starlette, service: TestService) -> None:
        super().__init__(app)
        self.service = service

    async def dispatch(self, request, call_next):
        print(self.service)
        return await call_next(request)
