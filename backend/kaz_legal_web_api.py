# kaz_legal_web_api.py (Версия 4.9 — Улучшенное форматирование ответов AI)
from memory import init_db, save_message, load_conversation, delete_conversation, get_all_sessions_summary_mongo
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
import google.generativeai as genai
import os
import json
import re
from flask_cors import CORS
import bleach # Для очистки HTML от XSS
from concurrent.futures import ThreadPoolExecutor # Для асинхронных вызовов
from PIL import Image # Для обработки изображений
import io # Для работы с байтовыми потоками
from docx import Document # Для чтения .docx
from PyPDF2 import PdfReader # Для чтения .pdf
import logging # Для логирования

# --- НОВОЕ: Импортируем helpers ---
from helpers import expand_keywords, build_snippet

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 GB (1 ГБ)
CORS(app, origins=["https://ai-lawyer-tau.vercel.app", "http://localhost:5000"]) # Добавьте ваш локальный адрес для разработки

# --- Инициализация AI и Базы Законов ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    'gemini-1.5-flash',
    generation_config={"response_mime_type": "text/plain", "temperature": 0.7}, # Model still prefers markdown but will adapt to HTML instruction
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
)
multimodal_model = genai.GenerativeModel( # Модель для работы с изображениями и текстом
    'gemini-1.5-flash',
    generation_config={"response_mime_type": "text/plain", "temperature": 0.7},
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
)

LAW_DB = []
LAW_INDEX = {} # Инвертированный индекс для быстрого поиска
# --- УЛУЧШЕНИЕ: Максимально расширенный словарь синонимов (с добавлением налоговых терминов) ---
LEGAL_SYNONYMS = {
    # Трудовые отношения
    'увольнение': ['уволен', 'увольняет', 'сокращение', 'расторжение договора', 'прекращение трудового договора', 'расчет', 'увольнение'],
    'отпуск': ['отпускные', 'ежегодный отпуск', 'трудовой отпуск', 'больничный', 'декретный отпуск'],
    'зарплата': ['заработная плата', 'оплата труда', 'выплата', 'аванс', 'расчет', 'оклад', 'премия'],
    'трудовой договор': ['трудовой контракт', 'договор', 'соглашение о труде', 'контракт'],
    'работодатель': ['компания', 'фирма', 'предприятие', 'начальник', 'руководство', 'организация'],
    'работник': ['сотрудник', 'персонал', 'служащий', 'подчиненный'],
    # Налоги
    'ИП': ['индивидуальный предприниматель', 'предприниматель', 'ИПшник', 'частник'],
    'УСН': ['упрощенная система налогообложения', 'упрощенка'],
    'налог': ['налоги', 'налоговый', 'сбор', 'пошлина', 'НДС', 'КПН', 'ИПН', 'социальный налог', 'отчисления', 'взносы'],
    'ЕНП': ['единый совокупный платеж'],
    'патент': ['специальный налоговый режим на основе патента'],
    'декларация': ['налоговая декларация', 'отчетность'],
    'срок': ['сроки', 'период', 'дата'],
    'штраф': ['пени', 'взыскание'],
    # Семья и брак
    'развод': ['расторжение брака', 'развод', 'алименты', 'раздел имущества'],
    'брак': ['женитьба', 'семейный союз', 'супружество'],
    'алименты': ['выплаты на ребенка', 'содержание'],
    'имущество': ['недвижимость', 'активы', 'собственность'],
    # Уголовное право
    'кража': ['хищение', 'воровство'],
    'мошенничество': ['обман', 'афера'],
    'преступление': ['правонарушение', 'уголовное дело'],
    'наказание': ['срок', 'тюрьма', 'штраф', 'лишение свободы'],
    # Административное право
    'штраф': ['административный штраф', 'взыскание'],
    'нарушение': ['проступок', 'правонарушение'],
    'протокол': ['административный протокол'],
    # Гражданское право
    'договор': ['контракт', 'соглашение'],
    'возмещение ущерба': ['компенсация', 'возмещение убытков'],
    'иск': ['исковое заявление', 'судебный иск'],
    'собственность': ['право собственности', 'имущество'],
    # Общие юридические термины
    'закон': ['кодекс', 'нормативный акт', 'постановление', 'правила'],
    'статья': ['пункт', 'часть', 'подпункт'],
    'суд': ['судебный орган', 'правосудие', 'истец', 'ответчик'],
    'жалоба': ['обращение', 'заявление', 'петиция'],
    'консультация': ['совет', 'помощь', 'разъяснение'],
    'документ': ['бумага', 'справка', 'акт', 'удостоверение'],
}

def load_laws():
    global LAW_DB, LAW_INDEX
    try:
        # Construct the absolute path to kazakh_laws.json
        base_dir = os.path.dirname(os.path.abspath(__file__))
        laws_file_path = os.path.join(base_dir, 'laws', 'kazakh_laws.json')

        with open(laws_file_path, 'r', encoding='utf-8') as f:
            LAW_DB = json.load(f)
        logging.info(f"✅ Загружено {len(LAW_DB)} законов.")

        # Построение инвертированного индекса
        LAW_INDEX = {}
        for i, law in enumerate(LAW_DB):
            text_content = (law.get('title', '') + ' ' + law.get('text', '')).lower()
            words = re.findall(r'\b\w+\b', text_content)
            for word in words:
                if word not in LAW_INDEX:
                    LAW_INDEX[word] = []
                LAW_INDEX[word].append(i) # Сохраняем индекс закона в LAW_DB
        logging.info("✅ Построен инвертированный индекс.")

    except FileNotFoundError:
        logging.error(f"❌ Ошибка: Файл законов не найден по пути: {laws_file_path}")
    except json.JSONDecodeError as e:
        logging.error(f"❌ Ошибка декодирования JSON в файле законов: {e}")
    except Exception as e:
        logging.error(f"❌ Неизвестная ошибка при загрузке законов: {e}")

load_laws() # Load laws at startup
init_db() # Инициализируем MongoDB соединение при старте приложения

# --- НОВОЕ: Функция для извлечения текста из документов с ограничением ---
def extract_text_from_pdf(file_stream, max_chars=50000): # Лимит 50,000 символов
    reader = PdfReader(file_stream)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
        if len(text) > max_chars: # Прекращаем чтение, если достигнут лимит
            text = text[:max_chars]
            break
    return text.strip()

def extract_text_from_docx(file_stream, max_chars=50000): # Лимит 50,000 символов
    document = Document(file_stream)
    text = ""
    for paragraph in document.paragraphs:
        text += paragraph.text + "\n"
        if len(text) > max_chars: # Прекращаем чтение
            text = text[:max_chars]
            break
    return text.strip()

def get_file_parts(file):
    # Determine MIME type from the file object's mimetype attribute
    mime_type = file.mimetype
    file_stream = io.BytesIO(file.read()) # Создаем байтовый поток из FileStorage

    if mime_type == 'image/jpeg' or mime_type == 'image/png':
        # Для изображений возвращаем FileData
        return [genai.types.FileData(mime_type=mime_type, data=file_stream.getvalue())]
    elif mime_type == 'application/pdf':
        text_content = extract_text_from_pdf(file_stream)
        return [{"text": text_content}]
    elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        text_content = extract_text_from_docx(file_stream)
        return [{"text": text_content}]
    elif mime_type == 'text/plain':
        text_content = file_stream.read().decode('utf-8')
        return [{"text": text_content[:50000]}] # Лимит 50,000 символов для текстовых файлов
    else:
        logging.warning(f"Неподдерживаемый тип файла: {mime_type}")
        return []

# --- НОВОЕ: Полностью заменяем find_laws_by_keywords ---
def find_laws_by_keywords(question, max_snippet_chars: int = 4000):
    """
    Ищет релевантные законы и возвращает список словарей с
    title / article / text (=короткий сниппет), не превышая max_snippet_chars.
    """
    question_lower = question.lower()
    raw_keywords = set(re.findall(r'\b\w+\b', question_lower))
    expanded_keywords = expand_keywords(raw_keywords, LEGAL_SYNONYMS)

    # Собираем id статей из инвертированного индекса
    law_ids = set()
    for kw in expanded_keywords:
        law_ids.update(LAW_INDEX.get(kw, []))

    # Считаем простую релевантность
    def relevance(law_index):
        law = LAW_DB[law_index]
        txt = (law.get('title', '') + ' ' + law.get('text', '')).lower()
        return sum(txt.count(kw) for kw in expanded_keywords)

    # Сортируем, готовим сниппеты, следим за общим объёмом
    selected, total = [], 0
    # Сортируем индексы законов по релевантности, затем получаем сами законы
    sorted_law_indices = sorted(list(law_ids), key=relevance, reverse=True)

    for law_index in sorted_law_indices:
        law = LAW_DB[law_index]
        # Используем build_snippet для создания компактного сниппета
        snippet = build_snippet(law.get('text', ''), expanded_keywords)

        law_entry = {
            "title":   law.get('title', ''),
            "article": law.get('article', ''),
            "text":    snippet
        }
        # Оцениваем размер в символах для простоты (токены примерно коррелируют)
        size = len(snippet) + len(law_entry["title"]) + len(law_entry["article"]) + 50 # Добавляем запас

        if total + size > max_snippet_chars:
            logging.info(f"🛑 Достигнут лимит символов для сниппетов законов. Остановились на {len(selected)} законах. Общий размер: {total} символов.")
            break

        selected.append(law_entry)
        total += size

        if len(selected) >= 8:   # максимум 8 статей на запрос (можно настроить)
            logging.info(f"🛑 Достигнут лимит по количеству статей. Выбрано {len(selected)} статей.")
            break

    logging.info(f"✅ Найдено {len(selected)} законов, передано {total} символов.")
    return selected

# --- Генерация ответа AI ---
def generate_response(chat_history_formatted, user_question, relevant_laws_info=None, document_content=None):
    prompt_parts = []

    # Системная инструкция
    system_instruction = """
    Ты - AI-юрист, специализирующийся исключительно на законодательстве Республики Казахстан.
    Твоя главная задача - предоставлять точную, актуальную и полную юридическую информацию,
    основанную на законах и нормативных актах РК.
    
    При ответе следуй этим правилам:
    1.  Всегда явно указывай, что информация относится к законодательству Республики Казахстан.
    2.  Если вопрос нечеткий или слишком общий, или требует уточнения для применения конкретных норм РК,
        задавай уточняющие вопросы. Например: "Пожалуйста, уточните, какой аспект [тема] вас интересует в рамках законодательства РК?"
    3.  Используй официальный, но понятный язык. Избегай жаргона, где это возможно.
    4.  Если вопрос выходит за рамки законодательства РК или является этически спорным,
        вежливо откажись отвечать и предложи переформулировать вопрос в рамках твоей компетенции.
    5.  Не придумывай информацию. Если у тебя нет данных, так и скажи.
    6.  Приводи ссылки на статьи законов или нормативные акты, если это уместно и возможно.
    7.  Ответы должны быть лаконичными, но исчерпывающими.
    8.  Будь вежливым и профессиональным.
    """
    prompt_parts.append({"role": "user", "parts": [{"text": system_instruction}]})
    prompt_parts.append({"role": "model", "parts": [{"text": "Понял. Я готов предоставлять консультации строго по законодательству Республики Казахстан, оформляя ответы в формате HTML."}]})

    # --- ОГРАНИЧЕНИЕ ИСТОРИИ ЧАТА ---
    # Определите, сколько последних сообщений вы хотите сохранить.
    # Каждая пара (пользователь, модель) - это 2 сообщения.
    # Начните с небольшого числа, например, 10-20 сообщений.
    MAX_HISTORY_MESSAGES = 10 # Например, последние 10 сообщений (5 пар диалогов)

    # Усекаем историю, чтобы в модель попадали только последние N сообщений
    truncated_chat_history_formatted = chat_history_formatted[-MAX_HISTORY_MESSAGES:]

    for msg in truncated_chat_history_formatted:
        prompt_parts.append({"role": msg["role"], "parts": [msg["content"]]})

    # Добавляем информацию о законах, если она есть
    if relevant_laws_info:
        laws_text = "\n\nИспользуй следующую информацию из законодательства РК для ответа:\n"
        for law in relevant_laws_info:
            laws_text += f"Название: {law.get('title', 'N/A')}\n"
            laws_text += f"Статья/Пункт: {law.get('article', 'N/A')}\n"
            laws_text += f"Текст: {law.get('text', 'N/A')}\n\n"
        prompt_parts.append({"role": "user", "parts": [{"text": laws_text}]})
        prompt_parts.append({"role": "model", "parts": [{"text": "Принял к сведению предоставленную информацию о законах."}]})

    # Добавляем содержимое документа, если оно есть
    if document_content:
        # Если это бинарные данные (изображения), добавляем напрямую
        if isinstance(document_content, list) and document_content and isinstance(document_content[0], genai.types.FileData):
            prompt_parts.append({"role": "user", "parts": document_content})
            # Для мультимодальных запросов, текущий вопрос пользователя добавляется после файла
            final_user_question = f"Мой вопрос: {user_question}"
            prompt_parts.append({"role": "user", "parts": [{"text": final_user_question}]})
            logging.info("Отправляем мультимодальный запрос с изображением/файлом.")
            response = multimodal_model.generate_content(prompt_parts)
        else: # Иначе это текстовый контент из документа
            doc_text = "\n\nИспользуй следующий документ для ответа:\n"
            if isinstance(document_content, list):
                for part in document_content:
                    if "text" in part:
                        doc_text += part["text"] + "\n"
            else:
                doc_text += str(document_content)

            prompt_parts.append({"role": "user", "parts": [{"text": doc_text}]})
            prompt_parts.append({"role": "model", "parts": [{"text": "Принял к сведению содержимое документа."}]})

            # Добавляем текущий вопрос пользователя для текстовых документов
            final_user_question = f"Мой вопрос: {user_question}"
            prompt_parts.append({"role": "user", "parts": [{"text": final_user_question}]})
            logging.info("Отправляем текстовый запрос с документом.")
            response = model.generate_content(prompt_parts)
    else: # Если документа нет, просто добавляем вопрос пользователя
        final_user_question = f"Мой вопрос: {user_question}"
        prompt_parts.append({"role": "user", "parts": [{"text": final_user_question}]})
        logging.info("Отправляем текстовый запрос без документа.")
        response = model.generate_content(prompt_parts)

    # --- ИСПРАВЛЕНИЕ: Преобразование frozenset в list для bleach.clean ---
    # Убедимся, что все нужные HTML теги разрешены
    ALLOWED_TAGS_EXTENDED = list(bleach.sanitizer.ALLOWED_TAGS) + [
        'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a',
        'div', # Добавляем div для возможного блочного форматирования
        'span' # Добавляем span для инлайн форматирования
    ]
    clean_answer = bleach.clean(
        response.text,
        tags=ALLOWED_TAGS_EXTENDED,
        attributes={'a': ['href', 'title']},
        strip=True
    )
    return clean_answer

# --- Маршрут для обработки запросов AI ---
@app.route("/ask", methods=["POST"])
def ask_ai():
    try:
        data = request.json
        user_question = data.get("question", "")
        session_id = data.get("session_id", "default")
        uploaded_file = request.files.get('file') # Получаем файл, если он есть

        logging.info(f"Получен запрос для сессии {session_id}: '{user_question[:50]}...'")

        if not user_question and not uploaded_file:
            return jsonify({"error": "Вопрос или файл не предоставлен."}), 400

        # Загружаем историю чата из MongoDB
        chat_history = load_conversation(session_id)

        # Преобразуем историю для модели
        chat_history_formatted = []
        for msg in chat_history:
            content_text = ""
            if isinstance(msg.get("parts"), list):
                for part in msg["parts"]:
                    if isinstance(part, dict) and "text" in part:
                        content_text += part["text"]
                    elif isinstance(part, str):
                        content_text += part
            elif isinstance(msg.get("parts"), str):
                content_text = msg["parts"]
            chat_history_formatted.append({"role": msg["role"], "content": content_text})

        # --- ОБРАБОТКА ДОКУМЕНТОВ ---
        document_content_for_model = None
        if uploaded_file:
            logging.info(f"Обработка загруженного файла: {uploaded_file.filename} ({uploaded_file.mimetype})")
            document_content_for_model = get_file_parts(uploaded_file)
            if not document_content_for_model:
                return jsonify({"error": "Не удалось обработать загруженный файл."}), 400

        # Поиск релевантных законов (теперь использует сниппеты)
        relevant_laws_info = find_laws_by_keywords(user_question)

        # Генерируем ответ асинхронно
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(generate_response, chat_history_formatted, user_question, relevant_laws_info, document_content_for_model)
        ai_answer = future.result() # Ожидаем результат

        # Сохраняем вопрос пользователя и ответ AI в историю
        save_message(session_id, "user", user_question)
        save_message(session_id, "model", ai_answer) # Сохраняем уже HTML ответ

        logging.info(f"Ответ AI для сессии {session_id} сгенерирован успешно.")
        return jsonify({"answer": ai_answer, "session_id": session_id})

    except genai.APIError as e: # ИСПРАВЛЕНО: Правильный путь для исключения API
        logging.error(f"❌ Ошибка API ключа Gemini или другая ошибка API: {e}")
        return jsonify({"error": "Ошибка конфигурации API: Ключ Gemini API недействителен или отсутствует, либо другая ошибка API."}), 500
    except genai.types.BlockedPromptException as e:
        logging.warning(f"⚠️ Запрос был заблокирован из-за правил безопасности: {e}")
        return jsonify({"error": "Ваш запрос был отклонен из-за правил безопасности AI. Пожалуйста, переформулируйте."}), 400
    except genai.types.StopCandidateException as e:
        logging.warning(f"⚠️ Генерация ответа была остановлена до завершения: {e}")
        return jsonify({"error": "Ответ был неполным. Пожалуйста, попробуйте еще раз или задайте уточняющий вопрос."}), 500
    except Exception as e:
        logging.error(f"❌ Ошибка в /ask: {e}", exc_info=True) # exc_info=True для полного traceback
        return jsonify({"error": f"Ошибка сервера: {str(e)}"}), 500


# --- Маршрут для загрузки истории сообщений ---
@app.route("/get-history", methods=["GET"])
def get_history():
    session_id = request.args.get("session_id", "default")
    try:
        history = load_conversation(session_id)
        formatted_history = []
        for entry in history:
            # Убедитесь, что content корректно извлекается
            # Теперь content может быть HTML, поэтому передаем его как есть
            content = entry['parts'][0] if isinstance(entry['parts'], list) and entry['parts'] else ''
            formatted_history.append({"role": entry['role'], "content": content})
        return jsonify({"history": formatted_history})
    except Exception as e:
        logging.error(f"❌ Ошибка в /get-history: {e}")
        return jsonify({"error": f"Ошибка сервера при получении истории: {str(e)}"}), 500

# --- Маршрут для получения сводки всех сессий для отображения в сайдбаре ---
@app.route("/get-all-sessions-summary", methods=["GET"])
def get_all_sessions_summary_route():
    try:
        sessions_summary = get_all_sessions_summary_mongo()
        return jsonify({"sessions": sessions_summary})
    except Exception as e:
        logging.error(f"❌ Ошибка в /get-all-sessions-summary: {e}")
        return jsonify({"error": f"Ошибка сервера при получении сводки сессий: {str(e)}"}), 500

# --- Маршрут для удаления истории сообщений ---
@app.route("/clear-history", methods=["POST"])
def clear_history_route():
    session_id = request.json.get("session_id", "default")
    try:
        delete_conversation(session_id)
        return jsonify({"message": "История очищена", "session_id": session_id})
    except Exception as e:
        logging.error(f"❌ Ошибка в /clear-history: {e}")
        return jsonify({"error": f"Ошибка сервера при очистке истории: {str(e)}"}), 500

# --- Маршрут для главной страницы (обслуживание frontend) ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

# --- Запуск сервера Flask ---
if __name__ == '__main__':
    # Используйте '0.0.0.0' для прослушивания всех доступных сетевых интерфейсов
    # Это необходимо для развертывания на Railway.
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000))
