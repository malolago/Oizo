import dishka
import inspect
from .controllers import Controller, _Route, _Mount
from .providers import Provider


class Module:
    imports: tuple[type["Module"], ...]
    providers: tuple[type["Provider"], ...]
    controllers: tuple[type["Controller"], ...]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls.__file = inspect.getfile(cls)

        if missing := {"imports", "providers", "controllers"} - cls.__dict__.keys():
            raise TypeError(f"{cls.__name__} must define {missing}")

    @classmethod
    def compile(cls) -> dishka.Provider:
        provider = dishka.Provider()

        visited: set[type[Module]] = set()

        def register(module: type[Module]) -> None:
            if module in visited:
                return

            visited.add(module)

            # 1. Les modules importés d'abord
            for imported in module.imports:
                register(imported)

            # 2. Puis les providers du module
            for provider_cls in module.providers:
                provider.provide(
                    provider_cls,
                    scope=provider_cls.scope,
                )

        register(cls)

        return provider

    @classmethod
    def get_routes(cls):
        routes: list[_Mount] = []
        for controller in cls.controllers:
            routes.append(controller.get_routes())

        return routes

    @classmethod
    def get_files(cls):
        files = {
            cls.__file,
            *(inspect.getfile(obj) for obj in cls.providers),
            *(inspect.getfile(obj) for obj in cls.controllers),
        }

        for mod in cls.imports:
            files |= mod.get_files()

        return files
