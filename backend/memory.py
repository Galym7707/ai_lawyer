import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime

# Получаем строку подключения из переменных окружения
# Эту переменную вы установите на Railway
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "ai_lawyer_chat" # Имя базы данных в MongoDB Atlas

client = None
db = None

def init_db():
    global client, db
    if not MONGO_URI:
        print("❌ Ошибка: Переменная окружения MONGO_URI не установлена. Подключение к MongoDB невозможно.")
        return

    try:
        # Устанавливаем таймаут соединения, чтобы избежать бесконечного ожидания
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping') # Проверка соединения с базой данных
        db = client[DB_NAME]
        print("✅ Подключение к MongoDB Atlas успешно установлено.")
        
        # Создаем индекс для session_id для ускорения запросов
        # Проверяем, существует ли индекс, чтобы избежать ошибок при повторном запуске
        if "conversations" not in db.list_collection_names():
            db.create_collection("conversations")
        
        # Создаем комбинированный индекс для session_id и message_index
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

def save_message(session_id, role, content):
    if not db:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Сохранение невозможно.")
        return

    try:
        # Получаем максимальный message_index для текущей сессии
        # Если сессия новая, max_index будет None, используем 0
        latest_message = db.conversations.find({"session_id": session_id}).sort("message_index", -1).limit(1)
        max_index = 0
        if latest_message.count() > 0: # Проверяем, есть ли результаты
            for msg in latest_message: # Итерируемся по курсору
                max_index = msg.get("message_index", -1) + 1
                break # Берем первый (единственный) результат
        
        db.conversations.insert_one({
            "session_id": session_id,
            "message_index": max_index,
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow() # Добавляем метку времени
        })
        print(f"Сообщение сохранено для сессии {session_id}, индекс: {max_index}")
    except Exception as e:
        print(f"❌ Ошибка при сохранении сообщения в MongoDB: {e}")

def load_conversation(session_id):
    if not db:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Загрузка невозможна.")
        return []

    try:
        # Сортируем по message_index для правильного порядка сообщений
        messages = db.conversations.find({"session_id": session_id}).sort("message_index", 1)
        return [{"role": msg["role"], "parts": [msg["content"]]} for msg in messages]
    except Exception as e:
        print(f"❌ Ошибка при загрузке разговора из MongoDB: {e}")
        return []

def delete_conversation(session_id):
    """Удаляет всю историю сообщений для указанной сессии."""
    if not db:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Удаление невозможно.")
        return

    try:
        result = db.conversations.delete_many({"session_id": session_id})
        print(f"История для сессии {session_id} удалена. Удалено документов: {result.deleted_count}")
    except Exception as e:
        print(f"❌ Ошибка при удалении разговора из MongoDB: {e}")

def get_all_sessions_summary_mongo():
    if not db:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Загрузка сводки невозможна.")
        return []

    try:
        # Используем агрегацию для получения первого пользовательского сообщения для каждой сессии
        # Это более эффективно, чем делать отдельные запросы для каждой сессии
        pipeline = [
            # Сортируем по session_id и message_index, чтобы гарантировать порядок
            {"$sort": {"session_id": 1, "message_index": 1}},
            # Группируем по session_id и находим первое сообщение пользователя
            {"$group": {
                "_id": "$session_id",
                "first_user_message_content": {
                    "$first": {
                        "$cond": [
                            {"$eq": ["$role", "user"]},
                            "$content",
                            "$$REMOVE" # Удаляем, если не пользовательское сообщение
                        ]
                    }
                }
            }},
            # Удаляем сессии без пользовательских сообщений (если таковые есть после $$REMOVE)
            {"$match": {"first_user_message_content": {"$exists": True}}},
            # Проекция для формирования нужного формата
            {"$project": {
                "id": "$_id",
                "title": {
                    "$cond": [
                        {"$ne": ["$first_user_message_content", None]},
                        # Обрезаем заголовок до 50 символов и добавляем "..." если длиннее
                        {"$concat": [
                            {"$substrCP": ["$first_user_message_content", 0, 50]},
                            {"$cond": [
                                {"$gt": [{"$strLenCP": "$first_user_message_content"}, 50]},
                                "...",
                                ""
                            ]}
                        ]},
                        "Новый чат"
                    ]
                },
                "_id": 0
            }},
            {"$sort": {"id": 1}} # Сортируем по session_id для стабильного порядка
        ]
        
        sessions_summary = list(db.conversations.aggregate(pipeline))
        print(f"✅ Получена сводка всех сессий: {len(sessions_summary)} сессий.")
        return sessions_summary
    except Exception as e:
        print(f"❌ Ошибка при получении сводки сессий из MongoDB: {e}")
        return []
