from starlette.middleware import _MiddlewareFactory
from starlette.middleware.base import BaseHTTPMiddleware


class InjectionMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        middleware_type: _MiddlewareFactory,
    ):
        super().__init__(app)
        self.middleware_type = middleware_type

    async def dispatch(
        self,
        request,
        call_next,
    ):

        container = request.scope["dishka_container"]

        middleware = container.get(self.middleware_type)

        return await middleware.dispatch(
            request,
            call_next,
        )
