from providers import Provider
from controllers import Controller, Route


class Module:
    imports: tuple[type["Module"], ...]
    providers: tuple[type["Provider"], ...]
    controllers: tuple[type["Controller"], ...]
    exports: tuple[type[Provider], ...]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if (
            missing := {"imports", "providers", "controllers", "exports"}
            - cls.__dict__.keys()
        ):
            raise TypeError(f"{cls.__name__} must define {missing}")

    def get_providers(self):
        providers: list["Provider"] = []

        for module_cls in self.imports:
            module = module_cls()
            providers.extend(module.get_providers())

        providers.extend(provider() for provider in self.providers)

        return providers

    def get_routes(self):
        routes: list["Route"] = []
        for controller in self.controllers:
            routes.extend(controller.get_routes())

        return routes
