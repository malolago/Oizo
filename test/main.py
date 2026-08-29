from app_module import appModule

from oizo.runtime import App

if __name__ == "__main__":
    app = App()
    app.create(appModule)
    app.listen(debug=True)
