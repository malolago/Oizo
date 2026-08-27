from .controllers import _Route


def get(path=""):
    def decorator(fn):
        fn.__route__ = _Route(
            method="GET",
            path=path,
            handler=fn,
        )
        return fn

    return decorator


def post(path=""):
    def decorator(fn):
        fn.__route__ = _Route(
            method="POST",
            path=path,
            handler=fn,
        )
        return fn

    return decorator
