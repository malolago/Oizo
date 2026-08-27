from .controllers import Route


def get(path=""):
    def decorator(fn):
        fn.__route__ = Route(
            method="GET",
            path=path,
            handler=fn,
        )
        return fn

    return decorator


def post(path=""):
    def decorator(fn):
        fn.__route__ = Route(
            method="POST",
            path=path,
            handler=fn,
        )
        return fn

    return decorator
