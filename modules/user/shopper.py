"""
    Данный модуль содержит реализацию класса Покупатель, сущность, при помощи которой телеграмм бот оперирует с данными
пользователя являющегося источником заказов на приобретение товаров. Класс покупатель является дочерним для класса User.
"""
from marshmallow import fields, post_load
from typing import Optional, List
import time
from threading import Semaphore

from .user import User, UserPool, UserSchema
from ..orders import ShopperOrdersPool, Order, Basket
from ..logger import get_development_logger
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
                 firstName: Optional[str] = None,
                 lastName: Optional[str] = None,
                 nickname: Optional[str] = None,
                 phoneNumber: Optional[str] = None,
                 homeAddress: Optional[str] = None
                 ):
        super().__init__(tgId, orders_url, firstName, lastName, nickname, phoneNumber, homeAddress)
        self.__orders: Optional[ShopperOrdersPool] = None
        self._personal_data_cache = self._get_personal_data_cache()
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

    @execute_in_new_thread(daemon=True)
    def __get_orders(self) -> None:
        """Этот метод выполняется в отдельном потоке и служит для получения всех заказов пользователя"""
        with Semaphore():
            self.__orders = ShopperOrdersPool(self.tgId, self.orders_url)

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

    def update_orders(self) -> None:
        """Метод обновляет заказы пользователя"""
        with Semaphore():
            self.__orders = ShopperOrdersPool(self.tgId, self.orders_url)


class ShopperSchema(UserSchema):
    """Класс - схема данных предназначенная для валидации данных покупателя получаемых от внешнего API"""
    @post_load
    def create_shopper(self, data, **kwargs) -> Shopper:
        shopper = Shopper(**data)
        return shopper


class ShopperPool(UserPool):
    """
        Этот класс предназначен для хранения коллекции покупателей в одном месте, предоставления быстрого доступа к
    любому объекту покупателя, а так же для контроля актуальности данных покупателей. Через объект этого класса должно
    осуществляться любое взаимодействие с объектами покупателей. Так же объект этого класса осуществляет взаимодействие
    с внешним API, удаленно хранящим данные покупателей
    """
    def __init__(self, shopper_url: str, orders_url: str, session_time: Optional[int] = None):
        super().__init__(shopper_url, orders_url, ShopperSchema, Shopper, session_time)

    def _save_user_data(self, list_shoppers: List[Shopper]) -> None:
        """
            Данный метод является вспомогательным и используется в методе data_control. Для каждого пользователя в
        переданном списке этот метод отправляет сообщение об окончании сессии при помощи телеграмм бота, сохраняет
        данные пользователя в локальную базу данных, и, если пользователя был зарегистрирован во внешнем API и были
        изменены его данные - отправляет эти изменения на сервер. Если покупатель не был зарегистрирован на сервере -
        делается пост запрос с его данными на сервер.
        """
        super()._save_user_data(list_shoppers)

        for i_shopper in list_shoppers:
            for i_order in i_shopper.get_orders():
                i_order.save_on_server()

            basket = i_shopper.get_basket()
            basket.save_on_server()

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
