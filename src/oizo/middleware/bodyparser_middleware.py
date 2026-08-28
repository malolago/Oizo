from starlette.middleware.base import BaseHTTPMiddleware


class BodyParserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.headers.get("content-type") == "application/json":
            request.state.json = await request.json()
        return await call_next(request)
