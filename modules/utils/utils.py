"""
    Данный модуль содержит вспомогательные функции, используемые в других модулях проекта и решающие
узко-направленные задачи
"""
from typing import Callable, Optional, Any, Union, List, Tuple, Dict
import functools
from threading import Thread, Semaphore
from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from sys import getsizeof

from ..logger import get_development_logger


dev_log = get_development_logger(__name__)


def execute_in_new_thread(_func: Optional[Callable] = None, *, daemon: bool = False) -> Callable:
    """
        Функция - декоратор, которая запускает выполнение переданной в неё функции в отдельном потоке. Следует обратить
    внимание на то, что выполняемая в отдельном потоке функция не должна возвращать никаких результатов своей работы
    """
    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        def wrapped(*args, **kwargs) -> None:
            thread = Thread(target=func, args=args, kwargs=kwargs, daemon=daemon)
            thread = thread.start()
        return wrapped

    if _func is None:
        return decorator
    return decorator(_func)


class ProjectCache:
    """
        Класс - модель кэша данных. Позволяет сохранять полученную от API информацию, которая может быть
    переиспользована некоторое время. Используется в качестве декоратора.
    """
    def __init__(self):
        self.__memory = dict()

    @dataclass
    class Data:
        result: Any
        saving_time: datetime

    def __call__(self, func: Callable) -> Callable:
        self.__data_control()

        @functools.wraps(func)
        def wrapped(*args, **kwargs) -> Any:
            key = ''.join([func.__name__,
                           *[str(i_arg) for i_arg in args if isinstance(i_arg, Union[str, int, List, Tuple, Dict, float])],
                           *kwargs.keys()])
            data = self.__memory.get(key, None)

            if data is None:
                data = self.Data(func(*args, **kwargs), datetime.now())
                if not data.result is None:
                    self.__memory[key] = data

            return data.result

        return wrapped

    @execute_in_new_thread(daemon=True)
    def __data_control(self) -> None:
        """
            Метод осуществляет контроль "свежести" данных в кэше. Если данные хранятся в кэше больше установленного
        времени - они удаляются.
        """
        while True:
            time.sleep(3600)

            start_size = getsizeof(self.__memory)

            for i_key, i_data in list(self.__memory.items()):
                if datetime.now() - i_data.saving_time > timedelta(seconds=43200):
                    with Semaphore():
                        self.__memory.pop(i_key)

            new_size = getsizeof(self.__memory)
            dev_log.debug(f"Размер кэша {self.__name__} до/после очистки: {start_size}/{new_size}")


def timer(func: Callable) -> Optional[Any]:
    """Декоратор - таймер. Отображает время выполнения декорируемой функции"""
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        time_start = time.time()
        result = func(*args, **kwargs)
        print(f"Время выполнения функции {func.__name__} - {round(time.time()-time_start, 3)}")
        return result
    return wrapped
