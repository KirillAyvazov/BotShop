from flask import Flask
from threading import Thread
import time
import os

from .model import db
from .routs import create_routs
from .. import project_path


class FlaskTestServer(Flask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __start(self):
        create_routs(self)
        self.run(debug=False) # ОТЛАДКУ НЕ ВКЛЮЧАТЬ! ПРИЛОЖЕНИЕ УПАДЕТ ИЗ_ЗА ОШИБОК В БИБЛИОТЕКЕ!

    def start_testing_server(self) -> None:
        """Метод для запуска тестового приложения в отдельном потоке"""
        thread = Thread(target=self.__start, daemon=True, name="testing_server")
        thread.start()
        time.sleep(0.2)


def create_app() -> FlaskTestServer:
    """Функция создает экземпляр фласк приложения"""
    app = FlaskTestServer(__name__, instance_path="/home/kirill/project/app_path")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fff.db"

    db.init_app(app)
    with app.app_context():
        db.drop_all()
        db.create_all()

    return app

