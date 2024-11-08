"""
    Данный модуль содержит реализацию класса Продавец, сущность, при помощи которой телеграмм бот оперирует с данными
пользователя являющегося потребителем и обработчиком заказов на приобретение товаров. Класс покупатель является
дочерним для класса User.
"""
from typing import Optional, List, Dict, Any, Union, Callable
import time
import requests
from marshmallow import post_load, Schema
from telebot.types import Message
import functools
from threading import Semaphore

from .user import User, UserPool, UserSchema, fields
from ..bot.message_deletion_blocker import dev_log
from ..orders import SellerOrdersPool, Order
from ..utils import execute_in_new_thread


class Seller(User):
    """
        Класс - модель продавца - является сущностью предназначенной для хранения, получения и преобразования данных
    пользователей необходимых для обработки заказов
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
        self.orders_pool: Optional[SellerOrdersPool] = None
        self.authorization: bool = False
        self.status: Optional[str] = None
        self.authorization_counter: int = 0

        self._personal_data_cache = self._get_personal_data_cache()
        self.__get_active_orders()

    @execute_in_new_thread(daemon=True)
    def __get_active_orders(self) -> None:
        """Этот метод служит для инициализации объекта хранящего заказы и выполняется в отдельном потоке"""
        with Semaphore():
            self.orders_pool = SellerOrdersPool(self.tgId, self.orders_url)

    def update_active_orders(self):
        """
            Данный метод служит для обновления активных заказов и может быть использован в API бота для выполнения
        команды от другой управляющей сущности
        """
        with Semaphore():
            self.orders_pool = None
            self.orders_pool = SellerOrdersPool(self.tgId, self.orders_url)

    def get_new_orders(self) -> List[Order]:
        """Метод возвращает список новых заказов"""
        time_start = time.time()
        while time.time() - time_start < 15:
            if self.orders_pool:
                return self.orders_pool.new

    def get_current_orders(self) -> List[Order]:
        """Метод возвращает список текущих заказов"""
        time_start = time.time()
        while time.time() - time_start < 15:
            if self.orders_pool:
                return self.orders_pool.current

    def __repr__(self) -> str:
        """
            Метод возвращает строку, содержащую основные данные продавца: имя, телефон, адрес при применении к объекту
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

        return '\n'.join(text)


class SellerSchema(UserSchema):
    """Класс - схема данных предназначенная для валидации данных продавца получаемых от внешнего API"""
    @post_load
    def create_shopper(self, data, **kwargs) -> Seller:
        seller = Seller(**data)
        return seller


class AuthorizationListSchema(Schema):
    """Схема получения от сервера и передачи ему же данных об авторизации продавцов"""
    tgId = fields.Int(required=True, allow_none=False)
    phoneNumber = fields.Str(required=True, dump_default="000")
    status = fields.Str(required=True, allow_none=False, load_only=True)


class AuthorizationResponseSchema(Schema):
    """Схема получения от сервера и передачи ему же данных об авторизации продавцов"""
    authorized = fields.Boolean(required=True, allow_none=False, load_only=True)
    status = fields.Str(required=False, allow_none=True, load_only=True, load_default="admin")   # АТРИБУТ load_default="admin" НУЖНО УБРАТЬ!!!


class SellerPool(UserPool):
    """
        Этот класс предназначен для хранения коллекции продавцов в одном месте, предоставления быстрого доступа к
    любому объекту продавца, а так же для контроля актуальности данных продавцов. Через объект этого класса должно
    осуществляться любое взаимодействие с объектами продавцов. Так же объект этого класса осуществляет взаимодействие
    с внешним API, удаленно хранящим данные продавцов
    """
    def __init__(self, seller_url: str, orders_url: str, authorization_url: str, session_time: Optional[int] = None):
        super().__init__(seller_url, orders_url, SellerSchema, Seller, session_time)

        self.__authorization_url: str = authorization_url
        self.__authorization_list_schema = AuthorizationListSchema()
        self.__authorization_response_schema = AuthorizationResponseSchema()
        self.__content_type: Dict[str, str] = {'Content-Type': 'application/json'}

    def __check_seller_authorization(self, seller: Seller) -> Seller:
        """
            Метод осуществляет проверку авторизации пользователя в качестве продавца путем выполнения запроса к API,
        где хранятся списки продавцов и наделения соответствующих полей продавца необходимыми для авторизации значениями
        """
        result = self.__api_check_authorization(seller)

        if result and result.get("authorized", False):
            seller.authorization = True
            seller.status = result.get("status", None)

        return seller

    def __api_check_authorization(self, seller: Seller) -> Dict[str, Any]:
        """Метод выполняет запрос к API для проверки авторизации продавца"""
        try:
            data = self.__authorization_list_schema.dumps(seller)
            response = requests.post("/".join([self.__authorization_url, "check"]), data=data,
                                     headers=self.__content_type)

            if response.status_code == 200:
                return self.__authorization_response_schema.loads(response.text)

            dev_log.info(
                f"Не удалось проверить авторизацию пользователя {seller.tgId} статус код {response.status_code}")

        except Exception as ex:
            dev_log.exception(f"Не удалось проверить авторизацию пользователя {seller.tgId} из-за ошибки",
                              exc_info=ex)

    def repeat_authorization(self, seller: Union[int, Message, Seller]) -> str:
        if isinstance(seller, int):
            seller = self.get(seller)

        elif isinstance(seller, Message):
            seller = self.get(seller.chat.id)

        if seller.phoneNumber is None:
            return "phone_number_is_none"

        else:
            seller = self.__check_seller_authorization(seller)
            if seller.authorization:
                return "ok"
            return "no"

    def get(self, tg_id: int) -> Seller:
        """
            Метод дополняет функционал метода родительского класса своим функционалом авторизации пользователя в
        качестве продавца.
        """
        seller: Seller = super().get(tg_id=tg_id)  # Возвращается объект User, но считаем его как Seller

        if seller.authorization_counter == 0:
            self.__check_seller_authorization(seller)
            seller.authorization_counter += 1

        return seller


    def access_control(self, status: List[str] = ["admin", "seller"]) -> Callable:
        """
            Метод - декоратор, предназначенный для контроля доступа пользователей к различным декорируемым функциям -
        обработчикам сообщений
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapped(*args, **kwargs) -> Callable:
                messages = list(filter(lambda i_arg: isinstance(i_arg, Message), args))
                if len(messages) > 0:
                    message: Message = messages[0]
                else:
                    messages = list((filter(lambda i_arg: isinstance(i_arg, Message), kwargs.values())))
                    message: Message = messages[0]

                seller = self.get(tg_id=message.chat.id)

                if seller.authorization and seller.status in status:
                    return func(*args, **kwargs)

                else:
                    if self._bot:
                        self._bot.send_message(message.chat.id,
                                               "У вас недостаточно прав для выполнения этого действия. Пожалуйста, авторизуйтесь")
                    dev_log.info(f"Неавторизованный пользователь {message.chat.id} пытается получить доступ к боту")

            return wrapped
        return decorator

