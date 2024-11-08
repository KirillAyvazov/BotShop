import time
import pytest
import pytz

from modules.user.seller import Seller
from modules.test.server.random_data import UserFaker
from modules.test.server.model import User


def test_normal_conditions(data_base, seller_pool, user_id):
    """
        Тест работы пула покупателей в нормальных условиях
            - проверяем, что размер пула равен нулю;
            - получаем из пула незарегистрированного пользователя;
            - проверяем что полученный объект из класса Shopper и что его поля is None;
            - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) и
                is_changed(изменен) = False
            - присваиваем полям пользователя случайные значения
            - проверяем что размер пула равен единице;
            - делаем один шаг метода контроля данных;
            - проверяем, что размер пула равен нулю;
            - проверяем, что после отправки данных на сервер атрибут объекта user is_changed(изменен) = False;
            - проверяем, что данные пользователя корректно записались в базу данных веб приложения;
            - получаем данные пользователя из пула и сравниваем их с теми что были отправлены на сервер
    """
    user_fake = UserFaker(user_id)

    assert seller_pool.get_pool_size() == 0

    user = seller_pool.get(user_id)

    assert isinstance(user, Seller)
    assert user.tgId == user_id
    assert user.firstName is None
    assert user.lastName is None
    assert user.nickname is None
    assert user.phoneNumber is None
    assert user.homeAddress is None

    assert user.registered_on_server == False
    assert user.is_changed() == False

    user.firstName = user_fake.firstName
    user.lastName = user_fake.lastName
    user.nickname = user_fake.nickname
    user.phoneNumber = user_fake.phoneNumber
    user.homeAddress = user_fake.homeAddress

    assert seller_pool.get_pool_size() == 1

    time.sleep(0.1)
    seller_pool.data_control(test_step=2)
    time.sleep(0.1)

    assert seller_pool.get_pool_size() == 0

    assert user.is_changed() == False   # Этот тест не проходит!

    user_from_db = data_base.session.get(User, user_id)
    assert isinstance(user_from_db, User)
    assert user.tgId == user_from_db.tgId
    assert user.firstName == user_from_db.firstName
    assert user.lastName == user_from_db.lastName
    assert user.nickname == user_from_db.nickname
    assert user.phoneNumber == user_from_db.phoneNumber
    assert user.homeAddress == user_from_db.homeAddress

    user = seller_pool.get(user_id)
    assert user.tgId == user_fake.tgId
    assert user.firstName == user_fake.firstName
    assert user.lastName == user_fake.lastName
    assert user.nickname == user_fake.nickname
    assert user.phoneNumber == user_fake.phoneNumber
    assert user.homeAddress == user_fake.homeAddress


def test_changing_user_data(seller_pool, data_base, user_id):
    """
        Тест проверят сохранение небольших изменений данных пользователя.
            - получаем данные пользователя, который был зарегистрирован в тесте test_normal_conditions;
            - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = True и
                is_changed(изменен) = False;
            - проверяем что значение атрибутов объекта user is_changed(изменен) = True
            - изменяем одно поле объекта пользователя;
            - проверяем что размер пула равен единице;
            - делаем один шаг метода контроля данных;
            - проверяем, что размер пула равен нулю;
            - сравниваем все поля пользователя попавшие в базу данных с предыдущими значениями и с учетом изменений
            - проверяем что после отправки данных на сервер атрибут объекта user is_changed(изменен) = False
    """
    user_fake = UserFaker.get_fake_user(user_id)
    user_fake.firstName = "ТЕСТОВОЕ_ИМЯ"

    user = seller_pool.get(user_id)

    assert user.registered_on_server == True
    assert user.is_changed() == False

    user.firstName = user_fake.firstName

    assert user.is_changed() == True

    assert seller_pool.get_pool_size() == 1

    time.sleep(0.1)
    seller_pool.data_control(test_step=2)
    time.sleep(0.1)

    assert seller_pool.get_pool_size() == 0

    user_from_db = data_base.session.get(User, user_id)
    assert isinstance(user_from_db, User)
    assert user_fake.tgId == user_from_db.tgId
    assert user_fake.firstName == user_from_db.firstName
    assert user_fake.lastName == user_from_db.lastName
    assert user_fake.nickname == user_from_db.nickname
    assert user_fake.phoneNumber == user_from_db.phoneNumber
    assert user_fake.homeAddress == user_from_db.homeAddress

    assert user.is_changed() == False   # Этот тест не проходит!