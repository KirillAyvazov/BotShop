import time
from telebot.types import Message

from modules.configurator import Configurator
from modules.logger import logger_init, get_development_logger
from modules.bot import BotShop, MessageDeletionBlocker, Command, CommandPool

from modules.user import ShopperPool


if __name__ == '__main__':
    # Создаём объект - конфигуратор
    configurator = Configurator()

    # Конфигурируем логгеры проекта
    logger_init(configurator.logger.development_logger_level, configurator.logger.business_logger_level)

    # Создаем бота
    bot = BotShop(configurator.bot.token)

    # Создаем хранилище данных покупателей
    shopper_pool = ShopperPool(shopper_url=configurator.api.shopper,
                               orders_url=configurator.api.order,
                               product_url=configurator.api.product,
                               session_time=configurator.shopper_data.session_time)
    # Передаем ему объект бот
    shopper_pool.add_bot(bot)

    # Боту передаем хранилище данных покупаетелей
    bot.add_user_pool(shopper_pool)

    pool_command = CommandPool(bot)
    pool_command.add_command(Command('/too', 'Rfrfd', 2))
    pool_command.add_command(Command('/free', 'Rdsfd', 3))
    pool_command.add_command(Command('/one', 'Rfghhjfd', 1))
    pool_command.add_command(Command('/foooo', 'Rfjhdffd', 4))
    pool_command.connect_commands()

    bot.polling()







