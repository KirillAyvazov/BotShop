"""
    Данный модуль содержит вспомогательные функции, используемые в других модулях проекта и решающие
узко-направленные задачи
"""
from typing import Callable, Optional
import functools
from threading import Thread


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
