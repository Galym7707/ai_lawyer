# kaz_legal_web_api.py (Версия 4.6 — Улучшенная производительность поиска, XSS защита, асинхронность, загрузка документов)
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

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 GB
CORS(app, origins=["https://ai-lawyer-tau.vercel.app", "http://localhost:5000"]) # Добавьте ваш локальный адрес для разработки

# --- Инициализация AI и Базы Законов ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.error("❌ Ошибка: Переменная окружения GEMINI_API_KEY не установлена.")
    # Вместо sys.exit() в Flask приложении лучше вернуть ошибку при запросе,
    # или инициализировать модель только при наличии ключа.
    # Для демонстрации, пока оставим заглушку, но в продакшене лучше сразу прерывать.
    genai.configure(api_key="YOUR_FALLBACK_API_KEY_OR_HANDLE_ERROR")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# Используем меньшую температуру для более точных юридических ответов
model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "text/plain", "temperature": 0.3})
multimodal_model = genai.GenerativeModel('gemini-1.5-flash') # Модель для работы с мультимодальным вводом

LAW_DB = [] # Список для хранения загруженных законов
LAW_INDEX = {} # Инвертированный индекс для быстрого поиска законов
executor = ThreadPoolExecutor(max_workers=5) # Пул потоков для асинхронных операций

# Словарь синонимов для расширения поисковых запросов
LEGAL_SYNONYMS = {
    'увольнение': ['уволен', 'уволили', 'расторжение трудового договора', 'прекращение работы'],
    'пособия': ['выплаты', 'компенсации', 'льготы', 'государственная помощь'],
    'налоги': ['налогообложение', 'фискальные сборы', 'НДС', 'ИПН', 'корпоративный подоходный налог'],
    'наследство': ['наследование', 'завещание', 'наследники', 'наследственное право'],
    'брак': ['супружество', 'семейные отношения', 'развод', 'алименты'],
    'кредит': ['займ', 'задолженность', 'ипотека', 'банковский кредит'],
    'штраф': ['административное взыскание', 'пеня', 'неустойка'],
    'договор': ['соглашение', 'контракт', 'сделка', 'обязательство'],
    'собственность': ['имущество', 'право собственности', 'владение', 'недвижимость'],
    'суд': ['судебное разбирательство', 'исковое заявление', 'процесс', 'правосудие'],
    'гражданство': ['ВНЖ', 'ПМЖ', 'паспорт', 'иностранцы'],
    'дорога': ['ПДД', 'ДТП', 'автомобиль', 'транспорт'],
    'земля': ['земельный участок', 'землепользование', 'сельское хозяйство'],
    'государство': ['правительство', 'госорганы', 'бюджет'],
    'пенсия': ['пенсионные отчисления', 'пенсионер', 'ЕНПФ'],
    'защита прав': ['юридическая защита', 'права потребителей', 'омбудсмен'],
}


# Функция для загрузки законов и построения инвертированного индекса
def load_laws():
    global LAW_DB, LAW_INDEX
    try:
        # Проверяем наличие файла laws/kazakh_laws.json
        laws_file_path = 'laws/kazakh_laws.json'
        if not os.path.exists(laws_file_path):
            logging.error(f"❌ Ошибка: Файл законов не найден по пути: {laws_file_path}")
            return

        with open(laws_file_path, 'r', encoding='utf-8') as f:
            LAW_DB = json.load(f)
        
        # Построение инвертированного индекса
        LAW_INDEX = {}
        for i, law in enumerate(LAW_DB):
            law_id = i # Используем индекс как ID
            
            # Токенизируем заголовок и текст, приводим к нижнему регистру
            text_content = (law.get('title', '') + ' ' + law.get('text', '')).lower()
            words = re.findall(r'\b\w+\b', text_content)
            
            for word in words:
                # Добавляем синонимы в индекс
                for synonym_group in LEGAL_SYNONYMS.values():
                    if word in synonym_group:
                        for s_word in synonym_group:
                            if s_word not in LAW_INDEX:
                                LAW_INDEX[s_word] = set()
                            LAW_INDEX[s_word].add(law_id)
                if word not in LAW_INDEX:
                    LAW_INDEX[word] = set()
                LAW_INDEX[word].add(law_id)
        logging.info(f"✅ Загружено {len(LAW_DB)} законов и построен инвертированный индекс.")
    except FileNotFoundError:
        logging.error(f"❌ Ошибка: Файл 'laws/kazakh_laws.json' не найден.")
    except json.JSONDecodeError as e:
        logging.error(f"❌ Ошибка декодирования JSON в 'laws/kazakh_laws.json': {e}")
    except Exception as e:
        logging.error(f"❌ Неизвестная ошибка при загрузке законов: {e}")

# Загружаем законы при старте приложения
load_laws()
init_db() # Инициализируем MongoDB соединение при старте приложения

# --- Вспомогательные функции ---
def find_laws_by_keywords(question):
    """Использует инвертированный индекс для поиска релевантных законов."""
    question_lower = question.lower()
    keywords = re.findall(r'\b\w+\b', question_lower)
    
    # Расширяем ключевые слова синонимами
    expanded_keywords = set(keywords)
    for kw in keywords:
        for group in LEGAL_SYNONYMS.values():
            if kw in group:
                expanded_keywords.update(group)
    
    relevant_law_ids = set()
    for keyword in expanded_keywords:
        if keyword in LAW_INDEX:
            relevant_law_ids.update(LAW_INDEX[keyword])
            
    relevant_laws = [LAW_DB[lid] for lid in relevant_law_ids]
    
    # Сортируем по степени релевантности (количество совпадений ключевых слов)
    # Это простая метрика, можно улучшить TF-IDF или BM25
    def calculate_relevance(law_text):
        count = 0
        law_text_lower = law_text.lower()
        for kw in expanded_keywords:
            count += law_text_lower.count(kw)
        return count

    # Ограничиваем количество законов для передачи в модель
    # Это важно для контроля токенов и фокуса модели
    relevant_laws_sorted = sorted(relevant_laws, key=lambda x: calculate_relevance(x.get('text', '') + x.get('title', '')), reverse=True)[:5] # Берем до 5 самых релевантных
    
    return relevant_laws_sorted


# --- Функции обработки документов ---
def extract_text_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def extract_text_from_docx(file_stream):
    document = Document(file_stream)
    text = ""
    for paragraph in document.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text_from_image(file_stream):
    # Google Generative AI Vision models can directly process image content.
    # We will pass the image directly to the multimodal model.
    return None # Text extraction from image will be handled by the model itself

def get_file_parts(file):
    """Возвращает содержимое файла в формате, пригодном для передачи в модель."""
    file_stream = io.BytesIO(file.read())
    mime_type = file.mimetype

    if 'image' in mime_type:
        return [genai.upload_file(file_stream.getvalue(), mime_type=mime_type)]
    elif mime_type == 'application/pdf':
        text_content = extract_text_from_pdf(file_stream)
        return [{"text": text_content}]
    elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        text_content = extract_text_from_docx(file_stream)
        return [{"text": text_content}]
    elif mime_type == 'text/plain':
        text_content = file_stream.read().decode('utf-8')
        return [{"text": text_content}]
    else:
        raise ValueError(f"Неподдерживаемый тип файла: {mime_type}")


# --- Функции для взаимодействия с AI ---
def generate_response(chat_history_formatted, user_question, relevant_laws_info=None, document_content=None):
    prompt_parts = []

    # Добавляем системные инструкции
    system_instruction = """
    Ты ИИ-юрист из Казахстана. Твоя основная задача — предоставлять юридические консультации строго по законодательству Республики Казахстан. 
    Ты должен отвечать четко, лаконично, ссылаясь на конкретные статьи, пункты и наименования законов, если это возможно. 
    Если ответ требует уточнения или информации, которой у тебя нет, задай уточняющий вопрос. 
    Не выдумывай информацию. Если не знаешь ответа, так и скажи, но постарайся предложить, где пользователь может найти информацию (например, "обратитесь к юристу", "проверьте статьи X Закона Y").
    Всегда помни о юрисдикции РК.
    """
    prompt_parts.append({"role": "user", "parts": [{"text": system_instruction}]})
    prompt_parts.append({"role": "model", "parts": [{"text": "Понял. Я готов предоставлять консультации строго по законодательству Республики Казахстан. Задавайте вопросы."}]})


    # Добавляем историю чата
    for msg in chat_history_formatted:
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
        # Если document_content - это объект FileData (для изображений), то он уже является частью, которую можно передать
        if isinstance(document_content, list) and document_content and isinstance(document_content[0], genai.types.FileData):
            # Если это список с объектом FileData, передаем его напрямую
            prompt_parts.append({"role": "user", "parts": document_content})
        else:
            # Иначе, это текстовое содержимое
            doc_text = "\n\nИспользуй следующий документ для ответа:\n"
            if isinstance(document_content, list):
                # Если это список текстовых частей (из PDF/DOCX)
                for part in document_content:
                    if "text" in part:
                        doc_text += part["text"] + "\n"
            else:
                doc_text += str(document_content) # На всякий случай, если передано что-то другое
            prompt_parts.append({"role": "user", "parts": [{"text": doc_text}]})
        prompt_parts.append({"role": "model", "parts": [{"text": "Принял к сведению содержимое документа."}]})

    # Добавляем текущий вопрос пользователя
    final_user_question = f"Мой вопрос: {user_question}"
    if document_content and isinstance(document_content, list) and document_content and isinstance(document_content[0], genai.types.FileData):
        # Если это запрос с изображением, вопрос пользователя идет после изображения
        prompt_parts.append({"role": "user", "parts": [{"text": final_user_question}]})
    elif document_content:
        # Если это документ, уточняем, что вопрос относится к документу
        prompt_parts.append({"role": "user", "parts": [{"text": final_user_question}]})
    else:
        prompt_parts.append({"role": "user", "parts": [{"text": final_user_question}]})

    # Проверяем, какая модель нужна
    if document_content and isinstance(document_content, list) and document_content and isinstance(document_content[0], genai.types.FileData):
        # Если есть FileData (изображение), используем мультимодальную модель
        response = multimodal_model.generate_content(prompt_parts)
    else:
        # Иначе, используем обычную модель
        response = model.generate_content(prompt_parts)
    
    # Очистка ответа от XSS
    clean_answer = bleach.clean(response.text, tags=bleach.sanitizer.ALLOWED_TAGS + ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a'], attributes={'a': ['href', 'title']}, strip=True)
    return clean_answer


# --- API Endpoints ---
@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/ask", methods=["POST"])
def ask_ai():
    try:
        user_question = request.json.get("question")
        session_id = request.json.get("session_id", "default")
        
        if not user_question:
            return jsonify({"error": "Вопрос не может быть пустым"}), 400

        # Загружаем историю для текущей сессии
        chat_history = load_conversation(session_id)
        
        # Преобразуем историю для модели
        chat_history_formatted = []
        for msg in chat_history:
            # Извлекаем текст из "parts", если это список объектов, как ожидает модель
            content_text = ""
            if isinstance(msg.get("parts"), list):
                for part in msg["parts"]:
                    if isinstance(part, dict) and "text" in part:
                        content_text += part["text"]
                    elif isinstance(part, str): # На случай, если "parts" содержит простые строки
                        content_text += part
            elif isinstance(msg.get("parts"), str): # На случай, если "parts" - это просто строка
                content_text = msg["parts"]

            chat_history_formatted.append({"role": msg["role"], "content": content_text})

        # Поиск релевантных законов по ключевым словам из вопроса
        relevant_laws = find_laws_by_keywords(user_question)

        # Генерируем ответ
        answer = generate_response(chat_history_formatted, user_question, relevant_laws_info=relevant_laws)
        
        # Сохраняем вопрос пользователя и ответ AI
        save_message(session_id, "user", user_question)
        save_message(session_id, "model", answer)

        return jsonify({"answer": answer, "session_id": session_id})

    except Exception as e:
        logging.error(f"❌ Ошибка в /ask: {e}")
        return jsonify({"error": f"Ошибка сервера: {str(e)}"}), 500

@app.route("/upload-document", methods=["POST"])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Файл не найден"}), 400
        
        file = request.files['file']
        user_question = request.form.get("question", "")
        session_id = request.form.get("session_id", "default")

        if file.filename == '':
            return jsonify({"error": "Имя файла не может быть пустым"}), 400
        
        # Получаем содержимое файла в нужном формате
        file_parts = get_file_parts(file)

        # Загружаем историю для текущей сессии
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

        # Генерируем ответ, передавая содержимое документа
        answer = generate_response(chat_history_formatted, user_question, document_content=file_parts)

        # Сохраняем вопрос пользователя и ответ AI. 
        # Для документов, сохраняем ссылку на файл и вопрос в истории пользователя.
        # В данном случае, мы сохраним только вопрос, так как само содержимое файла не будет храниться в MongoDB напрямую для истории.
        user_message_content = f"Вопрос к документу '{file.filename}': {user_question}" if user_question else f"Анализ документа: {file.filename}"
        save_message(session_id, "user", user_message_content)
        save_message(session_id, "model", answer)
        
        # Удаляем временный FileData для изображений
        if isinstance(file_parts, list) and file_parts and isinstance(file_parts[0], genai.types.FileData):
            for part in file_parts:
                genai.delete_file(part.uri)
                logging.info(f"🗑️ Удален временный файл Gemini: {part.uri}")

        return jsonify({"answer": answer, "session_id": session_id})

    except ValueError as ve:
        logging.error(f"❌ Ошибка загрузки документа (ValueError): {ve}")
        return jsonify({"error": f"Ошибка: {str(ve)}"}), 400
    except Exception as e:
        logging.error(f"❌ Ошибка в /upload-document: {e}")
        return jsonify({"error": f"Ошибка сервера при загрузке документа: {str(e)}"}), 500


# --- Маршрут для загрузки истории сообщений ---
@app.route("/get-history", methods=["GET"])
def get_history():
    session_id = request.args.get("session_id", "default")
    try:
        history = load_conversation(session_id)
        formatted_history = []
        for entry in history:
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000), debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')
