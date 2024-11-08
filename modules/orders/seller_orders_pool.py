import json
from multiprocessing.pool import ThreadPool
from typing import Dict, List, Optional

import requests

from ..logger import get_development_logger
from ..utils import timer
from .orders import Order, OrderSchema

dev_log = get_development_logger(__name__)


class SellerOrdersPool:
    def __init__(self, tgId: int, orders_url: str):
        self.__tgId: int = tgId
        self.__url_order: str = orders_url
        self.__order_schema = OrderSchema()
        self.__content_type: Dict[str, str] = {"Content-Type": "application/json"}
        self.new: Optional[List[Order]] = None
        self.current: Optional[List[Order]] = None
        self.completed: Optional[List[Order]] = None

        self.__get_orders()

    def __api_get_orders(
        self, status: str, start: int = 1, stop: int = 100
    ) -> List[Order]:
        """Метод получает от внешнего API список заказов по указанному статусу"""
        try:
            response = requests.get(
                "/".join([self.__url_order, status, str(start), str(stop)]),
                headers=self.__content_type,
            )

            if response.status_code == 200:
                data = json.loads(response.text)
                for i_dict in data:
                    i_dict["order_url"] = self.__url_order
                    i_dict["registered_on_server"] = True

                return self.__order_schema.loads(json.dumps(data), many=True)

            dev_log.info(
                f"Не удалось получить {status} заказы - статус код {response.status_code}"
            )
            return []

        except Exception as ex:
            dev_log.exception(
                f"Не удалось получить список {status} заказов из-за ошибки:",
                exc_info=ex,
            )

    def __get_orders(self) -> None:
        """
            Метод предназначен для инициализации получения списков заказов в параллельных потоках и присвоения
        результатов выполнения метода __api_get_orders соответствующим атрибутам объекта
        """
        thread_pool = ThreadPool(2)
        result = thread_pool.map(self.__api_get_orders, ["new", "current"])
        thread_pool.close()
        thread_pool.join()
        self.new = result[0]
        self.current = result[1]

    def move_an_order(self, order: Order) -> None:
        """
            Метод перемещает переданный в него заказ в соответсвующий его статусу список заказов - в новые, в
        действующие или завершенные
        """
        if order.status in [2, 3, 4, 5, 6] and order in self.new:
            self.new.remove(order)
            self.current.append(order)

        elif order.status in [7, 8, 9] and order in self.new:
            self.new.remove(order)

        elif order.status in [7, 8, 9] and order in self.current:
            self.current.remove(order)

        elif order.status == 1 and order in self.current:
            self.current.remove(order)
            self.new.append(order)
