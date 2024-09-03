"""
    Данный модуль содержит реализацию класса BotShop - основной сущности проекта, при помощи которой осуществляется
взаимодействие с пользователем телеграмм, данными пользователей и каталогом товаров. Данный класс является дочерним для
класса TeleBot библиотеки telebot и наследует его основной функционал, а так же переопределяет и определяет с нуля
некоторые методы
"""

from telebot import TeleBot
from telebot.types import Message, InputMediaPhoto
from telebot.apihelper import ApiTelegramException
from typing import Callable, List, Optional
import functools

from ..logger import get_development_logger
from .message_deletion_blocker import MessageDeletionBlocker


dev_log = get_development_logger(__name__)


class BotShop(TeleBot):
    """
        Класс является моделью бата - основной сущностью используемой в проекте, чрез которую реализуется основной
    функционал приложения. Представляет собой дочерний класс от TeleBot с расширенным функционалом. Расширение
    функционал основного класса осуществляется путём добавления новых атрибутов класса и изменения работы методов
    оригинального класса.
    """

    def __init__(self,
                 token: str,
                 disappearing_messages: bool = True,
                 message_limit: int = 1):
        super().__init__(token)
        self.user_pool = None
        self.disappearing_messages: bool = disappearing_messages
        self.message_limit: int = message_limit

    def __delete_old_message(self, message: Message, obj: str) -> None:
        """
            Вспомогательный метод. Получает на вход id сообщения отправленного ботом или пользователем, добавляет его в
        хранилище пользователя, после чего получает от туда другой список id сообщений - которые нужно удалить как
        превышающие лимит сообщений - и удаляет их
        """
        if self.user_pool:
            user = self.user_pool.get(message.chat.id)
            user.append_message(message.id, obj)
            user.update_activity_time()

            for i_message_id in user.pop_message(obj, message_limit=self.message_limit):
                try:
                    self.delete_message(message.chat.id, i_message_id)

                except ApiTelegramException as ex:
                    dev_log.exception('Не удалось удалить сообщение бота в чате пользователя {}'.format(message.chat.id),
                                         exc_info=ex)

    def send_message(self, *args, **kwargs) -> Message:
        """
            Метод изменяет функционал оригинального метода родительского класса для отправки сообщений: если атрибут
        бота disappearing_messages = True, то отправленное пользователю сообщение регистрируется в хранилище данных
        пользователя. Если количество отправленных ботом сообщений будет превышать установленный лимит message_limit -
        более ранние сообщения, превышающие лимит, будут удалены.
        """
        message: Message = super().send_message(*args, **kwargs, parse_mode = "HTML")

        if self.disappearing_messages:
            self.__delete_old_message(message, 'bot')

        return message

    def add_user_pool(self, user_pool) -> None:
        """
            Данный метод получает на вход объект - пул пользователей (пул покупателей или продавцов) и присваивает его
        атрибуту __user_pool. Это позволяет боту получать данные пользователей для своих нужд, например для получения
        id сообщений которые нужно удалить.
        """
        self.user_pool = user_pool

    def registration_incoming_message(self, func: Callable) -> Callable:
        """
            Декоратор функций-обработчиков сообщений, который позволяет удалять из чата старые сообщения пользователей
        если в файле конфигурации включена настройка disappearing_messages и количество отправленных пользователем
        сообщений будет превышать установленный в настройках лимит message_limit. Удалены будут более поздние сообщения,
        превышающие лимит.
        """
        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            result = func(*args, **kwargs)

            if self.user_pool and self.disappearing_messages:
                message_list = list(filter(lambda i_object: isinstance(i_object, Message), args))

                if len(message_list) <= 0:
                    message_list = list(filter(lambda i_object: isinstance(i_object, Message), kwargs.values()))

                if len(message_list) > 0:
                    self.__delete_old_message(message_list[0], 'user')

            return result
        return wrapped_func

    def close_session(self, user_id: int) -> None:
        """
            Данный метод служит для закрытия сессии пользователя.
            Контекст: при удалении данных пользователя из оперативной памяти хоста, по истечению времени их хранения,
        в чате пользователя может сохраниться диалог, в котором пользователь вводил какие-либо данные, но еще не
        отправил их на сервер. Через некоторое время пользователь может попытаться отправить данные, но они уже будут
        удалены.
            Для исключения такой ситуации предназначен этот метод. Метод отправляет в чат пользователю информационное
        сообщение-заглушку, тем самым делая предыдущее сообщение-форму для отправки данных не актуальной. Так же метод
        сбрасывает любое состояние пользователя.
        """
        text = "Всего хорошего! Возвращайтесь к нам скорее!"
        self.send_message(user_id, text)
        self.delete_state(user_id)

    def send_product(self, chat_id: int, product, text_message: Optional[str] = None, keyboard = None) -> Message:
        """
            Метод предназначен для отправки пользователю информации о товаре - все имеющиеся изображения и описание,
        а так же клавиатуру для управления карточкой товара. На вход метод принимает id пользователя, объект - продукт,
        из соответствующего модуля и клавиатуру которую необходимо отправить
        """
        with MessageDeletionBlocker(self) as register:
            msg_list: List[Message] = self.send_media_group(chat_id, product.image, disable_notification=True)

            text = str(product)
            if text_message:
                text = '\n\n'.join([text_message, text])

            msg_caption = self.send_message(chat_id, text=text, reply_markup=keyboard, disable_notification=True)

            register(*msg_list, msg_caption)

        if not isinstance(product.image[0].media, str):
            product.image = [InputMediaPhoto(i_message.photo[len(i_message.photo) - 1].file_id)
                             for i_message in msg_list]

    def notify_user(self, user_id: int, message: str) -> None:
        """Метод отправляет пользователю уведомление с заданным текстом"""
        with MessageDeletionBlocker(self):
            self.send_message(user_id, message)

    def polling(self, *args, **kwargs) -> None:
        """
            Это измененный метод запуска бота из оригинальной библиотеки с добавлением бесконечного цикла и обработкой
        ошибок
        """
        while True:
            try:
                super().polling(*args, **kwargs)

            except Exception as ex:
                dev_log.exception('Бот упал с ошибкой:', exc_info=ex)
