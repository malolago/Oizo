# Oizo

> Modern web framework for Python. Inspired by **NestJS**

<div align="center">

[![Python 3.13+](https://img.shields.io/badge/Python-3.13+-blue.svg?style=flat&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat)](LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

---

## Key features:

- 🏗️ **Modular Architecture** - Organize your application with composable modules
- 🎯 **Decorated Routes** - Define routes with clean and elegant decorators
- 💉 **Dependency Injection in Routes** - Automatic dependency injection into route handlers, powered by **Dishka**
- 🔄 **Powerful Middleware** - Flexible middleware pipeline with dependency injection support
- ✔️ **Typed Request Data** - Strongly-typed route parameters and request bodies
- ⚡ **High Performance** - Built on **Starlette** and **Uvicorn** for optimal performance
- 🔥 **Auto Hot Reload** - Automatic code reloading in development
- 🧪 **Highly Testable** - Clean architecture makes testing straightforward

## Installation

**Requirements:** Python 3.13 or higher

```bash
uv add oizo
```

## Quick Start

### Create a Service

```python
from oizo.injectable import Injectable
from dishka import Scope

class UserService(Injectable, scope = Scope.SINGLETON):    
    def get_users(self):
        return [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]
    
    def get_user(self, id: int):
        return {"id": id, "name": "User"}
```

### Create a Controller

Route handlers receive dependencies as parameters. The first parameter is ignored (due to pyright not handling programmatic `staticmethod`), and other parameters are automatically resolved:

```python
from oizo.controllers import Controller
from oizo.decorators import Get

class UserController(Controller):
    prefix = "/users"
    
    @Get("/")
    async def list_users(_, service: UserService):
        return service.get_users()
    
```

If you don't want to define DTOs, Starlette's `Request`, `Response` and `Starlette` are also automatically injected into each route handler, and each json-formed bodies are serialized:

```python
from oizo.controllers import Controller
from oizo.decorators import Get, Post

from starlette.requests import Request

class UserController(Controller):
    prefix = "/users"
    
    @Get("/")
    async def list_users(_, request: Request):
        body = request.state.json
        return request.path_params
```

### Create a Module

```python
from oizo.modules import Module

class UserModule(Module):
    imports = ()
    providers = (UserService,)
    controllers = (UserController,)
```

### Run the Application

```python
from oizo.runtime import App

if __name__ == "__main__":
    app = App()
    app.create(UserModule)
    app.listen()
```

Application starts on `http://localhost:8000`

## Architecture

### Modules

Modules are the building blocks of your application. Each module can import other modules and encapsulates its own controllers and services:

```python
class FeatureModule(Module):
    imports = (DependentModule,)      # Imported modules
    providers = (ServiceA, ServiceB)  # Services/Injectables
    controllers = (ControllerA,)      # Controllers
    
    @staticmethod
    def configure(consumer):
        # Optional: configure middleware for this module
        pass
```

### Controllers

Controllers define routes and handle HTTP requests. Route handlers have automatic dependency injection:

```python
from oizo.controllers import Controller
from oizo.decorators import Get, Post

class ResourceController(Controller):
    prefix = "/resources"
    
    @Get("/")
    async def list(_, service: MyService):
        return service.list()
    
```

### Dependency Injection

Dependencies are **injected directly into route handler parameters**. The framework automatically resolves dependencies based on type hints:

```python
class UserController(Controller):
```

### Middleware

Create custom middleware with dependency injection support:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from oizo.injectable import Injectable

class AuthService(Injectable):
    pass

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_service: AuthService):
        super().__init__(app)
        self.auth_service = auth_service
    
    async def dispatch(self, request, call_next):
        # Your middleware logic
        response = await call_next(request)
        return response

class AppModule(Module):
    imports = ()
    providers = (AuthService,)
    controllers = (UserController,)
    
    @staticmethod
    def configure(consumer):
        consumer.apply(AuthMiddleware).forRoutes("/api/admin/*")
```

> It is also possible to use them globally, by using `app.use(...)` in your `main.py` file. 

## Advanced Usage

### Dependency Scopes

Control how dependencies are instantiated:

```python
from dishka import Scope
from oizo.injectable import Injectable

class SessionService(Injectable, scope = Scope.SINGLETON):      
    # Single instance across the app
    
class RequestService(Injectable, scope = Scope.REQUEST):
    # One instance per HTTP request

class TransientService(Injectable, scope = Scope.TRANSIENT):
    # New instance for each injection
```

### Request Context

Access the current request when needed:

```python
from starlette.requests import Request
from starlette.responses import Response
from starlette.applications import Starlette

class ContextController(Controller):
    prefix = "/context"
    
    @Get("/headers")
    async def get_headers(_, request: Request):
        return dict(request.headers)
    
    @Get("/set-cookie")
    async def set_cookie(_, response: Response):
        response.set_cookie("session", "abc123")
        return {"status": "cookie set"}

    @Get("/create_route")
    async def get_routes(_, app: Starlette):
        app.add_route("/route", handler, ["GET"])

```

### Composing Modules

Build complex applications by composing multiple modules:

```python
class UserModule(Module):
    imports = ()
    providers = (UserService,)
    controllers = (UserController,)

class PostModule(Module):
    imports = (UserModule,)  # Inherit UserService
    providers = (PostService,)
    controllers = (PostController,)

class AppModule(Module):
    imports = (PostModule,)  # Imports both UserModule and PostModule
    providers = ()
    controllers = ()
```

## Project Structure

```
src/oizo/
├── __init__.py
├── controllers.py              # Base Controller class
├── decorators.py               # HTTP decorators (@Get, @Post, etc.)
├── injectable.py               # Base Injectable class for services
├── modules.py                  # Module system
├── resolver.py                 # Dependency resolution (request data, Dishka)
├── runtime.py                  # Application runtime & auto-injection
├── middleware/
│   ├── bodyparser_middleware.py    # Parse JSON request body
│   ├── consumer.py                 # Middleware registration API
│   ├── container_middleware.py     # Attach DI container to requests
│   └── injection_middleware.py     # Inject middleware dependencies
```

## Testing

The modular architecture and dependency injection make testing straightforward:

```python
from unittest.mock import Mock

class MockUserService:
    def get_users(self):
        return [{"id": 1, "name": "Test User"}]

async def test_list_users():
    mock_service = MockUserService()
    controller = UserController()
    
    result = await controller.list_users(mock_service)
    
    assert len(result) == 1
    assert result[0]["name"] == "Test User"
```

## Performance

Oizo is built on proven, high-performance libraries:

- **Starlette** - Lightning-fast ASGI framework
- **Uvicorn** - Ultra-fast ASGI server
- **Dishka** - Modern, efficient dependency injection
- **Typed DTOs** - Simple request data containers

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Inspiration

Oizo combines the best practices from popular web frameworks:

- **NestJS** - Modular architecture and dependency injection
- **Starlette** - Performance and middleware flexibility

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

Need help?

- 📖 [Read the documentation](#)
- 🐛 [Report a bug](https://github.com/yourusername/oizo/issues)
- 💡 [Request a feature](https://github.com/yourusername/oizo/discussions)

