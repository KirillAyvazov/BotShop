from typing import Optional

from telebot.apihelper import ApiTelegramException

from ..logger import get_development_logger

dev_log = get_development_logger(__name__)


class MessageDeletionBlocker:
    """
        Класс - контекстный менеджер, который позволяет временно заблокировать удаление сообщений из чата и
    отправить пользователю группу сообщений от бота.
        Для того что бы при включенной настройке исчезающих сообщений (в файле bot_config
    disappearing_messages: bool = True) можно было отправить группу сообщений, вызываем класс MessageDeletionBlocker
    в контекстном менеджере, например "with MessageDeletionBlocker() as register:". Далее выполняем
    отправку сообщений ботом необходимое количество раз в блоке with.
        Для того что бы после закрытия блока with группа отправленных сообщений была удалена последующим сообщением,
    передаём их в объект register, например так: "register(mes1, mes2, mes3).
        Параметр delete_old_message объекта register по умолчанию имеет значение True и отвечает за удаление старых
    сообщений, отправленных до нового блока сообщений.

    """

    __disappearing_messages_default: Optional[bool] = None

    def __init__(self, bot):
        self.bot = bot

    def __enter__(self):
        """
            Метод позволяет вызвать класс в качестве контекстного менеджера. Данный метод преобразует значение
        глобальной переменной disappearing_messages в значение False, сохраняя в памяти его предыдущее значение.
        Метод возвращает объект класса MessageDeletionBlocker, который в рамках контекстного менеджера может быть
        использован для регистрации сообщений отправленных в блоке.

        """
        self.__disappearing_messages_default = self.bot.disappearing_messages
        self.bot.disappearing_messages = False
        return self

    def __call__(self, *args, delete_old_message: bool = True) -> None:
        """
            Метод позволяет объекту класса быть вызываемым объектом. Принимает в себя объекты telebot.types.Message
        в неограниченном количестве, регистрирует их и удаляет старые сообщения, сделанные до вызова блока новых
        сообщений.
        """
        if self.__disappearing_messages_default:

            if len(args) > 0:
                message = args[0]
                user = self.bot.user_pool.get(message.chat.id)
                user.append_message(message.id, "bot")

                if delete_old_message:
                    for i_message_id in user.pop_message("bot", self.bot.message_limit):
                        try:
                            self.bot.delete_message(message.chat.id, i_message_id)
                        except ApiTelegramException as ex:
                            dev_log.exception(
                                f"Не удалось удалить сообщение бота в чате {message.chat.id}"
                            )

                for i_message in args[1:]:
                    user.append_message(i_message.id, "bot")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
            Метод закрытия контекстного менеджера. Преобразует значение атрибута бота disappearing_messages,
        возвращая ему исходное значение, которое было установлено до вызова контекстного менеджера
        """
        self.bot.disappearing_messages = self.__disappearing_messages_default
