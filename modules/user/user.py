"""
    Данный модуль содержит реализацию базового класса - модели пользователя, который является родительским классом для
класса Продавца и Покупателя. Данный клас содержит общие характеристики и решает общие задачи двух дочерних классов.
    К общим задачам двух классов Продавец и Покупатель можно отнести необходимость хранения в локальной базе данных бота
информации о полученных и переданных пользователем телеграмма сообщениях, а так же время его последней активности. Эти
данные необходимы для реализации исчезающих сообщений и завершения сессии пользователя.
"""

from sqlalchemy import Column, Integer, String, PrimaryKeyConstraint, DateTime, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from typing import List, Literal, Dict, Any, Callable, Optional, Tuple
import os
from queue import Queue, LifoQueue
from telebot.types import Message

from ..logger import get_development_logger
from ..products import Product


dev_log = get_development_logger(__name__)

Base = declarative_base()

if not os.path.exists('database'):
    os.makedirs('database')
engine = create_engine('sqlite:///{}'.format(os.path.join('database', 'user_database.db')))

Session = sessionmaker(bind=engine)
session = Session()

ObjectName = Literal['bot', 'user']


class UserTable(Base):
    """
        Класс - представление таблицы базы данных в которой хранятся данные необходимые для корректной работы класса
    Пользователя
    """
    __tablename__ = 'user'

    tgId = Column(Integer)
    message_id_bot_to_user = Column(String, nullable=False, default='')
    message_id_user_to_bot = Column(String, nullable=False, default='')
    last_session = Column(DateTime, default=datetime.now())

    __table_args__ = (
        PrimaryKeyConstraint('tgId'),
    )


Base.metadata.create_all(engine)


class User:
    """
        Класс - содержащий основные атрибуты и методы необходимые для корректной работы с телеграмм ботом и
    предназначенный для хранения данных пользователя и управления ими.
    """

    def __init__(self, tg_id: int, orders_url: str, product_url: str):
        self.tgId: int = tg_id
        self.orders_url: str = orders_url
        self.product_url: str = product_url
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
        self.back = False

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
            for i_elem in [i_elem for i_elem in user_table.message_id_user_to_bot.split(',')]:
                self.__message_id_user_to_bot.put(i_elem)

            for i_elem in [i_elem for i_elem in user_table.message_id_bot_to_user.split(',')]:
                self.__message_id_bot_to_user.put(i_elem)

            self.last_session = datetime.strptime(str(user_table.last_session), "%Y-%m-%d %H:%M:%S.%f")

        else:
            user_table = UserTable(tgId=self.tgId)
            session.add(user_table)
            try:
                session.commit()
                self.__restore_data_in_local_db()
            except Exception as ex:
                session.rollback()
                dev_log.exception('Не удалось добавить запись о пользователе {} в локальную базу данных'.format(self.tgId),
                                exc_info=ex)

    def __object_control(self, object_name: ObjectName) -> Queue[int]:
        """
            Метод осуществляет контроль соответствия переданной строки возможным значениям литерала ObjectName.
        Если object_name не соответствует ни одному допустимому значению, возбуждается исключение ValueError.
            Если имя сущности == bot, возвращается список d сообщений полученных от бота. Если имя сущности равно
        user - возвращается список id сообщений отправленных пользователем.
            Это вспомогательный метод. Он используется в методах append_message и pop_message
        """
        if object_name == 'bot':
            return self.__message_id_bot_to_user
        elif object_name == 'user':
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
        self.last_session = datetime.now()

    def saving_to_local_db(self) -> None:
        """Метод сохраняет (обновляет) необходимые для корректной работы данные пользователя в локальную базу данных"""
        session.query(UserTable).filter(UserTable.tgId==self.tgId).update(
            {
                "message_id_bot_to_user": ','.join([str(self.__message_id_bot_to_user.get())
                                                    for _ in range(self.__message_id_bot_to_user.qsize())]),
                "message_id_user_to_bot": ','.join([str(self.__message_id_user_to_bot.get())
                                                    for _ in range(self.__message_id_user_to_bot.qsize())]),
                "last_session":  self.last_session
            },
            synchronize_session='fetch'
        )

        try:
            session.commit()

        except Exception as ex:
            session.rollback()
            dev_log.exception('Не удалось сохранить данные пользователя {} в локальную базу данных'.format(self.tgId),
                              exc_info=ex)

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
