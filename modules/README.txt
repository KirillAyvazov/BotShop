Версия 1.0.3
- Поправил баг с отображением информации пользователей
- Сделал тесты для пула покупателей и продавцов
- Для метода data_control сделал вариант исполнения для тестов
- Реализовал обработку исключений в методе data_control которые могут возникнуть при обработке данных пользователей
- Изменил логику сохранения данных пользователей на сервер при отсутствующем интернет соединении

Версия 1.0.2
- Для класса BotShop сделал рефакторинг метода для работы с уведомлениями пользователей
- Для класса UserPoll реализовал логику удаления уведомлений после завершения сессии пользователя
- Для класса User реализовал необходимые методы для работы с уведомлениями пользователей
- Создал таблицу для хранения данных об уведомлениях пользователей в локальной базе данных
- В пуле пользователей реализовал метод для проверки - активен ли пользователь
- Продавцу добавил метод обновления активных заказов
- Покупателю добавил метод обновления заказов
- сделал обработку исключений при отправке пользователю уведомлений

Версия 1.0.1
- сделал корректировку времени

Версия 1.0.0
- реализована логика продавца
- реализована логика покупателя
- реализован пул категорий
- реализована авторизация продавцов