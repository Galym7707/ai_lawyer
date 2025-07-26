import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime

# Получаем строку подключения из переменных окружения
# Эту переменную вы установите на Railway
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "ai_lawyer_chat"  # Имя базы данных в MongoDB Atlas

# Глобальные переменные для клиента и базы данных. Они заполняются при
# вызове ``init_db``. Использование глобальных переменных позволяет
# удобно делиться клиентом между функциями без дополнительного
# конфигурирования.
client = None
db = None

def init_db() -> None:
    """Инициализирует подключение к MongoDB.

    Читает URI из переменных окружения, создаёт клиент и проверяет
    соединение. Если переменная окружения ``MONGO_URI`` не задана,
    выводит ошибку и не выполняет подключение. При любых ошибках
    подключения также обнуляет глобальные переменные.
    """
    global client, db
    if not MONGO_URI:
        # Явно проверяем наличие URI — без него подключение невозможно
        print("❌ Ошибка: Переменная окружения MONGO_URI не установлена. Подключение к MongoDB невозможно.")
        return

    try:
        # Устанавливаем таймаут соединения, чтобы избежать бесконечного ожидания
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Проверка соединения с базой данных
        client.admin.command('ping')
        db = client[DB_NAME]
        print("✅ Подключение к MongoDB Atlas успешно установлено.")

        # Создаём коллекцию и индексы, если они отсутствуют. Это важно для
        # корректной работы методов сохранения и выборки сообщений.
        if "conversations" not in db.list_collection_names():
            db.create_collection("conversations")
        # Индекс по session_id и message_index ускоряет сортировку и поиск
        db.conversations.create_index([("session_id", 1), ("message_index", 1)], unique=False)
    except ConnectionFailure as e:
        print(f"❌ Ошибка подключения к MongoDB (ConnectionFailure): {e}")
        client = None
        db = None
    except OperationFailure as e:
        print(f"❌ Ошибка операции с MongoDB (OperationFailure - возможно, некорректные учетные данные или IP-адрес): {e}")
        client = None
        db = None
    except Exception as e:
        print(f"❌ Неизвестная ошибка при инициализации MongoDB: {e}")
        client = None
        db = None

def save_message(session_id: str, role: str, content: str) -> None:
    """Сохраняет сообщение в базе данных.

    Если база данных не инициализирована, выводит предупреждение и
    завершает функцию. Индекс сообщения вычисляется на основе
    последнего сохранённого сообщения для данной сессии.
    """
    global db
    if db is None:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Сохранение невозможно.")
        return

    try:
        # Ищем последнее сообщение в данной сессии, чтобы вычислить новый индекс
        last_message = db.conversations.find_one(
            {"session_id": session_id},
            sort=[("message_index", -1)]
        )
        message_index = (last_message["message_index"] + 1) if last_message else 0

        message_document = {
            "session_id": session_id,
            "message_index": message_index,
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        }
        db.conversations.insert_one(message_document)
    except Exception as e:
        print(f"❌ Ошибка при сохранении сообщения в MongoDB: {e}")

def load_conversation(session_id: str):
    """Возвращает список сообщений для указанной сессии.

    Формат результата соответствует требованиям Google Generative AI API:
    каждый элемент списка содержит ``role`` и список ``parts``, где
    ``parts`` — это словари с ключом ``text``.
    """
    global db
    if db is None:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Загрузка невозможна.")
        return []
    try:
        messages = db.conversations.find(
            {"session_id": session_id},
            sort=[("message_index", 1)]
        )
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
        return formatted_messages
    except Exception as e:
        print(f"❌ Ошибка при загрузке истории из MongoDB: {e}")
        return []

def delete_conversation(session_id: str) -> None:
    """Удаляет все сообщения для указанной сессии."""
    global db
    if db is None:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Удаление невозможно.")
        return
    try:
        result = db.conversations.delete_many({"session_id": session_id})
        print(f"🗑️ Удалено {result.deleted_count} сообщений для сессии {session_id}.")
    except Exception as e:
        print(f"❌ Ошибка при удалении истории из MongoDB: {e}")

def get_all_sessions_summary_mongo():
    """Возвращает сводку всех сессий в виде списка словарей.

    Каждый элемент списка содержит идентификатор сессии и сокращённое
    название первого сообщения пользователя. Если база данных не
    инициализирована, возвращает пустой список.
    """
    global db
    if db is None:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Получение сводки невозможно.")
        return []
    try:
        pipeline = [
            {"$group": {
                "_id": "$session_id",
                "first_user_message_content": {"$first": "$content"},
                "first_user_message_role": {"$first": "$role"},
                "first_message_timestamp": {"$first": "$timestamp"}
            }},
            {"$addFields": {
                "first_user_message_content": {
                    "$cond": [
                        {"$eq": ["$first_user_message_role", "user"]},
                        "$first_user_message_content",
                        "$$REMOVE"
                    ]
                }
            }},
            {"$match": {"first_user_message_content": {"$exists": True}}},
            {"$project": {
                "id": "$_id",
                "title": {"$cond": [
                    {"$ne": ["$first_user_message_content", None]},
                    {"$concat": [
                        {"$substrCP": ["$first_user_message_content", 0, 50]},
                        "..."
                    ]},
                    "Новый чат"
                ]},
                "_id": 0
            }},
            {"$sort": {"id": 1}}
        ]
        sessions_summary = list(db.conversations.aggregate(pipeline))
        return sessions_summary
    except Exception as e:
        print(f"❌ Ошибка при получении сводки сессий из MongoDB: {e}")
        return []
