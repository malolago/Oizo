from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class BodyParserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.json = await request.json()
        return await call_next(request)
