from oizo.modules import Module
from app_service import appService
from app_controller import appController


class appModule(Module):
    imports = ()
    providers = (appService,)
    controllers = (appController,)
