from faker import Faker
from typing import Optional


fake = Faker("ru_RU")


class UserFaker:
    """Класс - модель пользователя со случайными данными"""

    all_object = dict()

    def __init__(self, tgId: int):
        self.tgId = tgId
        self.firstName = fake.last_name()
        self.lastName = fake.first_name()
        self.nickname = fake.first_name()
        self.phoneNumber = fake.phone_number()
        self.homeAddress = fake.address()

        self.all_object[tgId] = self

    @classmethod
    def get_fake_user(cls, tgId: int) -> Optional["UserFaker"]:
        return cls.all_object.get(tgId, None)
