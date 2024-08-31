from datetime import datetime
from typing import List, Optional, Dict
import requests
import json
import time

from .orders import OrderSchema, Order, Basket
from ..logger import get_development_logger


dev_log = get_development_logger(__name__)


class ShopperOrdersPool:
    def __init__(self, tgId: int, orders_url: str, product_url: str):
        self.__tgId: int = tgId
        self.__url_order: str = orders_url
        self.__product_url: str = product_url
        self.__order_schema = OrderSchema()
        self.__content_type: Dict[str, str] = {'Content-Type': 'application/json'}
        self.pool: Optional[List[Order]] = self.__api_get_orders()
        self.basket: Optional[Order] = self.__basket_search()

    def __api_get_orders(self) -> List[Order]:
        """Метод получает от внешнего API список заказов"""
        try:
            response = requests.get('/'.join([self.__url_order, str(self.__tgId)]), headers=self.__content_type)

            if response.status_code == 200:
                data = json.loads(response.text)
                for i_dict in data:
                    i_dict['product_url'] = self.__product_url
                return self.__order_schema.loads(json.dumps(data), many=True)

            dev_log.info(f'Не удалось получить заказы пользователя {self.__tgId} - статус код {response.status_code}')
            return []

        except Exception as ex:
            dev_log.exception(f'Не удалось получить список заказов пользователя {self.__tgId} из-за ошибки:',
                              exc_info=ex)

    def __call__(self, *args, **kwargs) -> List[Order]:
        """При обращении к объекту пула заказов как к вызываемому объекту будет возвращен список заказов"""
        return self.pool

    def __basket_search(self) -> Order:
        """Метод осуществляет поиск корзины среди заказов покупателя. Если таковой нет - создает новую корзину"""
        result = list(filter(lambda i_order: i_order.status == 0, self.pool))

        if len(result) > 0:
            order = result[0]
            self.pool.remove(order)
            return Basket(**{i_attr: i_val for i_attr, i_val in order.__dict__.items()})

        return Basket()
