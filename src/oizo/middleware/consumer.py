import fnmatch


class RouteBinder:
    def __init__(self, consumer: "MiddlewareConsumer", middlewares: tuple[type, ...]):
        self._consumer = consumer
        self._middlewares = middlewares

    def forRoutes(self, *patterns: str) -> "MiddlewareConsumer":
        for pattern in patterns:
            normalized_pattern = self._consumer._normalize_path(pattern)

            for middleware in self._middlewares:
                # 1. Enregistrement de la règle de matching
                self._consumer._rules.append((middleware, normalized_pattern))

                # 2. Mise à jour du registre pour Dishka
                if normalized_pattern not in self._consumer.registry:
                    self._consumer.registry[normalized_pattern] = []
                if middleware not in self._consumer.registry[normalized_pattern]:
                    self._consumer.registry[normalized_pattern].append(middleware)

        return self._consumer


class MiddlewareConsumer:
    def __init__(self):
        # Registre associant chaque pattern à ses middlewares : dict[str, list[Type]]
        self.registry: dict[str, list[type]] = {}
        # Liste interne de tuples (middleware, pattern_normalise) pour le matching
        self._rules: list[tuple[type, str]] = []

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Garantit un slash initial et nettoie les espaces."""
        path = path.strip()
        if not path.startswith("/"):
            path = "/" + path
        return path

    def apply(self, *middleware_types: type) -> RouteBinder:
        """Accepte un ou plusieurs middlewares à appliquer."""
        return RouteBinder(self, middleware_types)

    def get_middlewares(self, route_path: str, method: str | None = None) -> list[type]:
        """Retourne la liste des middlewares correspondant à la route donnée."""
        normalized_path = self._normalize_path(route_path)
        matched_middlewares: list[type] = []

        for middleware, pattern in self._rules:
            if (
                fnmatch.fnmatch(normalized_path, pattern)
                and middleware not in matched_middlewares
            ):
                matched_middlewares.append(middleware)

        return matched_middlewares

    @property
    def all_middlewares(self) -> set[type]:
        """Retourne l'ensemble de tous les types de middlewares enregistrés."""
        return {mw for middlewares in self.registry.values() for mw in middlewares}
