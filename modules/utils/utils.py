"""
    Данный модуль содержит вспомогательные функции, используемые в других модулях проекта и решающие
узко-направленные задачи
"""
from typing import Callable, Optional, Any
import functools
from threading import Thread
from dataclasses import dataclass
from datetime import datetime, timedelta
import time


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
    __memory = dict()

    @dataclass
    class Data:
        result: Any
        saving_time: datetime = datetime.now()

    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapped(*args, **kwargs) -> Any:
            key = ''.join([*[str(i_arg) for i_arg in args], *kwargs.keys()])
            data = self.__get_data(key)

            if data is None:
                data = self.Data(func(*args, **kwargs))
                self.__memory[key] = data

            return data.result

        return wrapped

    def __get_data(self, key: str) -> Optional[Any]:
        """
            Метод осуществляет получение данных из кэша контроль времени хранения данных. Время хранения данных не
        должно превышать 1 сутки.
        """
        data = self.__memory.get(key, None)

        if data:
            if datetime.now() - data.saving_time < timedelta(days=1):
                return data
            self.__memory.pop(key)


def timer(func: Callable) -> Optional[Any]:
    """Декоратор - таймер. Отображает время выполнения декорируемой функции"""
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        time_start = time.time()
        result = func(*args, **kwargs)
        print(f"Время выполнения функции {func.__name__} - {round(time.time()-time_start, 3)}")
        return result
    return wrapped
