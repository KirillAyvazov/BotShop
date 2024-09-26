"""
    Данный модуль содержит реализацию класса Продавец, сущность, при помощи которой телеграмм бот оперирует с данными
пользователя являющегося потребителем и обработчиком заказов на приобретение товаров. Класс покупатель является
дочерним для класса User.
"""
from typing import Optional, List
import time

from .user import User
from ..orders import SellerOrdersPool, Order


class Seller(User):
    """
        Класс - модель продавца - является сущностью предназначенной для хранения, получения и преобразования данных
    пользователей необходимых для обработки заказов
    """
    def __init__(self,
                 tgId: int,
                 orders_url: str,
                 product_url: str,
                 firstName: Optional[str] = None,
                 lastName: Optional[str] = None,
                 nickname: Optional[str] = None,
                 phoneNumber: Optional[str] = None,
                 ):
        super().__init__(tgId, orders_url, product_url, firstName, lastName, nickname, phoneNumber)
        self.orders: Optional[SellerOrdersPool] = None

    def __get_active_orders(self) -> None:
        """Этот метод служит для инициализации объекта хранящего заказы"""
        self.orders = SellerOrdersPool(self.tgId, self.orders_url, self.product_url)

    def get_new_orders(self) -> List[Order]:
        """Метод возвращает список новых заказов"""
        time_start = time.time()
        while time.time() - time_start < 15:
            if self.orders:
                return self.orders.new

    def get_current_orders(self) -> List[Order]:
        """Метод возвращает список текущих заказов"""
        time_start = time.time()
        while time.time() - time_start < 15:
            if self.orders:
                return self.orders.current
