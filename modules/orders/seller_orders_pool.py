from typing import List, Optional, Dict
import requests
import json
from multiprocessing.pool import ThreadPool
from datetime import datetime

from .orders import OrderSchema, Order
from ..logger import get_development_logger
from ..utils import timer


dev_log = get_development_logger(__name__)


class SellerOrdersPool:
    def __init__(self, tgId: int, orders_url: str, product_url: str):
        self.__tgId: int = tgId
        self.__url_order: str = orders_url
        self.__product_url: str = product_url
        self.__order_schema = OrderSchema()
        self.__content_type: Dict[str, str] = {'Content-Type': 'application/json'}
        self.new: Optional[List[Order]] = None
        self.current: Optional[List[Order]] = None
        self.completed: Optional[List[Order]] = None

        self.__get_orders()

    @timer
    def __api_get_orders(self, status: str, start: int = 1, stop: int = 100) -> List[Order]:
        """Метод получает от внешнего API список заказов по указанному статусу"""
        try:
            response = requests.get('/'.join([self.__url_order, status, str(start), str(stop)]),
                                    headers=self.__content_type)

            if response.status_code == 200:
                data = json.loads(response.text)
                for i_dict in data:
                    i_dict['order_url'] = self.__url_order
                    i_dict['product_url'] = self.__product_url
                    i_dict['registered_on_server'] = True

                    for j_dict in i_dict.get('products', {}):
                        j_dict['product_url'] = self.__product_url

                return self.__order_schema.loads(json.dumps(data), many=True)

            dev_log.info(f'Не удалось получить {status} заказы - статус код {response.status_code}')
            return []

        except Exception as ex:
            dev_log.exception(f'Не удалось получить список {status} заказов из-за ошибки:',
                              exc_info=ex)

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



