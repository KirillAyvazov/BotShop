"""
    Данный модуль содержит реализацию базового класса - модели пользователя, который является родительским классом для
класса Продавца и Покупателя. Данный клас содержит общие характеристики и решает общие задачи двух дочерних классов.
    К общим задачам двух классов Продавец и Покупатель можно отнести необходимость хранения в локальной базе данных бота
информации о полученных и переданных пользователем телеграмма сообщениях, а так же время его последней активности. Эти
данные необходимы для реализации исчезающих сообщений и завершения сессии пользователя.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    PrimaryKeyConstraint,
    DateTime,
    create_engine,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, timedelta
import pytz
from typing import List, Literal, Dict, Any, Callable, Optional, Union, Tuple
import os
from queue import Queue, LifoQueue
from telebot.types import Message
import requests
import json
from abc import ABC
import time
from threading import Semaphore
import sys
from marshmallow import Schema, fields

from ..logger import get_development_logger
from ..products import Product
from ..utils import execute_in_new_thread


dev_log = get_development_logger(__name__)
moscow_tz = pytz.timezone("Europe/Moscow")

Base = declarative_base()

if not os.path.exists("database"):
    os.makedirs("database")
engine = create_engine(
    "sqlite:///{}".format(os.path.join("database", "user_database.db"))
)

Session = sessionmaker(bind=engine)
session = Session()

ObjectName = Literal["bot", "user"]


class UserTable(Base):
    """
        Класс - представление таблицы базы данных в которой хранятся данные необходимые для корректной работы класса
    Пользователя
    """

    __tablename__ = "user"

    tgId = Column(Integer)
    message_id_bot_to_user = Column(String, nullable=False, default="")
    message_id_user_to_bot = Column(String, nullable=False, default="")
    last_session = Column(DateTime, default=datetime.now(moscow_tz))
    notifications = relationship("NotificationTable")

    __table_args__ = (PrimaryKeyConstraint("tgId"),)


class NotificationTable(Base):
    """Класс - модель таблицы для хранения id уведомлений пользователей"""

    __tablename__ = "notification"

    id = Column(Integer)
    user_id = Column(Integer)
    notification_id = Column(Integer)

    __table_args__ = (
        PrimaryKeyConstraint("id"),
        ForeignKeyConstraint(["user_id"], ["user.tgId"]),
    )


Base.metadata.create_all(engine)


class User:
    """
        Класс - содержащий основные атрибуты и методы необходимые для корректной работы с телеграмм ботом и
    предназначенный для хранения данных пользователя и управления ими.
    """

    def __init__(
        self,
        tg_id: int,
        orders_url: str,
        firstName: Optional[str] = None,
        lastName: Optional[str] = None,
        nickname: Optional[str] = None,
        phoneNumber: Optional[str] = None,
        homeAddress: Optional[str] = None,
    ):
        self.tgId: int = tg_id
        self.orders_url: str = orders_url
        self.firstName: Optional[str] = firstName
        self.lastName: Optional[str] = lastName
        self.nickname: Optional[str] = nickname
        self.phoneNumber: Optional[str] = phoneNumber
        self.homeAddress: Optional[str] = homeAddress
        self.__message_id_bot_to_user = Queue(30)
        self.__message_id_user_to_bot = Queue(30)
        self.__recently_deleted_messages = list()
        self.last_session: Optional[datetime] = None
        self.__queue_of_steps = LifoQueue(40)
        self.registered_on_server: bool = False
        self.product_index: int = 0
        self.order_index: int = 0
        self.category_index: int = 0
        self.product_viewed: Optional[Product] = None
        self.order_viewed: Optional[Product] = None
        self.count_product: int = 1
        self.back: bool = False

        self._personal_data_cache: Optional[int] = None
        self.__restore_data_in_local_db()

    def __restore_data_in_local_db(self) -> None:
        """
            Данный метод восстанавливает данные пользователя по-указанному id из локальной базы данных. Если в базе
        данных данные пользователя не найдены - в ней будет создана новая запись с указанным id пользователя и всем
        полям будут присвоены значения по умолчанию. Полученные данные из базы присваиваются объекту класса в качестве
        атрибутов.
        """
        user_table = session.get(UserTable, self.tgId)

        if user_table:
            for i_elem in [
                i_elem for i_elem in user_table.message_id_user_to_bot.split(",")
            ]:
                self.__message_id_user_to_bot.put(i_elem)

            for i_elem in [
                i_elem for i_elem in user_table.message_id_bot_to_user.split(",")
            ]:
                self.__message_id_bot_to_user.put(i_elem)

            self.last_session = datetime.strptime(
                str(user_table.last_session), "%Y-%m-%d %H:%M:%S.%f"
            )

        else:
            user_table = UserTable(tgId=self.tgId)
            session.add(user_table)
            try:
                session.commit()
                self.__restore_data_in_local_db()
            except Exception as ex:
                session.rollback()
                dev_log.exception(
                    "Не удалось добавить запись о пользователе {} в локальную базу данных".format(
                        self.tgId
                    ),
                    exc_info=ex,
                )

    def __object_control(self, object_name: ObjectName) -> Queue[int]:
        """
            Метод осуществляет контроль соответствия переданной строки возможным значениям литерала ObjectName.
        Если object_name не соответствует ни одному допустимому значению, возбуждается исключение ValueError.
            Если имя сущности == bot, возвращается список d сообщений полученных от бота. Если имя сущности равно
        user - возвращается список id сообщений отправленных пользователем.
            Это вспомогательный метод. Он используется в методах append_message и pop_message
        """
        if object_name == "bot":
            return self.__message_id_bot_to_user
        elif object_name == "user":
            return self.__message_id_user_to_bot
        raise ValueError('Метод должен принимать на вход строку "bot" "user"')

    def append_message(self, message_id: int, object_name: ObjectName) -> None:
        """
            Метод получает на вход id сообщений и строку с названием сущности источника сообщения - bot или user.
        Если это название == bot, то метод работает с очередью id сообщений отправленных ботом пользователю. Если же
        название сущности user, то метод работает с id сообщений отправленных пользователем боту.
            Метод предназначен для регистрации нового id сообщения в перечне id сообщений пересланных от указанной
        сущности.
        """
        queue_message_id: Queue[int] = self.__object_control(object_name)
        queue_message_id.put(message_id)

    def pop_message(self, object_name: ObjectName, message_limit: int) -> List[int]:
        """
            Метод получает на вход строку с названием сущности - bot или user. Если это название == bot, то метод
        работает с очередью id сообщений отправленных ботом пользователю. Если же название сущности user, то метод
        работает с id сообщений отправленных пользователем боту
            Метод возвращает список id сообщений пересланных указанной сущностью, которые переполняют установленный в
        файле конфигурации лимит. Сообщения, полученные от данного метода, должны быть удалены из чата с пользователем
        внешней, вызывающей этот метод функцией. Данный метод так же удалит id которые он вернул из отслеживания.
        """
        queue_message_id: Queue[int] = self.__object_control(object_name)

        list_messages_delete = []
        while queue_message_id.qsize() > message_limit:
            list_messages_delete.append(queue_message_id.get())

        self.__recently_deleted_messages.extend(list_messages_delete)
        self.__recently_deleted_messages = self.__recently_deleted_messages[-10:]

        return list_messages_delete

    def update_activity_time(self) -> None:
        """
            Метод обновляет дату и время последней активности пользователя. Функция применяется для контроля свежести
        данных пользователя
        """
        self.last_session = datetime.now(moscow_tz)

    def saving_to_local_db(self) -> None:
        """Метод сохраняет (обновляет) необходимые для корректной работы данные пользователя в локальную базу данных"""
        session.query(UserTable).filter(UserTable.tgId == self.tgId).update(
            {
                "message_id_bot_to_user": ",".join(
                    [
                        str(self.__message_id_bot_to_user.get())
                        for _ in range(self.__message_id_bot_to_user.qsize())
                    ]
                ),
                "message_id_user_to_bot": ",".join(
                    [
                        str(self.__message_id_user_to_bot.get())
                        for _ in range(self.__message_id_user_to_bot.qsize())
                    ]
                ),
                "last_session": self.last_session,
            },
            synchronize_session="fetch",
        )

        try:
            session.commit()

        except Exception as ex:
            session.rollback()
            dev_log.exception(
                "Не удалось сохранить данные пользователя {} в локальную базу данных".format(
                    self.tgId
                ),
                exc_info=ex,
            )

    def register_step(self, step: Callable) -> None:
        """
            Метод осуществляет регистрацию функции в очереди LIFO, которую пользователь должен запомнить и выполнить при
        необходимости. По факту, этот метод это способ избежать параллельного импорта в проекте. Зарегистрированные
        таким образом функции должны принимать на вход объект Message из библиотеки telebot.
        """
        self.__queue_of_steps.put(step)

    def perform_saved_step(self, message: Message) -> Optional[Any]:
        """
            Метод выполняет последний зарегистрированный пользователем шаг и возвращает результат его работы.
        В качестве аргумента этот метод получает объект Message из библиотеки telebot, который он передает в
        исполняемую функцию
        """
        func: Callable = self.__queue_of_steps.get()
        return func(message)

    def get_notification_id(self, delete=False) -> List[int]:
        """
            Метод возвращает список id уведомлений отправленных пользователю. Если передать параметр delete=True - эти
        сообщения будут удалены из базы данных
        """
        user: UserTable = session.query(UserTable).get(self.tgId)
        list_notifications_id = [
            i_notification.notification_id for i_notification in user.notifications
        ]

        if delete:
            try:
                for i_notification in user.notifications:
                    session.delete(i_notification)
                    session.commit()
            except Exception as ex:
                dev_log.exception(
                    f"Не удалось удалить из базы данных"
                    f"уведомления пользователя {self.tgId}",
                    exc_info=ex,
                )
                session.rollback()

        return list_notifications_id

    def _get_personal_data_cache(self) -> int:
        """
            Метод отсеивает из персональных данных пользователя значения None и из оставшихся значений вычисляет хэш.
        Это вспомогательный метод. Он необходим для определения - были ли изменены персональные данные покупателя.
        Применяется в функции is_changed
        """
        list_personal_data = [
            self.firstName,
            self.lastName,
            self.nickname,
            self.phoneNumber,
            self.homeAddress,
        ]
        list_personal_data = list(
            filter(lambda i_elem: not i_elem is None, list_personal_data)
        )
        list_personal_data = list(map(str, list_personal_data))
        return hash("".join(list_personal_data))

    def is_changed(self) -> bool:
        """Метод проверяет, были ли изменены персональны данные пользователя после их получения от внешнего API"""
        return not self._get_personal_data_cache() == self._personal_data_cache

    def update_personal_data_cache(self) -> None:
        """
            Метод обновляет значение атрибута _personal_data_cache на актуальное значение с учетом произошедших
        изменений объекта. Этот метод используется при успешной отправке данных пользователя на сервер, что бы изменить
        статус объекта с "измененного" на "сохраненный"
        """
        self._personal_data_cache = self._get_personal_data_cache()


class UserSchema(Schema):
    """Класс - схема данных предназначенная для валидации данных пользователя получаемых от внешнего API"""

    tgId = fields.Int(required=True, allow_none=False)
    firstName = fields.Str(allow_none=True)
    lastName = fields.Str(allow_none=True)
    nickname = fields.Str(allow_none=True)
    phoneNumber = fields.Str(allow_none=True)
    homeAddress = fields.Str(allow_none=True)
    orders_url = fields.Str(required=True, allow_none=False)


class UserPool(ABC):
    """
        Данный является родительским для классов ShopperPool и SellerPool и является моделью объекта,
    предназначенного для хранения коллекции пользователей в одном месте, предоставления быстрого доступа к
    любому объекту пользователя, а так же для контроля актуальности данных пользователей. Через объект этого класса должно
    осуществляться любое взаимодействие с объектами пользователей. Так же объект этого класса осуществляет взаимодействие
    с внешним API, удаленно хранящим данные пользователей
    """

    def __init__(
        self,
        user_url: str,
        orders_url: str,
        user_schema,
        user_class,
        session_time: Optional[int] = None,
    ):
        self._user_url: str = user_url
        self._orders_url: str = orders_url
        self._user_schema = user_schema()
        self.__user_class = user_class
        self._content_type: Dict[str, str] = {"Content-Type": "application/json"}
        self._pool: Dict[int:User] = dict()
        self._session_time: Optional[int] = session_time
        self._bot = None

    def get(self, tg_id: int) -> User:
        """
            Метод возвращает объект пользователя из пула пользователей по-указанному id. Если такового там нет,
        метод попытается получить информацию о покупателе из внешнего API и из локальной базы данных. Если и там
        информации о покупателе нет - будет создан и возвращен новый объект пользователя
        """
        user = self._pool.get(tg_id, None)

        if not user:
            user = self._api_get(tg_id)
            self._pool[tg_id] = user

        if not user:
            user = self.__user_class(tg_id, self._orders_url)
            self._pool[tg_id] = user

        user.update_activity_time()

        return user

    def _api_get(
        self, tg_id: int, get_user_object: bool = True
    ) -> Union[Optional[User], Optional[Dict[str, Any]]]:
        """
            Метод реализует получение данных пользователя от внешнего API. Если аргумент get_user_object = True,
        метод вернет объект пользователя, если False - словарь с данными пользователя
        """
        try:
            response = requests.get(
                "/".join([self._user_url, str(tg_id)]), headers=self._content_type
            )
            if response.status_code == 200:
                data = json.loads(response.text)

                if not get_user_object:
                    return data

                data["orders_url"] = self._orders_url
                user = self._user_schema.loads(json.dumps(data), unknown="exclude")
                user.registered_on_server = True
                return user

            dev_log.info(
                f"Не удалось получить от сервера данные пользователя {tg_id}. Статус код {response.status_code}"
            )

        except Exception as ex:
            dev_log.exception(
                "При попытке получить от сервера данные пользователя {} произошла ошибка:".format(
                    tg_id
                ),
                exc_info=ex,
            )

    def _api_put(self, user: User) -> Optional[bool]:
        """Метод осуществляет сохранение измененных данных пользователя на внешнем сервере"""
        try:
            data = self._user_schema.dumps(user)
            response = requests.put(
                self._user_url, data=data, headers=self._content_type
            )
            if response.status_code == 200:
                dev_log.debug(
                    f"Данные пользователя {user.tgId} успешно обновлены на сервере"
                )
                return True

        except Exception as ex:
            dev_log.exception(
                f"Не удалось обновить данные пользователя {user.tgId} из-за ошибки:",
                exc_info=ex,
            )

    def _api_post(self, user: User) -> Optional[bool]:
        """Метод осуществляет добавление нового пользователя на внешний сервер"""
        try:
            data = self._user_schema.dumps(user)
            response = requests.post(
                self._user_url, data=data, headers=self._content_type
            )
            if response.status_code == 200:
                dev_log.debug(
                    f"Данные нового пользователя {user.tgId} успешно добавлены на сервер"
                )
                return True

        except Exception as ex:
            dev_log.exception(
                f"Не удалось добавить данные нового пользователя {user.tgId} из-за ошибки:",
                exc_info=ex,
            )

    def add_bot(self, bot) -> None:
        """
            Метод принимает на вход объект телеграмм бота и присваивает его атрибуту self._bot. В пуле пользователей
        объект телеграмм бота используется в методе __save_shoppers_data для отправки сообщения пользователю о
        завершении сессии, поэтому у передаваемого объекта бота должен быть реализован метод close_session
        """
        self._bot = bot

    def _save_user_data(self, list_user: List[User]) -> None:
        """
            Данный метод является вспомогательным и используется в методе data_control. Для каждого пользователя в
        переданном списке этот метод отправляет сообщение об окончании сессии при помощи телеграмм бота, сохраняет
        данные пользователя в локальную базу данных, и, если пользователя был зарегистрирован во внешнем API и были
        изменены его данные - отправляет эти изменения на сервер. Если покупатель не был зарегистрирован на сервере -
        делается пост запрос с его данными на сервер.
        """
        for i_user in list_user:
            if self._bot:
                self._bot.close_session(i_user.tgId)

            i_user.saving_to_local_db()

            result = False
            if i_user.registered_on_server and i_user.is_changed():
                result = self._api_put(i_user)

            elif not i_user.registered_on_server and not i_user.is_changed():
                result = self._api_post(i_user)

            elif not i_user.registered_on_server and i_user.is_changed():
                result = self._api_post(i_user)
                if not result:
                    restore_data = self.__restoring_original_data(i_user)
                    if restore_data:
                        result = self._api_put(i_user)

            if result:
                i_user.update_personal_data_cache()
                i_user.registered_on_server = True

    def __restoring_original_data(self, user) -> bool:
        """
            Данный метод предназначен для получения данных зарегистрированного пользователя с сервера в случаях, когда
        пользователь из-за перебоев с сетью был помечен ботом как незарегистрированный пользователь
        """
        old_user_data: Dict[str, Any] = self._api_get(
            tg_id=user.tgId, get_user_object=False
        )
        if old_user_data:
            for i_attr_name, i_val in old_user_data.items():
                if not getattr(user, i_attr_name, None):
                    setattr(user, i_attr_name, i_val)
            return True

    @execute_in_new_thread(daemon=True)
    def data_control(
        self,
        *,
        test_step: Optional[int] = None,
        test_session_time: Optional[int] = None,
    ) -> None:
        """
            Этот метод - бесконечный цикл выполняемый в отдельном потоке - служит для контроля востребованности данных
        пользователей. Если в пуле пользователей есть объекты, взаимодействие с которыми не осуществлялось установленное
        время - они будут удалены из оперативной памяти.
        """
        # Код для тестирования:
        if test_session_time:
            self._session_time = test_session_time

        time_delta = timedelta(seconds=self._session_time)

        while self._session_time:
            time.sleep(self._session_time // 2)

            list_user_to_delete = list(
                filter(
                    lambda i_user: datetime.now(moscow_tz) - i_user.last_session
                    > time_delta,
                    self._pool.values(),
                )
            )

            try:
                self._save_user_data(list_user_to_delete)
                self._delete_user_notifications(list_user_to_delete)

            except Exception as ex:
                dev_log.exception(
                    "При обработке данных пользователей произошла ошибка:", exc_info=ex
                )

            new_pool = {
                i_id: i_user
                for i_id, i_user in self._pool.items()
                if i_user not in list_user_to_delete or i_user.is_changed()
            }

            with Semaphore():
                initial_pool_size = sys.getsizeof(self._pool)
                self._pool = new_pool
                final_size_pool = sys.getsizeof(self._pool)

            dev_log.debug(
                "Размер пула покупателей до/после очищения: {}/{}".format(
                    initial_pool_size, final_size_pool
                )
            )
            new_pool = None

            # Код для выполнения пошаговых тестов
            if isinstance(test_step, int):
                if test_step <= 0:
                    break
                test_step -= 1

        dev_log.warning("Метод data_control завершил свое выполнение!")

    def is_active(self, tg_id) -> bool:
        """
            Метод для проверки - является ли пользователь активным. Метод проверяет, зарегистрирован ли какой-либо
        объект пользователя в пуле пользователей по указанному id
        """
        return tg_id in self._pool.keys()

    def _delete_user_notifications(self, user_list) -> None:
        """Метод предназначен для удаления уведомлений в чатах пользователей, список которых был передан на вход метода"""
        if self._bot:
            for i_user in user_list:
                i_user: User
                for i_notification_id in i_user.get_notification_id(delete=True):
                    self._bot.delete_message(i_user.tgId, i_notification_id)

    @classmethod
    def add_notification_id(cls, user_id, notification_id) -> None:
        """Метод предназначен для сохранения в локальной базе данных id отправленного пользователю уведомления"""
        new_notification = NotificationTable(
            user_id=user_id, notification_id=notification_id
        )
        try:
            session.add(new_notification)
            session.commit()

        except Exception as ex:
            dev_log.exception(
                f"Не удалось добавить в базу данных id {notification_id} "
                f"уведомления пользователя {user_id}",
                exc_info=ex,
            )
            session.rollback()

    def get_pool_size(self):
        """Метод возвращает размер пула (количество элементов в пуле"""
        return len(self._pool.keys())
