"""В данном модуле приведены примеры создания и использования основных объектов проекта"""

from telebot.types import Message

# Осуществляем необходимые импорты:
from modules.configurator import Configurator
from modules.logger import logger_init
from modules.bot import BotShop, CommandPool, MessageContent, Command
from modules.user import ShopperPool, SellerPool
from modules.products import CategoryPool


# КОНФИГУРАТОР
# Создаём объект - конфигуратор. Объект, хранящий все настройки проекта
configurator = Configurator()


# ЛОГИРОВАНИЕ
# Конфигурируем логгеры проекта
logger_init(development_logger_level=configurator.logger.development_logger_level,
            business_logger_level=configurator.logger.business_logger_level)


# ТЕЛЕРГАММ БОТ
# Создаем объект - телеграмм бота:
bot = BotShop(configurator.bot.token)
# Создаем объект - пул команд бота. Этот объект необходим для автоматического подключения описанных в обработчиках
# команд
command_pool = CommandPool(bot)


# ПОКУПАТЕЛИ
# Создаем хранилище данных покупателей. Объект предоставляет доступ ко всем объектам-покупателям по их id
shopper_pool = ShopperPool(shopper_url=configurator.api.shopper,
                           orders_url=configurator.api.order,
                           session_time=configurator.shopper_data.session_time)
# Запускаем поток для контроля данных пользователей. При помощи этого метода контролируется сессия каждого пользователя
shopper_pool.data_control()
# Передаем пулу пользователей объект телеграмм бот. Это необходимо для отправки автоматичесиких сообщений пользователю
shopper_pool.add_bot(bot)


# ПРОДАВЦЫ
# Создаем пул продавцов. Объект предоставляет доступ ко всем объектам-продавцам по их id
seller_pool = SellerPool(seller_url=configurator.api.shopper,
                        orders_url=configurator.api.order,
                        authorization_url=configurator.api.authorization_url,
                        session_time=configurator.seller_data.session_time)
# Запускаем поток для контроля данных пользователей. При помощи этого метода контролируется сессия каждого пользователя
seller_pool.data_control()
# Передаем пулу пользователей объект телеграмм бот. Это необходимо для отправки автоматичесиких сообщений пользователю
seller_pool.add_bot(bot)


# КАТЕГОРИИ ТОВАРОВ
# Создаем объект пул категорий. Объект хранит весь список категорий продаваемых товаров
category_pool = CategoryPool(url_category=configurator.api.category, url_product=configurator.api.product,
                             update_period=configurator.product_data.update_period)
# Запускаем поток по контролю обновлений товаров
category_pool.data_control()


# НАСТРОЙКА БОТА
# Боту передаем хранилище данных покупаетелей
bot.add_user_pool(shopper_pool)
# ИЛИ
# Боту передаем хранилище данных продавцов
bot.add_user_pool(seller_pool)


# ЗАГОТОВЛЕННЫЕ СООБЩЕНИЯ
# Создаем объект хранящий заготовки сообщений и получаем текст сообщений
message_content = MessageContent('text_message.json')


if __name__ == '__main__':
    # Пример простого обработчика: отправить пользователю содержимое его корзины:
    command = Command(name='basket', description="Содержимое корзины", priority=2)
    command_pool.add_command(command)

    @bot.message_handler(commands=[command.name])
    @bot.registration_incoming_message
    def show_basket(message: Message) -> None:
        """Функция просмотра корзины пользователя"""
        user = shopper_pool.get(message.chat.id) # Получаем пользователя по его id
        basket = user.get_basket() # Получаем корзину пользователя
        bot.send_message(message.chat.id, str(basket)) # Отправляем текст корзины

