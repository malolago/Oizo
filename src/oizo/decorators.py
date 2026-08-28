from .controllers import _Route


def Get(path="/"):
    def decorator(fn):
        fn.__route__ = _Route(
            method="GET",
            path=path,
            handler=fn,
        )
        return fn

    return decorator


def Post(path="/"):
    def decorator(fn):
        fn.__route__ = _Route(
            method="POST",
            path=path,
            handler=fn,
        )
        return fn

    return decorator
