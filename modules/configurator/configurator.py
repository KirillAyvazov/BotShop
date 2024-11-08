"""
    Данный модуль содержит реализацию сущности - конфигуратора, сущности, которая читает, сохраняет и передает другим
объектам программы параметры, указанные в конфигурационном файле config. Так же, данный объект осуществляет контроль
наличия необходимых для работы проекта путей и файлов. Некоторые пути определены по умолчанию, они необходимы для работы
самой библиотеки, так, например, проверяется наличие файла config. Так же необходимые пути для контроля можно задать
на старте проекта, при инициализации объекта конфигуратора. Если указанный путь не найден - можно указать параметр
create, при наличии которого путь будет создан
"""

import os
import yaml
import dotenv
from typing import Dict, Any, Union
from dataclasses import dataclass

from ..utils import singleton


dotenv.load_dotenv()


@dataclass
class SubConfigurator:
    """Вспомогательный класс, используемый для хранения параметров настроек в классе-конфигураторе"""

    pass


class Configurator:
    """
    Класс реализующий контроль наличия параметров проекта, их загрузку и их передачу целевым исполнителям
    """

    def __init__(self):
        self.__config_control()
        self.__read_config()

    @classmethod
    def __config_control(cls) -> None:
        """Метод осуществляет контроль наличия в проекте файла config на первом уровне вложенности"""
        if not os.path.exists("config.yaml"):
            raise FileNotFoundError(
                "В проекте отсутствует файл config.yaml или он имеет более глубокий уровень "
                "вложенности"
            )

    @classmethod
    def path_control(cls, path: str, create: bool = False) -> None:
        """
            Метод проверяет существование в директории проекта переданного в него пути и, если параметр create = True
        создает его. Если указанный путь отсутствует и create = False - будет выброшено исключение FileNotFoundError
        """
        if not os.path.exists(path):
            if create:
                os.makedirs(path)
            else:
                raise FileNotFoundError("В проекте отсутствует путь {}".format(path))

    def __read_config(self) -> None:
        """
            Метод предназначен для чтения данных из файла config.yaml. Так же данный метод вызывает метод присвоения
        прочтенных из файла-конфигурации параметров
        """
        with open("config.yaml", "r") as config_file:
            data: Dict[str, Any] = yaml.safe_load(config_file)
        self.__save_config(self, data)

    @classmethod
    def __save_config(
        cls, obj: Union["Configurator", SubConfigurator], data: Dict[str, Any]
    ) -> Union["Configurator", SubConfigurator]:
        """
            Метод осуществляет присвоение объекту конфигуратора атрибутов, прочтенных из файла config.yaml. Это
        реализовано с применением рекурсии.
        """
        for i_key, i_val in data.items():
            if i_key == "env":
                for i_env_key, i_env_val in i_val.items():
                    setattr(obj, i_env_key, os.getenv(i_env_val))

            elif not isinstance(i_val, dict):
                setattr(obj, i_key, i_val)

            else:
                sub_configurator = SubConfigurator()
                result = cls.__save_config(sub_configurator, i_val)
                setattr(obj, i_key, result)

        return obj
