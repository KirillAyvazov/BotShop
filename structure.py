from modules.configurator import Configurator
from modules.logger import logger_init
from modules.bot import BotShop, CommandPool
from modules.user import ShopperPool
from modules.products import CategoryPool


# Создаём объект - конфигуратор
configurator = Configurator()


# Конфигурируем логгеры проекта
logger_init(development_logger_level=configurator.logger.development_logger_level,
            business_logger_level=configurator.logger.business_logger_level)


# Создаем бота
bot = BotShop(configurator.bot.token)


# Создаем объект - пул команд для бота
command_pool = CommandPool(bot)


# Создаем хранилище данных покупателей
shopper_pool = ShopperPool(shopper_url=configurator.api.shopper,
                           orders_url=configurator.api.order,
                           product_url=configurator.api.product,
                           session_time=configurator.shopper_data.session_time)

# Запускаем поток для контроля данных пользователей
shopper_pool.data_control()

# Передаем пулу пользователей объект бот
shopper_pool.add_bot(bot)


# Боту передаем хранилище данных покупаетелей
bot.add_user_pool(shopper_pool)


# Создаем объект пул категорий
category_pool = CategoryPool(url_category=configurator.api.category,
                             update_period=configurator.product_data.update_period)

# Запускаем поток по контролю обновлений товаров
category_pool.data_control()
