import dishka


class Injectable:
    def __init__(self):
        super().__init__()

    def __init_subclass__(cls, scope: dishka.BaseScope = dishka.Scope.APP) -> None:
        super().__init_subclass__()
        cls.scope = scope
