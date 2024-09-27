"""
    Данный модуль содержит реализацию класса Покупатель, сущность, при помощи которой телеграмм бот оперирует с данными
пользователя являющегося источником заказов на приобретение товаров. Класс покупатель является дочерним для класса User.
"""
import sys
from marshmallow import fields, post_load
from typing import Optional, List, Dict, Any
import requests
import time
from datetime import timedelta, datetime
from threading import Semaphore
import json

from .user import User, UserPool, UserSchema
from ..orders import ShopperOrdersPool, Order, Basket
from ..logger import get_development_logger
from ..products import Product
from ..utils import execute_in_new_thread


dev_log = get_development_logger(__name__)


class Shopper(User):
    """
        Класс Покупатель - является сущностью предназначенной для хранения, получения и преобразования данных
    пользователей необходимых для осуществления покупок.
    """
    def __init__(self,
                 tgId: int,
                 orders_url: str,
                 product_url: str,
                 firstName: Optional[str] = None,
                 lastName: Optional[str] = None,
                 nickname: Optional[str] = None,
                 phoneNumber: Optional[str] = None,
                 homeAddress: Optional[str] = None
                 ):
        super().__init__(tgId, orders_url, product_url, firstName, lastName, nickname, phoneNumber)
        self.homeAddress: Optional[str] = homeAddress
        self.__orders: Optional[ShopperOrdersPool] = None
        self.__personal_data_cache = self.__get_personal_data_cache()

        self.__get_orders()

    def __repr__(self) -> str:
        """
            Метод возвращает строку, содержащую основные данные покупателя: имя, телефон, адрес при применении к объекту
        покупателя метода str
        """
        text, name = [], None
        if self.nickname:
            name = self.nickname
        elif self.firstName :
            name = ' '.join([self.firstName, self.lastName])
        if name:
            text.append('<b>Имя:</b> {}'.format(name))

        if self.phoneNumber:
            text.append('<b>Номер телефона:</b> {}'.format(self.phoneNumber))

        if self.homeAddress:
            text.append('<b>Домашний адрес:</b> {}'.format(self.homeAddress))

        return '\n'.join(text)

    def __get_personal_data_cache(self) -> int:
        """
            Метод отсеивает из персональных данных пользователя значения None и из оставшихся значений вычисляет хэш.
        Это вспомогательный метод. Он необходим для определения - были ли изменены персональные данные покупателя.
        Применяется в функции is_changed
        """
        list_personal_data = [self.firstName, self.lastName, self.nickname, self.phoneNumber, self.homeAddress]
        list_personal_data = list(filter(lambda i_elem: not i_elem is None, list_personal_data))
        list_personal_data = list(map(str, list_personal_data))
        return hash(''.join(list_personal_data))

    def is_changed(self) -> bool:
        """Метод проверяет, были ли изменены персональны данные покупателя после их получения от внешнего API"""
        return not self.__get_personal_data_cache() == self.__personal_data_cache

    @execute_in_new_thread(daemon=True)
    def __get_orders(self) -> None:
        """Этот метод выполняется в отдельном потоке и служит для получения всех заказов пользователя"""
        with Semaphore():
            self.__orders = ShopperOrdersPool(self.tgId, self.orders_url, self.product_url)

    def get_orders(self) -> List[Order]:
        """При обращении к объекту пула заказов как к вызываемому объекту будет возвращен список заказов"""
        time_start = time.time()
        while time.time() - time_start < 15:
            if self.__orders:
                return self.__orders()

    def get_basket(self) -> Basket:
        """Метод возвращает корзину пользователя, представляющую собой заказ со статусом 0"""
        time_start = time.time()
        while time.time() - time_start < 15:
            if self.__orders:
                return self.__orders.basket

    def create_new_order(self) -> None:
        """Метод создает новый заказ из корзины пользователя"""
        self.__orders.create_new_order()


class ShopperSchema(UserSchema):
    """Класс - схема данных предназначенная для валидации данных покупателя получаемых от внешнего API"""
    homeAddress = fields.Str(allow_none=True)

    @post_load
    def create_shopper(self, data, **kwargs) -> Shopper:
        shopper = Shopper(**data)
        shopper.registered_on_server = True
        return shopper


class ShopperPool(UserPool):
    """
        Этот класс предназначен для хранения коллекции покупателей в одном месте, предоставления быстрого доступа к
    любому объекту покупателя, а так же для контроля актуальности данных покупателей. Через объект этого класса должно
    осуществляться любое взаимодействие с объектами покупателей. Так же объект этого класса осуществляет взаимодействие
    с внешним API, удаленно хранящим данные покупателей
    """
    def __init__(self, shopper_url: str, orders_url: str, product_url: str, session_time: Optional[int] = None):
        super().__init__(shopper_url, orders_url, product_url, ShopperSchema, self.__class__, session_time)

    def _save_user_data(self, list_shoppers: List[Shopper]) -> None:
        """
            Данный метод является вспомогательным и используется в методе data_control. Для каждого пользователя в
        переданном списке этот метод отправляет сообщение об окончании сессии при помощи телеграмм бота, сохраняет
        данные пользователя в локальную базу данных, и, если пользователя был зарегистрирован во внешнем API и были
        изменены его данные - отправляет эти изменения на сервер. Если покупатель не был зарегистрирован на сервере -
        делается пост запрос с его данными на сервер.
        """
        for i_shopper in list_shoppers:
            if self._bot:
                self._bot.close_session(i_shopper.tgId)

            i_shopper.saving_to_local_db()

            for i_order in i_shopper.get_orders():
                i_order.save_on_server()

            basket = i_shopper.get_basket()
            basket.save_on_server()

            if i_shopper.is_changed() and i_shopper.registered_on_server:
                self._api_put(i_shopper)
            elif not i_shopper.registered_on_server:
                self._api_post(i_shopper)

    def get_personal_data(self, tg_id: int) -> str:
        """
            Метод возвращает персональную информацию о покупателе в виде строки
        """
        data =  super()._api_get(tg_id, get_user_object=False)

        name = data.get("nickname", None)
        if name is None:
            name = " ".join([str(data.get("firstName", None)), str(data.get("lastName", None))])

        text = [
            f"<b>Имя:</b> {name}",
            f"<b>Номер телефона:</b> {str(data.get('phoneNumber', None))}",
            f"<b>Адрес доставки:</b> {str(data.get('homeAddress', None))}"
        ]

        return "\n".join(text)
