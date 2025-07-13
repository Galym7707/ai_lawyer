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
    if not LAW_INDEX:
        logging.warning("Предупреждение: Инвертированный индекс законов пуст.")
        return []

    keywords = re.findall(r'\b\w+\b', question.lower())
    
    # Расширяем ключевые слова синонимами
    expanded_keywords = set(keywords)
    for kw in keywords:
        for syn_group in LEGAL_SYNONYMS.values():
            if kw in syn_group:
                expanded_keywords.update(syn_group)

    relevant_law_ids = set()
    for keyword in expanded_keywords:
        if keyword in LAW_INDEX:
            relevant_law_ids.update(LAW_INDEX[keyword])
    
    # Сортировка по релевантности (простое совпадение ключевых слов)
    # Можно улучшить, например, считать количество совпадений
    ranked_laws = []
    for law_id in list(relevant_law_ids):
        law = LAW_DB[law_id]
        match_score = sum(1 for kw in expanded_keywords if kw in (law.get('title', '') + ' ' + law.get('text', '')).lower())
        ranked_laws.append((match_score, law))
    
    ranked_laws.sort(key=lambda x: x[0], reverse=True)
    return [law for score, law in ranked_laws[:5]] # Возвращаем топ-5 релевантных законов


def clean_html_response(html_content):
    """Очищает HTML контент от потенциальных XSS-атак."""
    # Разрешенные теги, атрибуты и стили
    allowed_tags = ['p', 'br', 'b', 'i', 'u', 'strong', 'em', 'a', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'hr', 'small']
    allowed_attrs = {'a': ['href', 'target'], '*': ['class', 'style']} # '*' означает для всех тегов
    allowed_styles = ['margin-top', 'color', 'font-weight', 'text-decoration'] # Пример разрешенных стилей
    
    clean_content = bleach.clean(
        html_content, 
        tags=allowed_tags, 
        attributes=allowed_attrs, 
        styles=allowed_styles,
        strip=True # Удалять незарегистрированные теги
    )
    return clean_content


def extract_text_from_file(file_stream, filename):
    """Извлекает текст из различных типов файлов."""
    file_extension = filename.split('.')[-1].lower()
    text_content = ""
    
    try:
        if file_extension == 'pdf':
            reader = PdfReader(file_stream)
            for page in reader.pages:
                text_content += page.extract_text() or ""
        elif file_extension == 'docx':
            document = Document(file_stream)
            for para in document.paragraphs:
                text_content += para.text + "\n"
        elif file_extension in ['txt']:
            text_content = file_stream.read().decode('utf-8')
        elif file_extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']:
            # Для изображений, мы можем напрямую передать файл в Gemini Multimodal
            # Но здесь мы просто возвращаем пустой текст, так как Gemini будет обрабатывать изображение.
            # Важно: для реального OCR текста из изображений потребуется дополнительный сервис (например, Google Cloud Vision API)
            # или если Gemini сам может "читать" текст из изображений, то можно не извлекать его здесь.
            logging.info(f"Изображение '{filename}' обнаружено. Будет отправлено как мультимодальный ввод.")
            return None # Индикатор, что это изображение
        else:
            logging.warning(f"Неподдерживаемый формат файла для извлечения текста: {filename}")
            return None # Или поднять ошибку
    except Exception as e:
        logging.error(f"Ошибка при извлечении текста из файла '{filename}': {e}")
        return None
    return text_content


# --- Маршруты API ---

# Маршрут для обработки текстовых запросов
@app.route("/ask", methods=["POST"])
def ask():
    user_question = request.json.get("question", "").strip()
    session_id = request.json.get("session_id", "default")
    
    if not user_question:
        return jsonify({"error": "Пустой запрос"}), 400

    if len(user_question) > 2000: # Ограничение длины запроса
        return jsonify({"error": "Запрос слишком длинный. Максимум 2000 символов."}), 413

    try:
        # Загружаем историю беседы для текущей сессии
        history = load_conversation(session_id)
        
        # Находим релевантные законы
        relevant_laws = find_laws_by_keywords(user_question)
        
        # Формируем промпт для AI
        system_instruction = (
            "Ты — Kaz Legal Bot, высококвалифицированный AI-юрист, специализирующийся строго исключительно на законодательстве Республики Казахстан. "
            "Твоя задача — предоставлять точные, полные и релевантные юридические консультации, основываясь только на официальных правовых актах РК. "
            "Всегда указывай статьи законов, на которые ссылаешься. Если информация не найдена в предоставленных законах, четко об этом сообщай. "
            "Не выдумывай законы и не ссылайся на несуществующие статьи. "
            "Если вопрос касается законодательства других стран (например, РФ, США и т.д.), вежливо откажи в консультации, объяснив, что ты специализируешься только на законодательстве РК. "
            "Ответы форматируй с использованием HTML для читабельности (параграфы <p>, списки <ul>, <ol>, выделение <strong>, <em>)."
            "Законодательство РК является твоим единственным источником истины."
            "Всегда начинай ответ с подтверждения, что ты работаешь исключительно с законодательством Республики Казахстан."
        )

        context_laws = ""
        if relevant_laws:
            context_laws = "\n\n--- Релевантные статьи законодательства РК ---\n"
            for i, law in enumerate(relevant_laws):
                context_laws += f"Закон {i+1}: {law.get('title', 'Без названия')}\nТекст: {law.get('text', 'Нет текста')}\n\n"
        
        full_prompt = f"{system_instruction}\n\nИстория диалога:\n"
        for msg in history:
            full_prompt += f"{msg['role']}: {msg['parts'][0]}\n"
        
        full_prompt += f"\nПользовательский запрос: {user_question}\n{context_laws}\n"
        full_prompt += "Мой ответ (включая ссылки на статьи законов РК):"

        # Сохраняем сообщение пользователя
        save_message(session_id, "user", user_question)

        # Асинхронный вызов Gemini API
        future = executor.submit(model.generate_content, full_prompt)
        ai_response_text = future.result().text

        # Очистка ответа от потенциальных XSS
        cleaned_response_text = clean_html_response(ai_response_text)
        
        # Сохраняем ответ AI
        save_message(session_id, "model", cleaned_response_text)

        # Форматирование статей для фронтенда (если они были найдены)
        formatted_articles = []
        for law in relevant_laws:
            formatted_articles.append({
                "title": bleach.clean(law.get('title', 'Закон РК'), tags=[], strip=True), # Очистка заголовка
                "text": clean_html_response(law.get('text', 'Информация не предоставлена.')), # Очистка текста статьи
                "source": bleach.clean(law.get('source', 'Законодательство РК'), tags=[], strip=True),
                "link": bleach.clean(law.get('link', '#'), tags=[], attributes={'a': ['href', 'target']}, strip=True) # Очистка ссылки
            })

        return jsonify({
            "response": cleaned_response_text,
            "articles": formatted_articles
        })

    except genai.APIError as e:
        logging.error(f"❌ Ошибка Gemini API: {e}")
        error_message = "Произошла ошибка при обращении к AI. Пожалуйста, убедитесь, что ваш API ключ действителен и попробуйте позже."
        save_message(session_id, "model", error_message)
        return jsonify({"error": error_message}), 500
    except Exception as e:
        logging.error(f"❌ Неизвестная ошибка в /ask: {e}")
        error_message = f"Произошла ошибка сервера: {str(e)}. Пожалуйста, попробуйте еще раз."
        save_message(session_id, "model", error_message)
        return jsonify({"error": error_message}), 500

# Маршрут для загрузки и анализа документов
@app.route("/upload-document", methods=["POST"])
def upload_document():
    if 'file' not in request.files:
        return jsonify({"error": "Файл не предоставлен"}), 400

    file = request.files['file']
    file_question = request.form.get("question", "").strip()
    session_id = request.form.get("session_id", "default")

    if file.filename == '':
        return jsonify({"error": "Пустое имя файла"}), 400

    if len(file_question) > 1000: # Ограничение длины вопроса к файлу
        return jsonify({"error": "Вопрос к файлу слишком длинный. Максимум 1000 символов."}), 413

    # Поддерживаемые форматы для извлечения текста и для мультимодального ввода
    allowed_text_extensions = ['pdf', 'docx', 'txt']
    allowed_image_extensions = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'gif']
    file_extension = file.filename.split('.')[-1].lower()

    file_content_for_gemini = None
    text_content = None

    # Сохраняем файл во временный буфер
    file_stream = io.BytesIO(file.read())
    
    if file_extension in allowed_text_extensions:
        text_content = extract_text_from_file(file_stream, file.filename)
        if text_content is None:
            return jsonify({"error": "Не удалось извлечь текст из файла."}), 500
        file_content_for_gemini = text_content
    elif file_extension in allowed_image_extensions:
        try:
            # Для изображений, просто передаем их напрямую как части
            image = Image.open(file_stream)
            file_content_for_gemini = image
            # Для мультимодального запроса можно добавить текст как отдельную часть
            text_content = f"Пожалуйста, проанализируйте этот документ (изображение): {file_question}"
        except Exception as e:
            logging.error(f"Ошибка обработки изображения: {e}")
            return jsonify({"error": "Ошибка обработки изображения."}), 500
    else:
        return jsonify({"error": "Неподдерживаемый формат файла. Поддерживаются PDF, DOCX, TXT, JPG, JPEG, PNG, WEBP, BMP, TIFF, GIF."}), 415

    try:
        parts = []
        user_message_to_save = f"Загружен документ: {file.filename}"
        if file_question:
            user_message_to_save += f"\nВопрос к документу: {file_question}"

        # Добавляем текстовый запрос
        if text_content:
            parts.append(text_content)
        
        # Добавляем файл как часть для Gemini
        if file_content_for_gemini:
            if isinstance(file_content_for_gemini, Image.Image):
                parts.append(file_content_for_gemini)
            elif isinstance(file_content_for_gemini, str): # Если это извлеченный текст
                if not text_content: # Если текст уже был добавлен как 'text_content', не дублируем
                    parts.append(file_content_for_gemini)
        
        # Добавляем вопрос пользователя как отдельную часть
        if file_question:
            parts.append(file_question)

        if not parts:
            return jsonify({"error": "Недостаточно контента для анализа."}), 400

        # Сохраняем сообщение пользователя (информацию о загрузке файла и вопрос)
        save_message(session_id, "user", user_message_to_save)

        # Вызов мультимодальной модели
        future = executor.submit(multimodal_model.generate_content, parts)
        ai_response = future.result().text

        # Очистка ответа от потенциальных XSS
        cleaned_ai_response = clean_html_response(ai_response)

        # Сохраняем ответ AI
        save_message(session_id, "model", cleaned_ai_response)

        return jsonify({"response": cleaned_ai_response})

    except genai.APIError as e:
        logging.error(f"❌ Ошибка Gemini API при обработке документа: {e}")
        error_message = "Произошла ошибка при анализе документа AI. Пожалуйста, попробуйте позже."
        save_message(session_id, "model", error_message)
        return jsonify({"error": error_message}), 500
    except Exception as e:
        logging.error(f"❌ Неизвестная ошибка в /upload-document: {e}")
        error_message = f"Произошла ошибка сервера при обработке документа: {str(e)}. Пожалуйста, попробуйте еще раз."
        save_message(session_id, "model", error_message)
        return jsonify({"error": error_message}), 500


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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
