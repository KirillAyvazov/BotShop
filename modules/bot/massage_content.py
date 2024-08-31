"""
    Данный модуль содержит реализацию класса, позволяющего читать заготовленный текст сообщений из json файла и
предоставлять к нему доступ
"""

import json
from typing import Dict, Any
import os


class MessageContent:
    def __init__(self, path):
        self.__path: str = path
        self.__get_message_content()

    def __search_text_message(self) -> Dict[str, Any]:
        """Метод осуществляет поиск json файлов с текстом сообщений в рабочей директории data модуля"""
        if os.path.exists(self.__path):
            with open(self.__path, 'r') as file:
                return json.loads(file.read())

        raise FileNotFoundError('В проекте отсутствует файл с текстом сообщений - text_message.txt')

    def __get_message_content(self) -> None:
        """Метод заполняет экземпляр класса полями и значениями c текстом сообщений"""
        for i_key, i_val in self.__search_text_message().items():
            setattr(self, i_key, ' '.join(i_val))
