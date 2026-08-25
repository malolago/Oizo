import dishka
import inspect


class Provider(dishka.Provider):
    def __init__(self):
        super().__init__()
        self.register()

    def __init_subclass__(cls, scope: dishka.BaseScope = dishka.Scope.APP) -> None:
        super().__init_subclass__()
        cls.scope = scope

    def register(self):
        methods = [
            method
            for _, method in inspect.getmembers(self, inspect.ismethod)
            if method.__func__.__qualname__.startswith(f"{self.__class__.__name__}.")
        ]
        for method in methods:
            self.provide(method, scope=self.scope)
