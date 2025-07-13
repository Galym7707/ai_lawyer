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
        # Если сессия новая, то index будет 0
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
        # print(f"💾 Сообщение сохранено в сессии {session_id} с индексом {message_index}")
    except Exception as e:
        print(f"❌ Ошибка при сохранении сообщения в MongoDB: {e}")

def load_conversation(session_id):
    if not db:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Загрузка невозможна.")
        return []
    try:
        messages = db.conversations.find(
            {"session_id": session_id},
            sort=[("message_index", 1)]
        )
        # Формат должен быть [{"role": "user", "parts": [{"text": "content"}]}]
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
        return formatted_messages
    except Exception as e:
        print(f"❌ Ошибка при загрузке истории из MongoDB: {e}")
        return []

def delete_conversation(session_id):
    if not db:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Удаление невозможно.")
        return
    try:
        result = db.conversations.delete_many({"session_id": session_id})
        print(f"🗑️ Удалено {result.deleted_count} сообщений для сессии {session_id}.")
    except Exception as e:
        print(f"❌ Ошибка при удалении истории из MongoDB: {e}")

def get_all_sessions_summary_mongo():
    if not db:
        print("❌ Ошибка: База данных MongoDB не инициализирована. Получение сводки невозможно.")
        return []
    try:
        # Используем агрегационный пайплайн для получения первого сообщения пользователя и сортировки
        pipeline = [
            # Группируем по session_id и находим первое сообщение пользователя для каждой сессии
            {"$group": {
                "_id": "$session_id",
                "first_user_message_content": {
                    "$first": "$content" # Это будет первое сообщение в сессии, независимо от роли
                },
                "first_user_message_role": {
                    "$first": "$role"
                },
                "first_message_timestamp": {
                    "$first": "$timestamp"
                }
            }},
            # Добавляем поле для определения, есть ли пользовательское сообщение в начале
            {"$addFields": {
                "first_user_message_content": {
                    "$cond": [
                        {"$eq": ["$first_user_message_role", "user"]},
                        "$first_user_message_content",
                        "$$REMOVE" # Удаляем поле, если первое сообщение не от пользователя
                    ]
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
