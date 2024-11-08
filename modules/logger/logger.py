"""
    Данный модуль содержит определения следующих функций: функция конфигурирования логгеров проекта, функция получения
логгера для разработки и функция получения бизнес логгера
    Для работы этого модуля необходимо наличие папки log_data в корне проекта!
"""

import logging.config
import sys
import os


path = "log_data"
if not os.path.exists(path):
    os.makedirs(path)


def logger_init(
    development_logger_level: str = "DEBUG", business_logger_level: str = "DEBUG"
):
    """
        Функция конфигурирует два логгера проекта - логгер для разработки и логгер для бизнеса. Конфигурируются уровни
    логгеров. Эти уровни прописаны в файле config.yaml и передаются в эту функцию при помощи конфигуратора. Поведение
    по умолчанию - все обработчики сообщений имеют тот же уровень что и их логгеры. Для того что бы изменить это
    поведение следует в словаре configuration_dict прописать в ручную необходимые уровни обработчиков.
    """

    configuration_dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "base": {
                "format": "\n%(asctime)s - %(levelname)s - %(module)s - thread: %(threadName)s - string: %(lineno)s - %(message)s",
                "datefmt": "%d-%m-%Y %H:%M:%S",
            }
        },
        "handlers": {
            "development_console": {
                "class": "logging.StreamHandler",
                "level": development_logger_level,
                "formatter": "base",
                "stream": sys.stdout,
            },
            "development_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": development_logger_level,
                "filename": os.path.join(path, "development.log"),
                "formatter": "base",
                "when": "W0",
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "business_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": business_logger_level,
                "filename": os.path.join(path, "business.log"),
                "formatter": "base",
                "when": "W0",
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "dev_log": {
                "level": development_logger_level,
                "handlers": ["development_console", "development_file"],
                "propagate": False,
            },
            "bus_log": {
                "level": business_logger_level,
                "handlers": ["business_file"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(configuration_dict)


def get_development_logger(name: str) -> logging.Logger:
    """Функция инициализации объекта лорегга разработки для конкретного модуля"""
    return logging.getLogger("dev_log.{}".format(name))


def get_business_logger(name: str) -> logging.Logger:
    """Функция инициализации объекта бизнес лорегга для конкретного модуля"""
    return logging.getLogger("bus_log.{}".format(name))
