"""
    Данный модуль содержит реализацию класса Покупатель, сущность, при помощи которой телеграмм бот оперирует с данными
пользователя являющегося источником заказов на приобретение товаров. Класс покупатель является дочерним для класса User.
"""
import sys
from marshmallow import Schema, fields, post_load
from typing import Optional, List, Dict
import requests
import time
from datetime import timedelta, datetime
from threading import Semaphore
import json

from .user import User, UserPool
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
        super().__init__(tgId, orders_url, product_url)
        self.firstName: Optional[str] = firstName
        self.lastName: Optional[str] = lastName
        self.nickname: Optional[str] = nickname
        self.phoneNumber: Optional[str] = phoneNumber
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


class ShopperSchema(Schema):
    """Класс - схема данных предназначенная для валидации данных покупателя получаемых от внешнего API"""
    tgId = fields.Int(required=True, allow_none=False)
    firstName = fields.Str(allow_none=True)
    lastName = fields.Str(allow_none=True)
    nickname = fields.Str(allow_none=True)
    phoneNumber = fields.Str(allow_none=True)
    homeAddress = fields.Str(allow_none=True)
    orders_url = fields.Str(required=True, allow_none=False)
    product_url = fields.Str(required=True, allow_none=False)

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
        self.__shopper_schema: ShopperSchema = ShopperSchema()



    def gett(self, tg_id: int) -> Shopper:
        """
            Метод возвращает объект покупателя из пула покупателей по-указанному id. Если такового там нет,
        метод попытается получить информацию о покупателе из внешнего API и из локальной базы данных. Если и там
        информации о покупателе нет - будет создан и возвращен новый объект покупателя.
        """
        shopper = self._pool.get(tg_id, None)



        if not shopper:
            shopper = self.__api_gett(tg_id)
            self._pool[tg_id] = shopper

        if not shopper:
            shopper = Shopper(tgId=tg_id, orders_url=self._orders_url, product_url=self._product_url)
            self._pool[tg_id] = shopper

        shopper.update_activity_time()

        return shopper

    def __api_gett(self, tg_id: int) -> Optional[Shopper]:
        """Метод реализует получение данных пользователя от внешнего API"""
        try:
            response = requests.get('/'.join([self._user_url, str(tg_id)]), headers=self._content_type)
            if response.status_code == 200:
                data = json.loads(response.text)
                data["orders_url"] = self._orders_url
                data["product_url"] = self._product_url
                return self.__shopper_schema.loads(json.dumps(data))
            dev_log.info('Не удалось получить от сервера данные пользователя {}'.format(tg_id))

        except Exception as ex:
            dev_log.exception('При попытке получить от сервера данные пользователя {} произошла ошибка:'.format(tg_id),
                              exc_info=ex)

    def __api_put(self, shopper: Shopper) -> None:
        """Метод осуществляет сохранение измененных данных покупателя на внешнем сервере"""
        try:
            data = self.__shopper_schema.dumps(shopper)
            response = requests.put(self._user_url, data=data, headers=self._content_type)
            if response.status_code == 200:
                dev_log.debug('Данные пользователя {} успешно обновлены на сервере'.format(shopper.tgId))

        except Exception as ex:
            dev_log.exception('Не удалось обновить данные пользователя {} из-за ошибки:', exc_info=ex)

    def __api_post(self, shopper: Shopper) -> None:
        """Метод осуществляет добавление нового покупателя на внешний сервер"""
        try:
            data = self.__shopper_schema.dumps(shopper)
            response = requests.post(self._user_url, data=data, headers=self._content_type)
            if response.status_code == 200:
                dev_log.debug('Данные нового пользователя {} успешно добавлены на сервер'.format(shopper.tgId))

        except Exception as ex:
            dev_log.exception('Не удалось добавить данные нового пользователя {} из-за ошибки:', exc_info=ex)

    def __save_shoppers_data(self, list_shoppers: List[Shopper]) -> None:
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
                self.__api_put(i_shopper)
            elif not i_shopper.registered_on_server:
                self.__api_post(i_shopper)


    @execute_in_new_thread(daemon=False)
    def data_control(self) -> None:
        """
            Этот метод - бесконечный цикл выполняемый в отдельном потоке - служит для контроля востребованности данных
        пользователей. Если в пуле пользователей есть объекты, взаимодействие с которыми не осуществлялось установленное
        время - они будут удалены из оперативной памяти.
        """
        time_delta = timedelta(seconds=self._session_time)
        while self._session_time:
            time.sleep(self._session_time // 2)
            list_shopper_to_delete = list(filter(lambda i_shopper: datetime.now() - i_shopper.last_session > time_delta,
                                                 self._pool.values()))

            self.__save_shoppers_data(list_shopper_to_delete)

            new_pool = {i_id: i_shopper for i_id, i_shopper in self._pool.items()
                        if i_shopper not in list_shopper_to_delete}

            with Semaphore():
                initial_pool_size = sys.getsizeof(self._pool)
                self._pool = new_pool
                final_size_pool = sys.getsizeof(self._pool)

            dev_log.debug('Размер пула покупателей до/после очищения: {}/{}'.format(initial_pool_size,
                                                                                    final_size_pool))
            new_pool = None

    def add_bot(self, bot) -> None:
        """
            Метод принимает на вход объект телеграмм бота и присваивает его атрибуту self.__bot. В пуле покупателей
        объект телеграмм бота используется в методе __save_shoppers_data для отправки сообщения пользователю о
        завершении сессии, поэтому у передаваемого объекта бота должен быть реализован метод close_session
        """
        self._bot = bot
