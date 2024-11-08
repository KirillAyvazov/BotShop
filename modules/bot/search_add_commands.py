"""
    Данный модуль содержит объект - пул команд бота - который позволяет удобно подключать команды боту из кода
приложения
"""

from dataclasses import dataclass
from typing import List

from telebot.types import BotCommand

from .bot_shop import BotShop


@dataclass
class Command:
    name: str
    description: str
    priority: int


class CommandPool:
    """
        Данный класс - модель пула команд бота, который позволяет собрать команды из файлов обработчиков, отсортировать
    их в порядке приоритета и подключить к боту.
    """

    def __init__(self, bot: BotShop):
        self.__bot: BotShop = bot
        self.__pool: List[Command] = list()

    def add_command(self, command: Command) -> None:
        """Данный метод добавляет переданную команду в пул команд"""
        self.__pool.append(command)

    def connect_commands(self) -> None:
        """Данный метод фильтрует команды из пула команд по их приоритету и присваивает их боту"""
        self.__pool.sort(key=lambda i_command: i_command.priority)
        self.__bot.set_my_commands(
            [
                BotCommand(i_command.name, i_command.description)
                for i_command in self.__pool
            ]
        )
