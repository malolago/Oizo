from oizo.runtime import App
import inspect
from app_module import appModule

if __name__ == "__main__":
    app = App()
    app.create(appModule)
    app.listen()
