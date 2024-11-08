import json
from datetime import datetime
from typing import Dict, List, Optional

import pytz
import requests

from ..logger import get_development_logger
from ..utils import timer
from .orders import Basket, Order, OrderSchema

dev_log = get_development_logger(__name__)
moscow_tz = pytz.timezone("Europe/Moscow")


class ShopperOrdersPool:
    def __init__(self, tgId: int, orders_url: str):
        self.__tgId: int = tgId
        self.__url_order: str = orders_url
        self.__order_schema = OrderSchema()
        self.__content_type: Dict[str, str] = {"Content-Type": "application/json"}
        self.pool: Optional[List[Order]] = self.__api_get_orders()
        self.basket: Optional[Basket] = self.__basket_search()

    def __api_get_orders(self) -> List[Order]:
        """Метод получает от внешнего API список заказов"""
        try:
            response = requests.get(
                "/".join([self.__url_order, str(self.__tgId)]),
                headers=self.__content_type,
            )

            if response.status_code == 200:
                data = json.loads(response.text)
                for i_dict in data:
                    i_dict["order_url"] = self.__url_order
                    i_dict["registered_on_server"] = True

                return self.__order_schema.loads(json.dumps(data), many=True)

            dev_log.info(
                f"Не удалось получить заказы пользователя {self.__tgId} - статус код {response.status_code}"
            )

        except Exception as ex:
            dev_log.exception(
                f"Не удалось получить список заказов пользователя {self.__tgId} из-за ошибки:",
                exc_info=ex,
            )

        return []

    def __call__(self, *args, **kwargs) -> List[Order]:
        """При обращении к объекту пула заказов как к вызываемому объекту будет возвращен список заказов"""
        return self.pool

    def __basket_search(self) -> Basket:
        """Метод осуществляет поиск корзины среди заказов покупателя. Если таковой нет - создает новую корзину"""
        basket_list = list(
            filter(lambda i_order: isinstance(i_order, Basket), self.pool)
        )

        if len(basket_list) > 0:
            basket = basket_list[0]
            self.pool.remove(basket)

        else:
            basket = Basket(
                tgId=self.__tgId,
                order_url=self.__url_order,
                datetimeCreation=datetime.now(moscow_tz).strftime("%d.%m.%Y %H:%M"),
            )

        return basket

    def create_new_order(self) -> None:
        """
            Метод создаёт новый заказ. Корзину отправляет на сервер в качестве нового заказа, её добавляет в список
        заказов, и создает новую корзину
        """
        self.basket.create_new_order()
        self.pool.append(self.basket)
        self.basket = Basket(
            tgId=self.__tgId,
            order_url=self.__url_order,
            datetimeCreation=datetime.now(moscow_tz).strftime("%d.%m.%Y %H:%M"),
        )
