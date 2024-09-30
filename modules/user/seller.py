"""
    Данный модуль содержит реализацию класса Продавец, сущность, при помощи которой телеграмм бот оперирует с данными
пользователя являющегося потребителем и обработчиком заказов на приобретение товаров. Класс покупатель является
дочерним для класса User.
"""
from typing import Optional, List
import time
from marshmallow import post_load

from .user import User, UserPool, UserSchema
from ..orders import SellerOrdersPool, Order
from ..utils import execute_in_new_thread


class Seller(User):
    """
        Класс - модель продавца - является сущностью предназначенной для хранения, получения и преобразования данных
    пользователей необходимых для обработки заказов
    """
    def __init__(self,
                 tgId: int,
                 orders_url: str,
                 firstName: Optional[str] = None,
                 lastName: Optional[str] = None,
                 nickname: Optional[str] = None,
                 phoneNumber: Optional[str] = None,
                 ):
        super().__init__(tgId, orders_url, firstName, lastName, nickname, phoneNumber)
        self.orders: Optional[SellerOrdersPool] = None
        self.__personal_data_cache = self.__get_personal_data_cache()

        self.__get_active_orders()

    @execute_in_new_thread
    def __get_active_orders(self) -> None:
        """Этот метод служит для инициализации объекта хранящего заказы и выполняется в отдельном потоке"""
        self.orders = SellerOrdersPool(self.tgId, self.orders_url)

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

    def __repr__(self) -> str:
        """
            Метод возвращает строку, содержащую основные данные продавца: имя, телефон, адрес при применении к объекту
        покупателя метода str
        """
        text, name = [], None
        if self.nickname:
            name = self.nickname
        elif self.firstName :
            name = ' '.join([self.firstName, self.lastName])
        if name:
            text.append('<b>Имя:</b> {}'.format(name))

        if self.phoneNumber:
            text.append('<b>Номер телефона:</b> {}'.format(self.phoneNumber))

        return '\n'.join(text)

    def __get_personal_data_cache(self) -> int:
        """
            Метод отсеивает из персональных данных продавца значения None и из оставшихся значений вычисляет хэш.
        Это вспомогательный метод. Он необходим для определения - были ли изменены персональные данные продавца.
        Применяется в функции is_changed
        """
        list_personal_data = [self.firstName, self.lastName, self.nickname, self.phoneNumber]
        list_personal_data = list(filter(lambda i_elem: not i_elem is None, list_personal_data))
        list_personal_data = list(map(str, list_personal_data))
        return hash(''.join(list_personal_data))

    def is_changed(self) -> bool:
        """Метод проверяет, были ли изменены персональны данные продавца после их получения от внешнего API"""
        return not self.__get_personal_data_cache() == self.__personal_data_cache


class SellerSchema(UserSchema):
    """Класс - схема данных предназначенная для валидации данных продавца получаемых от внешнего API"""
    @post_load
    def create_shopper(self, data, **kwargs) -> Seller:
        seller = Seller(**data)
        seller.registered_on_server = True
        return seller


class SellerPool(UserPool):
    """
        Этот класс предназначен для хранения коллекции продавцов в одном месте, предоставления быстрого доступа к
    любому объекту продавца, а так же для контроля актуальности данных продавцов. Через объект этого класса должно
    осуществляться любое взаимодействие с объектами продавцов. Так же объект этого класса осуществляет взаимодействие
    с внешним API, удаленно хранящим данные продавцов
    """
    def __init__(self, seller_url: str, orders_url: str, session_time: Optional[int] = None):
        super().__init__(seller_url, orders_url, SellerSchema, Seller, session_time)

    def _save_user_data(self, list_seller: List[Seller]) -> None:
        """
            Данный метод является вспомогательным и используется в методе data_control. Для каждого пользователя в
        переданном списке этот метод отправляет сообщение об окончании сессии при помощи телеграмм бота, сохраняет
        данные пользователя в локальную базу данных, и, если пользователя был зарегистрирован во внешнем API и были
        изменены его данные - отправляет эти изменения на сервер. Если покупатель не был зарегистрирован на сервере -
        делается пост запрос с его данными на сервер.
        """
        for i_seller in list_seller:
            if self._bot:
                self._bot.close_session(i_seller.tgId)

            i_seller.saving_to_local_db()

            if i_seller.is_changed() and i_seller.registered_on_server:
                self._api_put(i_seller)
            elif not i_seller.registered_on_server:
                self._api_post(i_seller)

























