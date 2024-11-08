import pytest
import random

from modules.user.shopper import ShopperPool
from modules.user.seller import SellerPool
from modules.test.server.app import create_app
from modules.test.server.random_data import UserFaker
from modules.test.server.model import db


@pytest.fixture()
def shopper_url():
    """Фикстура возвращает url для получения данных пользователей"""
    return "http://127.0.0.1:5000/user"


@pytest.fixture()
def order_url():
    """Фикстура возвращает url для получения данных о заказах"""
    return "http://127.0.0.1:5000/order"


@pytest.fixture()
def category():
    """Фикстура возвращает url для получения данных о категориях продуктов"""
    return "http://127.0.0.1:5000/category"


@pytest.fixture()
def product():
    """Фикстура возвращает url для получения данных продуктов"""
    return "http://127.0.0.1:5000/product"


@pytest.fixture()
def authorization_url():
    """Фикстура возвращает url для авторизации пользователей"""
    return "http://127.0.0.1:5000/seller"


@pytest.fixture()
def url_no_valid(shopper_url, shopper_pool):
    """Фикстура возвращает недействительный url"""
    return "http://127.0.0.1:5000/no_valid"


@pytest.fixture(scope="session")
def app():
    """Фикстура запускает тестовый сервер веб приложения и возвращает экземпляр приложения"""
    app = create_app()
    app.start_testing_server()
    return app


@pytest.fixture
def data_base(app):
    with app.app_context():
        yield db


@pytest.fixture
def shopper_pool(shopper_url, order_url):
    return ShopperPool(
        shopper_url=shopper_url,
        orders_url=order_url,
        session_time=0.00001,
    )


@pytest.fixture
def seller_pool(shopper_url, order_url, authorization_url):
    return SellerPool(
        seller_url=shopper_url,
        orders_url=order_url,
        session_time=0.00001,
        authorization_url=authorization_url,
    )


@pytest.fixture(scope="module")
def user_id():
    return random.randint(1000000, 99999999)
