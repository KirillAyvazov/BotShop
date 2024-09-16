"""
    Данный модуль содержит реализацию модели заказа пользователей и реализацию объекта - пула заказа, объекта при
помощи которого осуществляется хранение, доступ и редактирование заказов пользователя.
"""
from marshmallow import Schema, fields, post_load, validate
from typing import Optional, List, Dict, Any, Union
import requests
from marshmallow.fields import Field
import json
from copy import deepcopy
from datetime import datetime

from ..products import Product, ProductSchema
from ..logger import get_development_logger


dev_log = get_development_logger(__name__)


class ProductData:
    """
        Это вспомогательный класс, при помощи которого осуществляется получение полной информации от стороннего API
    о продукте из заказа и осуществляется создание его объекта. Данный класс не предназначен для использования вне
    данного модуля.
    """
    def __init__(self, productsId: str, count: int, product_url: str):
        self.productsId: str = productsId
        self.count: int = count
        self.__product_url: str = product_url
        self.__content_type: Dict[str, str] = {'Content-Type': 'application/json'}
        self.__product_schema = ProductSchema()
        self.product: Product = self.__api_get_product()

    def __api_get_product(self) -> Product:
        """Данный метод осуществляет запрос к внешнему API для получения информации о товаре по указанному id товара"""
        try:
            response = requests.get('/'.join([self.__product_url, self.productsId]), headers=self.__content_type)

            if response.status_code == 200:
                product: Product = self.__product_schema.loads(response.text)
                product.count = self.count
                return product

            dev_log.debug(f'Не удалось получить данные о товаре {self.productsId} при загрузке заказа: статус код '
                          f'{response.status_code}')

        except Exception as ex:
            dev_log.exception(f'При попытке получить данные товара {self.productsId} произошла ошибка:', exc_info=ex)


class ProductDataSchema(Schema):
    """
        Класс - модель данных json получаемого от внешнего API при запросе продукта. Служит для валидации, сериализации
    и десериализации данных
    """
    productsId = fields.Str(required=True, allow_none=False)
    count = fields.Integer(required=True, allow_none=False)
    product_url = fields.Str(required=True, allow_none=False, load_only=True)

    @post_load
    def create_product_data(self, data, **kwargs) -> ProductData:
        """Метод позволяет возвратить после загрузки данных объект - товар"""
        return ProductData(**data)


class Order:
    """Модель заказа"""
    def __init__(self,
        tgId: Optional[int] = None,
        status: int = 0,
        idOrder: Optional[int] = None,
        datetimeCreation: Optional[str] = datetime.now().strftime("%d-%m-%Y %H:%M"),
        totalCost: Optional[int] = 0,
        delivery: bool = False,
        products: Union[str, List[Product]] = list(),
        datetimeUpdate: Optional[str] = None,
        userComment: Optional[str] = None,
        sellerComment: Optional[str] = None,
        completionDate: Optional[str] = None,
        source: Optional[str] = None,
        product_url: Optional[str] = None,
        order_url: Optional[str] = None,
        registered_on_server: bool = False
        ):
        self.tgId = tgId
        self.idOrder = idOrder
        self.status: int = status
        self.datetimeCreation: str = datetimeCreation
        self.totalCost: int = totalCost
        self.delivery: bool = delivery
        self.products: List[Product] = products
        self.datetimeUpdate: Optional[str] = datetimeUpdate
        self.userComment: Optional[str] = userComment
        self.sellerComment: Optional[str] = sellerComment
        self.completionDate: Optional[str] = completionDate
        self.source: Optional[str] = source

        self._product_data_schema = ProductDataSchema()
        self._order_schema = OrderSchema()
        self._content_type: Dict[str, str] = {'Content-Type': 'application/json'}
        self._order_url: str = order_url
        self._product_url: str = product_url

        self._registered_on_server: bool = registered_on_server
        self._control_hash: int = self.__get_hash_sum()

        self.__get_product_obj()

    def __get_product_obj(self) -> None:
        """Метод преобразует полученные данные о товарах в список объектов - товаров"""
        self.products: List[Product] = [i_product_data.product for i_product_data in self.products]

    def __api_post(self):
        """Метод передачи данных о заказе на сервер"""
        try:
            data = self._order_schema.dumps(self)
            response = requests.post(self._order_url, headers=self._content_type, data=data)

            if response.status_code == 200:
                dev_log.debug(f'Данные заказа №{self.idOrder} успешно переданы на сервер')
            else:
                dev_log.warning(f'Не удалось передать заказ №{self.idOrder} на сервер. Статус код {response.status_code}')

        except Exception as ex:
            dev_log.exception(f'При попытке передать заказ №{self.idOrder} произошла ошибка:', exc_info=ex)

    def __api_put(self):
        """Метод обновления данных о заказе на сервер"""
        try:
            data = self._order_schema.dumps(self)
            response = requests.put(self._order_url, headers=self._content_type, data=data)

            if response.status_code == 200:
                dev_log.debug(f'Данные заказа №{self.idOrder} успешно обновлены на сервере')
            else:
                dev_log.warning(f'Не удалось обновить заказ №{self.idOrder} на сервере. Статус код {response.status_code}')

        except Exception as ex:
            dev_log.exception(f'При попытке обновить заказ №{self.idOrder} произошла ошибка:', exc_info=ex)

    def save_on_server(self):
        """Метод сохраняет данные о заказе на сервере, если это необходимо (заказ новый или был изменен"""
        if not self._registered_on_server:
            self.__api_post()
        elif self.__is_updated():
            self.__api_put()

    def __get_hash_sum(self) -> int:
        """Этот метод возвращает хэш сумму всех полей объекта которые хранятся на сервере"""
        order_srt = ''.join([str(i_val) for i_name, i_val in self.__dict__.items() if not i_name.startswith('_')])
        order_products = ''.join([''.join([str(i_product), str(i_product.count)]) for i_product in self.products])
        order_srt = ''.join([order_srt, order_products])

        return hash(order_srt)

    def __is_updated(self) -> bool:
        """Если заказ был обновлен - метод вернет True"""
        return not self.__get_hash_sum() == self._control_hash

    def __repr__(self) -> str:
        """Метод выводит информацию о заказе при обращении к объекту заказа как к строчному объекту"""
        text = list()
        text.append('<b>Заказ №{}</b>'.format(str(self.idOrder)))
        text.append('Статус: {}'.format(self.get_order_status()))
        text.append('Заказ создан: {}'.format(self.datetimeCreation))
        text.append('Заказ обновлен {}'.format(self.datetimeUpdate))

        if self.completionDate:
            text.append('Запланированная дата завершения заказа: {}'.format(self.completionDate))

        text.append('Стоимость заказа: {}'.format(str(self.totalCost)))

        if self.delivery:
            text.append('Способ получения: доставка')
        else:
            text.append('Способ получения: самовывоз')

        if self.userComment:
            text.append('Комментарий заказчика: {}'.format(self.userComment))

        if self.sellerСomment:
            text.append('Комментарий продавца: {}'.format(self.sellerСomment))

        text.append('Товары:')
        for index, i_product in enumerate(self.products):
            i_product: Product
            text.append('{num}. {category_name}: {prod_name} - {count} шт. = {sum} рублей'.format(num=index+1,
                        category_name=i_product.category, prod_name=i_product.name, count=str(i_product.count),
                        sum=i_product.count*i_product.price))

        return '\n\n'.join(text)

    def get_order_status(self) -> str:
        '''Метод возвращает человекочитаемый статус заказа'''
        if self.status == 0:
            return 'корзина'
        elif self.status == 1:
            return 'ожидает подтверждения'
        elif self.status == 2:
            return 'ожидает оплаты'
        elif self.status == 3:
            return 'оплачен'
        elif self.status == 4:
            return 'изготавливается'
        elif self.status == 5:
            return 'готов к доставке'
        elif self.status == 6:
            return 'готов к выдаче'
        elif self.status == 7:
            return 'завершен'
        elif self.status == 8:
            return 'отменен продавцом'
        elif self.status == 9:
            return 'отменен покупателем'

    def is_actual(self):
        """Метод возвращает True если заказ всё еще актуален"""
        return self.status not in [0, 7, 8, 9]

    def possibility_delivery(self) -> bool:
        """
            Метод проверяет, возможно ли выполнить доставку заказа, т.е. все ли товары в заказе могут быть доставлены
        """
        return all([i_product.delivery for i_product in self.products])


class Basket(Order):
    """
        Класс - корзина пользователя. Является дочерним классом для класса Заказов и является хранилищем продуктов
    которые покупатель только собирается купить. Предоставляет соответсвующий интерфейс для взаимодействия с товарами.
    """

    def __init__(self,
                 tgId: Optional[int] = None,
                 status: int = 0,
                 idOrder: Optional[int] = None,
                 datetimeCreation: Optional[str] = None,
                 totalCost: Optional[int] = 0,
                 delivery: bool = False,
                 products: Union[str, List[Product]] = list(),
                 datetimeUpdate: Optional[str] = None,
                 userComment: Optional[str] = None,
                 sellerComment: Optional[str] = None,
                 completionDate: Optional[str] = None,
                 source: Optional[str] = None,
                 product_url: Optional[str] = None,
                 order_url: Optional[str] = None,
                 registered_on_server: bool = False
                 ):
        super().__init__(
            tgId,
            status,
            idOrder,
            datetimeCreation,
               totalCost,
            delivery,
            products,
            datetimeUpdate,
            userComment,
            sellerComment,
            completionDate,
            source,
            product_url,
            order_url,
            registered_on_server
        )

    def add_product(self, product: Product, count: int) -> None:
        """Метод добавляет в заказ новый продукт"""
        product_in_basket = list(filter(lambda i_product: i_product == product, self.products))

        if len(product_in_basket) > 0:
            new_product: Product = product_in_basket[0]
            new_product.count += count

        else:
            new_product = deepcopy(product)
            new_product.count = count
            self.products.append(new_product)

        self.__update_total_cost()

    def __update_total_cost(self):
        """Метод пересчитывает общую стоимость всех товаров в корзине"""
        self.totalCost = sum([i_product.count * i_product.price for i_product in self.products])

    def __repr__(self) -> str:
        """Данный метод предоставляет текстовую информацию о корзине при обращении к ней как к текстовому объекту"""
        if len(self.products) > 0:
            text = list()
            text.append(f"Всего {len(self.products)} товаров на сумму {self.totalCost} рублей:\n")

            for index, i_product in enumerate(self.products):
                i_product: Product
                text.append(f'{index + 1}. {i_product.category}: {i_product.name} x {i_product.count} ='
                            f' {i_product.count * i_product.price}')

            return '\n'.join(text)
        return ''

    def delete(self, index: int) -> None:
        """Метод удаления переданного товара из корзины"""
        self.products.pop(index)
        self.__update_total_cost()

    def clear(self) -> None:
        """Метод удаляет все продукты из корзины"""
        self.products = list()
        self.__update_total_cost()

    def get_list_product_name(self) -> List[str]:
        """Метод возвращает список названий товаров в корзине"""
        list_product_name = list()
        for index, i_product in enumerate(self.products):
            list_product_name.append(f'{index+1}. {i_product.category}: {i_product.name} - {i_product.count} шт.')
        return list_product_name


class OrderSchema(Schema):
    """
        Класс - модель данных json о заказе получаемого от внешнего API при запросе заказа. Служит для валидации,
    сериализации и десериализации данных
    """
    tgId = fields.Int(required=False)
    idOrder = fields.Int(required=False)
    status = fields.Int(required=True, allow_none=False, validate=[validate.Range(0, 10)])
    datetimeCreation = fields.Str(required=True, allow_none=True)
    datetimeUpdate = fields.Str(required=False, allow_none=True)
    userComment = fields.Str(required=False, allow_none=True, validate=[validate.Length(0, 201)])
    sellerComment = fields.Str(required=False, allow_none=True, validate=[validate.Length(0, 501)])
    completionDate = fields.Str(required=False, allow_none=True)
    totalCost = fields.Int(required=True, allow_none=False)
    delivery = fields.Boolean(required=True, allow_none=False)
    #products = fields.List(ProductDataSchema, required=True, allow_none=False)
    products = fields.Nested(ProductDataSchema, many=True, required=True)
    source = fields.Str(required=False, allow_none=True, dump_only=True, validate=[validate.OneOf(['buyer', 'seller'])])
    product_url = fields.Str(required=True, allow_none=False, load_only=True)
    order_url = fields.Str(required=True, allow_none=False, load_only=True)
    registered_on_server = fields.Boolean(required=True, allow_none=False, load_only=True)

    @post_load
    def create_order(self, data, **kwargs) -> Order:
        """Метод позволяет возвратить после загрузки данных объект заказа"""
        status = data.get('status')
        if status == 0:
            return Basket(**data)

        return Order(**data)
