"""
    Данный модуль содержит реализацию класса Продавец, сущность, при помощи которой телеграмм бот оперирует с данными
пользователя являющегося потребителем и обработчиком заказов на приобретение товаров. Класс покупатель является
дочерним для класса User.
"""
from typing import Optional

from .user import User
from ..orders import SellerOrdersPool


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
        super().__init__(tgId, orders_url, product_url)
        self.firstName: Optional[str] = firstName
        self.lastName: Optional[str] = lastName
        self.nickname: Optional[str] = nickname
        self.phoneNumber: Optional[str] = phoneNumber
        self.orders: Optional[SellerOrdersPool] = None

