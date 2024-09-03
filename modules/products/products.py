"""
    Данные модуль содержит описание основных сущностей, при помощи которых реализовано хранение и взаимодействие с
продаваемыми в магазине товарами.
"""
import os.path
from typing import List, Dict, Optional, Any
from telebot.types import InputMediaPhoto
import requests
from multiprocessing.pool import ThreadPool
from marshmallow import Schema, fields, post_load
import time
from threading import Semaphore
import json

from ..logger import get_development_logger
from ..utils import execute_in_new_thread

dev_log = get_development_logger(__name__)


class Product:
    """Класс - модель единицы продаваемой продукции"""
    def __init__(self, productId: str, name: str, price: int, description: str, image: List[str], delivery: bool,
                 category: str, count: int = 1):
        self.productId: str = productId
        self.name: str = name
        self.price: int = price
        self.description: str = description
        self.image: List[InputMediaPhoto] = self.__get_input_media_photo(image)
        self.delivery: bool = delivery
        self.category: str = category
        self.count: int = count

    @classmethod
    def __get_bytes_by_url(cls, url: str) -> bytes:
        """
            Данный метод вспомогательный, используется в методе get_list_images и служит для получения байтов
        изображения товара по указанному url
        """
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.content
            dev_log.exception('По url {} не удалось получить изображение товара от сервера - код {}'.format(url,
                               response.status_code))

        except Exception as ex:
            dev_log.exception('По url {} не удалось получить изображение товара от сервера'.format(url), exc_info=ex)

    def __get_list_images(self, list_url: List[str]) -> List[bytes]:
        """
            Данный метод вспомогательный и служит для получения списка байт-массивов изображений товаров из списка
        переданных url. Этот метод используется в методы get_input_media_photo
        """
        thread_pool = ThreadPool(10)
        result = thread_pool.map_async(self.__get_bytes_by_url, list_url)
        thread_pool.close()
        thread_pool.join()
        return result.get(timeout=10)

    def __get_input_media_photo(self, list_url: List[str]) -> List[InputMediaPhoto]:
        """
            Данный метод вспомогательный и служит для преобразования списка url изображений товаров в список объектов
        InputMediaPhoto - объекты, которые объект телеграм бота способен отправить пользователю в виде группового
        сообщения
        """
        list_input_media_photo = [InputMediaPhoto(i_elem)
                                  for i_elem in self.__get_list_images(list_url[:10])
                                  if isinstance(i_elem, bytes)]

        if len(list_input_media_photo) == 0:
            path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'placeholder.png')
            with open(path, 'rb') as file:
                list_input_media_photo.append(InputMediaPhoto(file.read()))

        return list_input_media_photo

    def __repr__(self) -> str:
        """Метод возвращает строку с информацией о товаре при обращении к объекту продукта как к типу str"""
        return (f"<b>Категория:</b> {self.category}\n<b>Название:</b> {self.name}\n<b>Цена:</b> "
                f"{self.price}\n<b>Описание:</b> {self.description}")


class ProductSchema(Schema):
    """
        Класс - модель данных json получаемого от внешнего API при запросе продукта. Служит для валидации, сериализации
    и десериализации данных.
    """
    productId = fields.Str(required=True, allow_none=False)
    name = fields.Str(required=True, allow_none=False)
    description = fields.Str(required=True, allow_none=False)
    price = fields.Int(required=True, allow_none=False)
    image = fields.List(fields.Str, required=True)
    delivery = fields.Boolean(required=True, allow_none=False)
    category = fields.Str(required=True, allow_none=False)

    @post_load
    def create_category(self, data, **kwargs) -> Product:
        return Product(**data)


class Category:
    """
        Класс - объекты которого объединяют в себе продукты относящиеся к определенному типу. Объект класса category
    является посредником при работе с объектами класса Product и обеспечивает их хранение и управление ими
    """
    def __init__(self, categoryId: int, name: str, variability: bool, url_category: str):
        self.__url_category: str = url_category
        self.__product_schema: ProductSchema = ProductSchema()
        self.__content_type: Dict[str, str] = {'Content-Type': 'application/json'}
        self.categoryId: int = categoryId
        self.name: str = name
        self.variability: bool = variability
        self.products: List['Product'] = self.__api_get_list_product(categoryId)


    def __api_get_list_product(self, category_id: int) -> List[Product]:
        """Метод служит для получения данных о продуктах указанной категории от внешнего API"""
        try:
            response = requests.get('/'.join([self.__url_category, str(category_id)]), headers=self.__content_type)

            if response.status_code == 200:
                return self.__product_schema.loads(response.text, many=True)

            dev_log.info(f"Не удалось получить данные о продуктах категории {self.categoryId}")

        except Exception as ex:
            dev_log.exception(f"При попытке получить данные о продуктах категории {self.categoryId} возникла ошибка",
                              exc_info=ex)

        return []

    def __repr__(self) -> str:
        """Метод возвращает название категории при обращении к объекту категории как к объекту str"""
        return self.name


class CategorySchema(Schema):
    """
        Класс - модель данных json получаемого от внешнего API при запросе списка категорий. Служит для валидации,
    сериализации и десериализации данных.
    """
    categoryId = fields.Int(required=True, allow_none=False)
    name = fields.Str(required=True, allow_none=False)
    variability = fields.Boolean(required=True, allow_none=False)
    url_category = fields.Str(required=False, allow_none=False, load_only=True)


    @post_load
    def create_category(self, data, **kwargs) -> Category:
        return Category(**data)


class CategoryPool:
    """
        Класс объект которого является для бота основной сущность для взаимодействия с каталогом продаваемых продуктов.
    Объект данного класса хранит в себе перечь доступных категорий товаров, а те, в свою очередь хранят список
    продаваемых товаров. При помощи объекта класса CategoryPool осуществляется периодическое обновление каталога
    продаваемых товаров.
    """
    def __init__(self, url_category: str, update_period: Optional[int] = None):
        self.__url_category = url_category
        self.__content_type: Dict[str, str] = {'Content-Type': 'application/json'}
        self.__category_schema: CategorySchema = CategorySchema()
        self.__update_period: Optional[int] = update_period
        self.categories: List[Category] = list()

        self.update()

    def __api_get_list_category(self) -> List[Category]:
        """Метод служит для получения от внешнего API списка категорий продаваемых товаров"""
        try:
            response = requests.get(self.__url_category, headers=self.__content_type)
            if response.status_code == 200:
                category_data: List[Dict[str, Any]] = json.loads(response.text)

                for i_dict in category_data:
                    i_dict.update({"url_category": self.__url_category})

                return self.__category_schema.loads(json.dumps(category_data), many=True)

            dev_log.info(f"Не удалось получить список категорий")

        except Exception as ex:
            dev_log.exception(f"При попытке получить список категорий возникла ошибка", exc_info=ex)

        return []

    def update(self) -> List[Category]:
        """Метод служит для получения или обновления списка категорий продаваемых товаров"""
        new_list_category = self.__api_get_list_category()
        if len(new_list_category) > 0:
            with Semaphore():
                self.categories = new_list_category

    @execute_in_new_thread(daemon=False)
    def data_control(self) -> None:
        """
            Этот метод - бесконечный цикл выполняемый в отдельном потоке - служит для обновления каталога продуктов
        с установленной периодичностью.
        """
        while self.__update_period:
            time.sleep(self.__update_period)
            self.update()
