import time
import pytest
import pytz

from modules.user.shopper import Shopper
from modules.test.server.random_data import UserFaker
from modules.test.server.model import User


def test_normal_conditions(shopper_pool, data_base, user_id):
    """
        Тест работы пула покупателей в нормальных условиях
            - проверяем, что размер пула равен нулю;
            - получаем из пула незарегистрированного пользователя;
            - проверяем что полученный объект класса Shopper и что его поля is None;
            - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
                is_changed(изменен) = False
            - присваиваем полям пользователя случайные значения
            - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
                is_changed(изменен) = True
            - проверяем что размер пула равен единице;
            - делаем один шаг метода контроля данных;
            - проверяем, что размер пула равен нулю;
            - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = True и
                is_changed(изменен) = False
            - проверяем, что данные пользователя корректно записались в базу данных веб приложения;
            - получаем данные пользователя из пула и сравниваем их с теми что были отправлены на сервер
    """
    user_fake = UserFaker(user_id)

    assert shopper_pool.get_pool_size() == 0

    user = shopper_pool.get(user_id)

    assert isinstance(user, Shopper)
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

    assert user.registered_on_server == False
    assert user.is_changed() == True

    assert shopper_pool.get_pool_size() == 1

    time.sleep(0.1)
    shopper_pool.data_control(test_step=2)
    time.sleep(0.1)

    assert shopper_pool.get_pool_size() == 0

    assert user.registered_on_server == True
    assert user.is_changed() == False

    user_from_db = data_base.session.get(User, user_id)
    assert isinstance(user_from_db, User)
    assert user.tgId == user_from_db.tgId
    assert user.firstName == user_from_db.firstName
    assert user.lastName == user_from_db.lastName
    assert user.nickname == user_from_db.nickname
    assert user.phoneNumber == user_from_db.phoneNumber
    assert user.homeAddress == user_from_db.homeAddress

    user = shopper_pool.get(user_id)
    assert user.tgId == user_fake.tgId
    assert user.firstName == user_fake.firstName
    assert user.lastName == user_fake.lastName
    assert user.nickname == user_fake.nickname
    assert user.phoneNumber == user_fake.phoneNumber
    assert user.homeAddress == user_fake.homeAddress


def test_changing_user_data(shopper_pool, data_base, user_id):
    """
        Тест проверят сохранение небольших изменений данных пользователя.
            - получаем данные пользователя, который был зарегистрирован в тесте test_normal_conditions;
            - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = True и
                is_changed(изменен) = False;
            - изменяем у объекта user поле firstName
            - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = True и
                is_changed(изменен) = True;
            - проверяем что размер пула равен единице;
            - делаем один шаг метода контроля данных;
            - проверяем, что размер пула равен нулю;
            - сравниваем все поля пользователя попавшие в базу данных с предыдущими значениями и с учетом изменений
            - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = True и
                is_changed(изменен) = False;
    """
    user_fake = UserFaker.get_fake_user(user_id)
    user_fake.firstName = "ТЕСТОВОЕ_ИМЯ"

    user = shopper_pool.get(user_id)

    assert user.registered_on_server == True
    assert user.is_changed() == False

    user.firstName = user_fake.firstName

    assert user.registered_on_server == True
    assert user.is_changed() == True

    assert shopper_pool.get_pool_size() == 1

    time.sleep(0.1)
    shopper_pool.data_control(test_step=2)
    time.sleep(0.1)

    assert shopper_pool.get_pool_size() == 0

    user_from_db = data_base.session.get(User, user_id)
    assert isinstance(user_from_db, User)
    assert user_fake.tgId == user_from_db.tgId
    assert user_fake.firstName == user_from_db.firstName
    assert user_fake.lastName == user_from_db.lastName
    assert user_fake.nickname == user_from_db.nickname
    assert user_fake.phoneNumber == user_from_db.phoneNumber
    assert user_fake.homeAddress == user_from_db.homeAddress

    assert user.registered_on_server == True
    assert user.is_changed() == False


def test_no_connection(shopper_pool, user_id, url_no_valid, data_base):
    """
        Тест работы пула покупателей в условиях неудавшегося запроса к API на этапе получения данных пользователя.
    Предполагаем что объект пользователя не был изменен. По завершении сессии пользователя объект должен быть удален
    из пула, данные на сервере не должны быть изменены.
        - ломаем url для получения данных пользователей;
        - получаем данные пользователя, который был зарегистрирован в тесте test_normal_conditions;
        - проверяем что пришел объект пользователя с полями is none;
        - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
            is_changed(изменен) = False
        - проверяем, что размер пула равен 1;
        - делаем один шаг метода контроля данных;
        - проверяем, что размер пула равен нулю;
        - сравниваем все исходные значения полей пользователя с теми что находятся в базе данных;
        - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
            is_changed(изменен) = False
    """
    setattr(shopper_pool, "_user_url", url_no_valid)

    user = shopper_pool.get(user_id)

    assert isinstance(user, Shopper)
    assert user.tgId == user_id
    assert user.firstName is None
    assert user.lastName is None
    assert user.nickname is None
    assert user.phoneNumber is None
    assert user.homeAddress is None

    assert user.registered_on_server == False
    assert user.is_changed() == False

    assert shopper_pool.get_pool_size() == 1

    time.sleep(0.1)
    shopper_pool.data_control(test_step=2)
    time.sleep(0.1)

    assert shopper_pool.get_pool_size() == 0

    user_fake = UserFaker.get_fake_user(user_id)
    user_from_db = data_base.session.get(User, user_id)
    assert isinstance(user_from_db, User)
    assert user_fake.tgId == user_from_db.tgId
    assert user_fake.firstName == user_from_db.firstName
    assert user_fake.lastName == user_from_db.lastName
    assert user_fake.nickname == user_from_db.nickname
    assert user_fake.phoneNumber == user_from_db.phoneNumber
    assert user_fake.homeAddress == user_from_db.homeAddress

    assert user.registered_on_server == False
    assert user.is_changed() == False


def test_recovery_connection(shopper_pool, user_id, url_no_valid, shopper_url, data_base):
    """
        Тест работы пула покупателей в условиях неудавшегося запроса к API на этапе получения данных пользователя и
    восстановления связи с сервером при завершении сессии пользователя.
    Предполагаем что объект пользователя не был изменен. Перед получением данных пользователя пропадает связь с сервером.
    Перед завершением сессии пользователя связь с сервером восстанавливается. По завершении сессии пользователя объект
    должен быть удален из пула, данные на сервере не должны быть изменены.
        - ломаем url для получения данных пользователей;
        - получаем данные пользователя, который был зарегистрирован в тесте test_normal_conditions;
        - проверяем что пришел объект пользователя с полями is none;
        - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
            is_changed(изменен) = False
        - проверяем, что размер пула равен 1;
        - делаем один шаг метода контроля данных;
        - проверяем, что размер пула равен 0;
        - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
            is_changed(изменен) = False
        - восстанавливаем url для получения данных пользователей;
        - делаем один шаг метода контроля данных;
        - проверяем, что размер пула равен нулю;
        - сравниваем все исходные значения полей пользователя с теми что находятся в базе данных;
    """
    setattr(shopper_pool, "_user_url", url_no_valid)

    user = shopper_pool.get(user_id)

    assert isinstance(user, Shopper)
    assert user.tgId == user_id
    assert user.firstName is None
    assert user.lastName is None
    assert user.nickname is None
    assert user.phoneNumber is None
    assert user.homeAddress is None

    assert user.registered_on_server == False
    assert user.is_changed() == False

    assert shopper_pool.get_pool_size() == 1

    setattr(shopper_pool, "_user_url", shopper_url)

    time.sleep(0.1)
    shopper_pool.data_control(test_step=2)
    time.sleep(0.1)

    assert shopper_pool.get_pool_size() == 0

    user_fake = UserFaker.get_fake_user(user_id)
    user_from_db = data_base.session.get(User, user_id)
    assert isinstance(user_from_db, User)
    assert user_fake.tgId == user_from_db.tgId
    assert user_fake.firstName == user_from_db.firstName
    assert user_fake.lastName == user_from_db.lastName
    assert user_fake.nickname == user_from_db.nickname
    assert user_fake.phoneNumber == user_from_db.phoneNumber
    assert user_fake.homeAddress == user_from_db.homeAddress

    assert user.registered_on_server == False
    assert user.is_changed() == False


def test_no_connection_and_change_user(shopper_pool, user_id, url_no_valid, shopper_url, data_base):
    """
        Тест работы пула покупателей в условиях неудавшегося запроса к API на этапе получения данных пользователя.
    Предполагаем что объект пользователя после получения данных был изменен. После неудачной попытки отправить данные
    пользователя на сервер, объект пользователя должен остаться в пуле. После восстановления связи с сервером, по
    завершении сессии пользователя объект должен быть удален из пула, данные на сервере должны быть изменены правильно -
    то есть должны быть обновлены только измененные поля.
        - ломаем url для получения данных пользователей;
        - получаем данные пользователя, который был зарегистрирован в тесте test_normal_conditions;
        - проверяем что пришел объект пользователя с полями is none;
        - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
            is_changed(изменен) = False
        - проверяем, что размер пула равен 1;
        - меняем значение одного поля пользователя;
        - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
            is_changed(изменен) = True
        - делаем один шаг метода контроля данных;
        - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
            is_changed(изменен) = True;
        - проверяем что размер пула равен 1;
        - восстанавливаем url для получения данных пользователей;
        - делаем один шаг метода контроля данных;
        - проверяем что значения атрибутов объекта user registered_on_server (зарегистрирован на сервере) = False и
            is_changed(изменен) = True;
        - проверяем, что размер пула равен нулю;


        - сравниваем все исходные значения полей пользователя с теми что находятся в базе данных;
    """
    print("ТОТ САМЫЙ ТЕСТ")
    setattr(shopper_pool, "_user_url", url_no_valid)

    user = shopper_pool.get(user_id)

    assert isinstance(user, Shopper)
    assert user.tgId == user_id
    assert user.firstName is None
    assert user.lastName is None
    assert user.nickname is None
    assert user.phoneNumber is None
    assert user.homeAddress is None

    assert user.no_connection_server == True
    assert user.registered_on_server == False
    assert user.is_changed() == False

    assert shopper_pool.get_pool_size() == 1

    user_fake = UserFaker.get_fake_user(user_id)
    user_fake.phoneNumber = "03"
    user.phoneNumber = user_fake.phoneNumber

    assert user.registered_on_server == False
    assert user.is_changed() == True

    time.sleep(0.1)
    shopper_pool.data_control(test_step=2)
    time.sleep(0.1)

    assert user.registered_on_server == False
    assert user.is_changed() == True

    assert shopper_pool.get_pool_size() == 1

    setattr(shopper_pool, "_user_url", shopper_url)

    time.sleep(0.1)
    shopper_pool.data_control(test_step=2)
    time.sleep(0.1)

    assert user.registered_on_server == True
    assert user.is_changed() == False

    assert shopper_pool.get_pool_size() == 0




