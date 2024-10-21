"""
    Данный модуль содержит вспомогательные функции, используемые в других модулях проекта и решающие
узко-направленные задачи
"""
from typing import Callable, Optional, Any, Union, List, Tuple, Dict
import functools
from threading import Thread, Semaphore
from dataclasses import dataclass
from datetime import datetime, timedelta
import pytz
import time
from sys import getsizeof

from ..logger import get_development_logger


dev_log = get_development_logger(__name__)
moscow_tz = pytz.timezone("Europe/Moscow")


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


def singleton(cls):
    """
        Функция - декоратор для классов. Она гарантирует, что при любой инициализации объекта класса, всегда будет
    возвращен один и тот же объект класса.
        Метод - декоратор, который инициализирует объект декорируемого класса, если тот еще не был инициализирован.
    Если был - возвращает уже имеющийся объект
    """
    memory: Dict[str: object] = dict()

    @functools.wraps(cls)
    def wrapper(*args, **kwargs):
        obj = memory.get(cls, None)
        if obj is None:
            obj = cls(*args, **kwargs)
            memory[cls] = obj
        return obj
    return wrapper


@singleton
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
                data = self.Data(func(*args, **kwargs), datetime.now(moscow_tz))
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
                if datetime.now(moscow_tz) - i_data.saving_time > timedelta(seconds=43200):
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


@singleton
class DataTunnel:
    """
        Класс - декоратор, предназначенный для того что бы обойти недостатки композиционной архитектуры, принятой в
    этом проекте. Объект класса является декоратором и сохраняет в своей памяти декорируемый метод или функцию. Так же
    он позволяет вызвать сохраненный метод или функцию в другом месте проекта.
        Контекст. Мне нужно обратиться к методу объекта класса CategoryPool из метода класса Order. Варианты:
    либо как-то гарантировать что в файле structure каждый раз при создании проекта будет создаваться объект
    category_pool и прописать логику добавления и передачи этого объекта по цепочке shopper_pool - shopper -
    shopper_orders_pool - order - product_data, либо использовать тоннель данных, который позволит вызвать необходимый
    в order объект category_pool
        Данный метод налагает ограничения на объекты класса - они становятся СИНГЛТОНАМИ!!!
    """
    def __init__(self):
        self.__func_dict: Dict[str, Callable] = dict()

    def add_methods(self, *methods_name) -> Callable:
        """
            Метод - декоратор класса. Предназначен для регистрации методов класса. В качестве аргументов принимает
        названия методов которые должны быть зарегистрированы
        """
        def decorator(cls) -> Callable:
            @functools.wraps(cls)
            def wrapped(*args, **kwargs) -> object:
                nonlocal cls
                cls = singleton(cls)
                cls_obj = cls(*args, **kwargs)
                methods = {".".join([cls.__name__, i_name_methods]): getattr(cls_obj, i_name_methods, None)
                           for i_name_methods in methods_name}
                self.__func_dict.update(methods)
                return cls_obj
            return wrapped
        return decorator

    def add_func(self, func: Callable) -> Callable:
        """Метод - декоратор. Сохраняет декорируемую функцию в памяти тоннеля"""
        if func.__name__ in self.__func_dict:
            raise ValueError("Функция с именем {} уже зарегистрирована в тоннеле данных".format(func.__name__))

        self.__func_dict[func.__name__] = func
        return func

    def perform(self, func_name: str, *args, **kwargs) -> Optional[Any]:
        """Метод выполнения зарегистрированного метода или функции, с переданным названием и аргументами"""
        func = self.__func_dict.get(func_name, None)
        if func:
            return func(*args, **kwargs)

        raise ValueError("Функция с именем {} НЕ зарегистрирована в тоннеле данных".format(func_name))
