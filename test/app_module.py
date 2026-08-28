from oizo.modules import Module
from app_service import appService
from app_controller import appController
from app_middleware import TestService, appMiddleware


class appModule(Module):
    imports = ()
    providers = (appService, TestService)
    controllers = (appController,)

    @staticmethod
    def configure(consumer):
        consumer.apply(appMiddleware).forRoutes("/test/*")
