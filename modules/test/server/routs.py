import random
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

from .model import User, db

valid_user_key = [
    "tgId",
    "firstName",
    "lastName",
    "nickname",
    "phoneNumber",
    "homeAddress",
]


def create_routs(app: Flask) -> None:
    """Функция создает роуты для фласк приложения"""

    @app.route("/", methods=["GET"])
    def hello():
        return "Тестовый сервер запущен", 200

    @app.route("/user/<int:tg_id>", methods=["GET"])
    def get_user(tg_id: Optional[int] = None):
        with app.app_context():
            user = db.session.query(User).get(tg_id)

            if user:
                json_data = {
                    i_key: i_val
                    for i_key, i_val in user.__dict__.items()
                    if i_key in valid_user_key
                }
                return jsonify(json_data)

            return "Not Found", 404

    @app.route("/user", methods=["POST"])
    def post_user():
        data: Dict[str, Any] = request.get_json()
        data = {
            i_key: i_val for i_key, i_val in data.items() if i_key in valid_user_key
        }

        with app.app_context():
            try:
                user = User(**data)
                db.session.add(user)
                db.session.commit()
            except Exception:
                db.session.rollback()
                return "No", 400

        return "OK", 200

    @app.route("/user", methods=["PUT"])
    def put_user():
        data = request.get_json()
        tg_id = data.get("tgId", None)
        if tg_id:
            with app.app_context():
                user = db.session.query(User).get(tg_id)
                for i_key, i_val in data.items():
                    setattr(user, i_key, i_val)

                db.session.add(user)
                db.session.commit()

        return "OK", 200

    @app.route("/order/<int:user_id>", methods=["GET"])
    def get_order(user_id: int):
        data = {"idOrder": random.randint(100, 10000)}
        return jsonify(data), 200

    @app.route("/order", methods=["POST"])
    def post_order():
        return "OK", 200
