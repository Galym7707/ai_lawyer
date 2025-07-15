from memory import init_db, save_message, load_conversation, delete_conversation, get_all_sessions_summary_mongo
from flask import Flask, request, jsonify, Response, stream_with_context
import google.generativeai as genai
import os
import json
import re
from flask_cors import CORS
import bleach
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import io
from docx import Document
from PyPDF2 import PdfReader
import logging
from lxml import html
from dotenv import load_dotenv
from helpers import expand_keywords, build_snippet
import unittest

# Load environment variables
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16 MB
CORS(app, origins=os.getenv('CORS_ORIGINS', 'https://ai-lawyer-tau.vercel.app,http://localhost:5000,http://127.0.0.1:5000').split(','))

# Инициализация AI и Базы Законов
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    logging.error("❌ GEMINI_API_KEY не установлен. Приложение не может запуститься.")
    raise EnvironmentError("GEMINI_API_KEY is not set.")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "text/plain", "temperature": 0.7})
vision_model = genai.GenerativeModel('gemini-1.5-flash')

LAW_DB = []
LAW_INDEX = {}
LEGAL_SYNONYMS = {
    # ... (your existing LEGAL_SYNONYMS dictionary, unchanged)
}

MONGO_URI = os.getenv("MONGO_URI")
if MONGO_URI:
    init_db()
else:
    logging.error("❌ Ошибка: Переменная окружения MONGO_URI не установлена. Подключение к MongoDB невозможно.")

executor = ThreadPoolExecutor(max_workers=4)

def load_law_db(path="laws/kazakh_laws_db.json"):
    global LAW_DB
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            LAW_DB = json.load(f)
        logging.info(f"✅ Загружено {len(LAW_DB)} статей из базы законов.")
        build_law_index()
    else:
        logging.warning(f"⚠️ База законов не найдена по пути: {path}. Поиск будет ограничен.")

load_law_db()

def validate_session_id(session_id):
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', session_id))

def clean_and_format_html(text):
    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\s*\n\s*\n\s*', '\n\n', text).strip()
    text = re.sub(r'\s+', ' ', text)
    
    # Исправляем разбитые слова
    text = re.sub(r'(\w+)\s+(\w{1,3})\b', r'\1\2', text)
    text = text.replace('руководи телю', 'руководителю')
    text = text.replace('свидетель ские', 'свидетельские')
    text = text.replace('скан-копи ю', 'скан-копию')
    text = text.replace('обратит ься', 'обратиться')
    
    # Разбиваем текст на строки
    lines = text.split('\n\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Проверяем, является ли это заголовком
        if re.match(r'^[А-Я][А-Яа-я\s]+$', line.strip()) and not line.startswith('-'):
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            formatted_lines.append(f'<h3>{line}</h3>')
            continue
            
        # Проверяем, является ли это началом списка
        if line.startswith('-') or ':' in line:
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            # Удаляем начальный дефис
            line = line.lstrip('- ').strip()
            if ':' in line and len(line.split(':', 1)) > 1:
                parts = line.split(':', 1)
                formatted_lines.append(f'<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>')
            else:
                formatted_lines.append(f'<li>{line}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            formatted_lines.append(f'<p>{line}</p>')
    
    if in_list:
        formatted_lines.append('</ul>')
    
    result = '\n'.join(formatted_lines)
    
    # Удаляем пустые теги и исправляем вложенные пробелы
    result = re.sub(r'<p>\s*</p>', '', result)
    result = re.sub(r'<p>\s*(<strong>[^<]+</strong>)\s*([^<]+)', r'<p>\1 \2</p>', result)
    
    return result

def validate_html(text):
    try:
        html.fromstring(text)
        return True
    except Exception as e:
        logging.warning(f"⚠️ Неверный HTML: {e}")
        return False

def sanitize_html_output(text):
    text = clean_and_format_html(text)
    text = post_process_ai_response(text)
    if not validate_html(text):
        logging.warning("⚠️ Исправление неверного HTML")
        text = f'<p>{text}</p>'
    allowed_tags = ['p', 'ul', 'li', 'h3', 'strong', 'em']
    allowed_attrs = {'strong': ['style']}
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attrs, strip=True)

def generate_response_stream(model, messages, session_id):
    ai_response_content = ""
    accumulated_text = ""
    try:
        for chunk in model.generate_content(messages, stream=True):
            if chunk.text:
                accumulated_text += chunk.text
                if re.search(r'</(p|ul|h3)>', accumulated_text) or len(accumulated_text) > 150:
                    cleaned_chunk = sanitize_html_output(accumulated_text)
                    if cleaned_chunk.strip() and not re.search(r'<[^>]+>', cleaned_chunk):
                        cleaned_chunk = f'<p>{cleaned_chunk}</p>'
                    ai_response_content += cleaned_chunk
                    yield cleaned_chunk
                    accumulated_text = ""
        if accumulated_text:
            cleaned_chunk = sanitize_html_output(accumulated_text)
            if cleaned_chunk.strip() and not re.search(r'<[^>]+>', cleaned_chunk):
                cleaned_chunk = f'<p>{cleaned_chunk}</p>'
            ai_response_content += cleaned_chunk
            yield cleaned_chunk
        save_message(session_id, "model", ai_response_content)
        logging.info(f"✅ Ответ AI сохранен для сессии {session_id}")
    except genai.types.BlockedPromptException as e:
        logging.error(f"❌ Запрос заблокирован: {e}")
        error_message = "<p>Извините, ваш запрос был заблокирован из-за потенциально неприемлемого контента.</p>"
        save_message(session_id, "model", error_message)
        yield error_message
    except Exception as e:
        logging.error(f"❌ Ошибка генерации ответа: {e}")
        error_message = "<p>Произошла ошибка при генерации ответа. Попробуйте еще раз.</p>"
        save_message(session_id, "model", error_message)
        yield error_message

def build_law_index():
    global LAW_INDEX
    LAW_INDEX = {}
    for article in LAW_DB:
        content_lower = article.get('content', '').lower()
        title_lower = article.get('title', '').lower()
        words = set(re.findall(r'\b\w+\b', content_lower + " " + title_lower))
        for word in words:
            if word not in LAW_INDEX:
                LAW_INDEX[word] = []
            LAW_INDEX[word].append(article)

def find_relevant_laws(query: str) -> list:
    if not LAW_INDEX:
        build_law_index()
    query_lower = query.lower()
    query_keywords = set(re.findall(r'\b\w+\b', query_lower))
    expanded_keywords = expand_keywords(query_keywords, LEGAL_SYNONYMS)

    relevant_articles = []
    seen_articles = set()
    for kw in expanded_keywords:
        for article in LAW_INDEX.get(kw, []):
            article_id = article.get('id', article.get('title', ''))
            if article_id not in seen_articles:
                snippet = build_snippet(article.get('content', ''), expanded_keywords)
                relevant_articles.append({
                    "title": article.get('title', 'Без названия'),
                    "link": article.get('link', '#'),
                    "snippet": snippet
                })
                seen_articles.add(article_id)

    relevant_articles.sort(key=lambda x: sum(kw in x['snippet'].lower() for kw in expanded_keywords), reverse=True)
    return relevant_articles[:5]

def process_file_content(file_stream, mimetype):
    text_content = ""
    try:
        if mimetype == 'application/pdf':
            reader = PdfReader(file_stream)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content += extracted + "\n"
        elif mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            document = Document(file_stream)
            for paragraph in document.paragraphs:
                text_content += paragraph.text + "\n"
        elif mimetype.startswith('image/'):
            image = Image.open(file_stream)
            response = vision_model.generate_content(
                ["Опиши этот документ или изображение. Извлеки весь текст и информацию, которая может быть полезна для юриста."],
                image=image
            )
            text_content = response.text
        elif mimetype.startswith('text/'):
            text_content = file_stream.read().decode('utf-8', errors='ignore')
        else:
            logging.warning(f"⚠️ Неподдерживаемый тип файла: {mimetype}")
            return None
    except PyPDF2.errors.PdfReadError as e:
        logging.error(f"❌ Ошибка чтения PDF: {e}")
        return None
    except PIL.UnidentifiedImageError as e:
        logging.error(f"❌ Ошибка обработки изображения: {e}")
        return None
    except Exception as e:
        logging.error(f"❌ Ошибка при обработке файла {mimetype}: {e}")
        return None
    return text_content  # Fixed typo: text_contentt -> text_content

@app.route("/ask", methods=["POST"])
def ask_route():
    logging.info("🚀 Обработка запроса на /ask")
    try:
        data = request.get_json()
        user_question = data.get("question", "")
        session_id = data.get("session_id", "default")

        if not validate_session_id(session_id):
            return jsonify({"error": "Недопустимый session_id"}), 400

        if not user_question:
            return jsonify({"error": "Пустой вопрос"}), 400

        history = load_conversation(session_id)
        full_history = history + [{"role": "user", "parts": [user_question]}]

        relevant_laws = find_relevant_laws(user_question)
        law_context = ""
        if relevant_laws:
            law_context = "<ul>"
            for law in relevant_laws:
                law_context += f"<li><strong>{law['title']}</strong>: {law['snippet']}</li>"
            law_context += "</ul>"

        system_instruction = """
        Ты - ИИ-юрист, специализирующийся исключительно на законодательстве Республики Казахстан.
        Твоя задача — давать точные, полные и основанные на законодательстве ответы.
        Всегда сначала дай четкую юридическую оценку и сразу напиши, что делать и куда обращаться.
        Ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.

        КРИТИЧЕСКИ ВАЖНО: Форматируй ответы ТОЛЬКО в чистом HTML, используя <p> для абзацев, <ul><li> для списков, <h3> для заголовков, <strong> для выделения текста. НИКОГДА не используй Markdown, звездочки (* или **), или plain text. Пример:

        <h3>Юридическая оценка ситуации</h3>
        <p><strong>Юридическая оценка:</strong> Увольнение без законных оснований является нарушением.</p>
        <ul>
        <li><strong>Действие:</strong> Обратитесь в суд.</li>
        </ul>

        Если данных недостаточно:
        <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
        <ul>
        <li><strong>Пункт 1:</strong> Описание...</li>
        </ul>

        Экстренные контакты:
        <p><strong>В экстренных случаях обращайтесь:</strong></p>
        <ul>
        <li>Полиция: <strong>102</strong></li>
        <li>Единый номер экстренных служб: <strong>112</strong></li>
        </ul>

        Всегда следуй этим правилам:
        1. Начинай с юридической оценки и рекомендаций, даже если данных мало.
        2. Задавай уточняющие вопросы в формате HTML-списка, если нужно.
        3. Используй официальный, но понятный язык.
        4. Не используй звездочки для цензуры; перефразируй, если нужно.
        5. Предоставляй практические советы и шаблоны документов, если применимо.

        {law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях, но предупреждай, что информация требует проверки по актуальным законам РК."}
        """

        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history

        return Response(stream_with_context(generate_response_stream(model, messages_for_model, session_id)), mimetype='text/html')
    except Exception as e:
        logging.error(f"❌ Ошибка в /ask: {e}")
        return jsonify({"error": f"Ошибка сервера при обработке запроса: {str(e)}"}), 500

@app.route("/upload-document", methods=["POST"])
def upload_document_route():
    logging.info("🚀 Обработка запроса на /upload-document")
    try:
        user_file = request.files.get('file')
        user_question = request.form.get("question", "")
        session_id = request.form.get("session_id", "default")

        if not validate_session_id(session_id):
            return jsonify({"error": "Недопустимый session_id"}), 400

        if not user_file:
            return jsonify({"error": "Файл не предоставлен"}), 400

        file_mimetype = user_file.mimetype
        logging.info(f"📁 Получен файл: {user_file.filename} с MIME-типом: {file_mimetype}")

        file_content_text = process_file_content(user_file.stream, file_mimetype)

        if file_content_text is None:
            return jsonify({"error": "Неподдерживаемый или поврежденный тип файла."}), 400

        file_message_content = f"Пользователь загрузил документ ({user_file.filename}). Содержимое документа:\n```\n{file_content_text[:2000]}...\n```"
        
        history = load_conversation(session_id)
        full_history = history + [{"role": "user", "parts": [file_message_content]}]
        if user_question:
            full_history.append({"role": "user", "parts": [user_question]})

        combined_text_for_search = file_content_text + " " + user_question
        relevant_laws = find_relevant_laws(combined_text_for_search)

        law_context = ""
        if relevant_laws:
            law_context = "<ul>"
            for law in relevant_laws:
                law_context += f"<li><strong>{law['title']}</strong>: {law['snippet']}</li>"
            law_context += "</ul>"
            logging.info(f"🔍 Найдены релевантные законы для документа и запроса.")

        system_instruction = """
        Ты - ИИ-юрист, специализирующийся исключительно на законодательстве Республики Казахстан.
        Твоя задача — давать точные, полные и основанные на законодательстве ответы.
        Всегда сначала дай четкую юридическую оценку и сразу напиши, что делать и куда обращаться.
        Ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.

        КРИТИЧЕСКИ ВАЖНО: Форматируй ответы ТОЛЬКО в чистом HTML, используя <p> для абзацев, <ul><li> для списков, <h3> для заголовков, <strong> для выделения текста. НИКОГДА не используй Markdown, звездочки (* или **), или plain text. Пример:

        <h3>Юридическая оценка ситуации</h3>
        <p><strong>Юридическая оценка:</strong> Увольнение без законных оснований является нарушением.</p>
        <ul>
        <li><strong>Действие:</strong> Обратитесь в суд.</li>
        </ul>

        Если данных недостаточно:
        <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
        <ul>
        <li><strong>Пункт 1:</strong> Описание...</li>
        </ul>

        Экстренные контакты:
        <p><strong>В экстренных случаях обращайтесь:</strong></p>
        <ul>
        <li>Полиция: <strong>102</strong></li>
        <li>Единый номер экстренных служб: <strong>112</strong></li>
        </ul>

        Всегда следуй этим правилам:
        1. Начинай с юридической оценки и рекомендаций, даже если данных мало.
        2. Задавай уточняющие вопросы в формате HTML-списка, если нужно.
        3. Используй официальный, но понятный язык.
        4. Не используй звездочки для цензуры; перефразируй, если нужно.
        5. Предоставляй практические советы и шаблоны документов, если применимо.

        **КОНТАКТЫ ЭКСТРЕННЫХ СЛУЖБ И СПРАВОЧНЫЕ ТЕЛЕФОНЫ (КАЗАХСТАН, АЛМАТЫ):**
            * Противопожарная служба: 101
            * Полиция: 102
            * Скорая медицинская помощь: 103
            * Аварийная служба газа: 104
            * Служба спасения: 109
            * Экстренный вызов: 112
            * АЛМАТЫЛИФТ: +7 (727) 397 77 70, +7(727) 397 79 26
            * ГКП на ПХВ акимата города Алматы "Алматы Қала Жарық": +7 (727) 390 20 40, +7 (727) 390 20 60, + 7 771 718 24 39/56
            * ГКП "Алматы Су": +7 727 274-66-66, +7 727 3 777 444
            * Единый контакт-центр по вопросам оказания государственных услуг: 8 800 080 7777 (1414)
            * Бесплатная справочная служба: +7 727 333 07 07
            * Платная справочная служба Казахтелеком: 169
            * Заказы междугородних и международных переговоров: 171
            * Аэропорт (Алматы): +7 (727) 222 15 51, *727 с мобильного
            * ЖД вокзал «Алматы 1» и «Алматы 2»: 105
            * Автовокзал «Саяхат»: +7 727 380 74 44
            * Автовокзал «Сайран»: +7 727 396 70 63
            * Стол находок ДВД г. Алматы: +7 727 292 70 84
            * Бюро находок «ПАНиКа»: +7 727 390 99 66, +7 747 390 99 66
            * Национальный телефон доверия для детей и молодежи: 150
            * Телефон доверия КНБ: 110
            * Контакт-центр судебных органов: 1401
            * Единый телефон доверия МВД: 1402
            * Телефон доверия Министерства сельского хозяйства РК: +7 7172 555 763
            * Телефон доверия Агентства РК по делам противодействию коррупции: 1424
            * Департамент полиции (Алматы): +7 727 254 40 92, +7 727 254 40 42
            * УП Алатауского района: +7 727 227 55 02, +7 727 227 55 28
            * УП Алмалинского района: +7 727 254 46 12
            * УП Ауэзовского района: +7 727 298 53 02, +7 727 298 53 05 (Отдел полиции при УП Ауэзовского района)
            * УП Бостандыкского района: +7 727 254 47 02
            * УП Жетысуского района: +7 727 254 49 02, +7 727 254 49 11
            * УП Медеуского района: +7 727 254 48 02, +7 727 254 48 72 (Отдел полиции при УП Медеуского района)
            * УП Турксибского района: +7 727 298 54 02, +7 727 290 32 27, +7 727 298 54 62 (Отдел полиции при УП Турксибского района)
            * Департамент по чрезвычайным ситуациям г. Алматы: +7 727 394 57 39
            * Районные отделы по ЧС (Алматы):
                * Алмалинский: +7 727 279 48 01, +7 727 390 75 30
                * Ауэзовский: +7 727 226 99 15
                * Бостандыкский: +7 727 337 87 16
                * Жетысуский: +7 727 233 33 45
                * Медеуский: +7 727 272 48 93
                * Наурызбайский: +7 727 305 05 01
                * Турксибский: +7 727 251 59 99
            * Казселезащита, эксплуатационное управление: +7 727 269 09 64
            * Республиканский опертивно-спасательный отряд: +7 727 372 15 60
            * Контакт-центр Фонда «Даму»: 1408
            * Контакт-центр Государственный центр по выплате пенсий: 1411
            * Контакт-центр Комитет государственных доходов МФ РК: 1412
            * Контакт-центр ЕНПФ: 1418
            * Горячая линия по земельному вопросу: 1434
            * Центр поддержки потребителей Казахтелеком: 160
            * Централизованное бюро ремонта Казахтелеком: 165
            * Телефон доверия по борьбе с торговлей людьми: 116-16
            * Банки (контакт-центры):
                * ATF: 8 8000 800 283 (2424)
                * AsiaCredit Bank: 3311
                * Сбербанк: +7 727 250 30 20 (5030)
                * VTB: 5050
                * ForteBank: 7575
                * Capital Bank Kazakhstan: 6161
                * First Heartland Jýsan Bank: 7711
                * Eurasian Bank: +7 727 332 77 22
                * Kaspi: 9999
                * Altyn Bank: +7 727 35 65 777
                * Жилстройсбербанк Казахстана: 300
                * Bank RBK: 7888
                * Al Hilal Bank: 2330
                * Halyk Bank: 7111
                * Nurbank: 2552
        
        6.  **Язык и тон:** Используй официальный, но понятный язык. Будь вежливым и профессиональным.
        7.  **Цензура:** **Не используй звездочки (*) для цензуры.** Если какой-то термин считается чувствительным, постарайся перефразировать ответ, либо, если это юридический термин, используй его как есть, так как это важно для юридической точности.
        {law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях, но предупреждай, что информация требует проверки по актуальным законам РК."}
        """

        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history

        return Response(stream_with_context(generate_response_stream(model, messages_for_model, session_id)), mimetype='text/html')
    except Exception as e:
        logging.error(f"❌ Ошибка в /upload-document: {e}")
        return jsonify({"error": f"Ошибка сервера при обработке документа: {str(e)}"}), 500

@app.route('/get-all-sessions-summary', methods=["GET"])
def get_all_sessions_summary_route():
    logging.info("🚀 Обработка запроса на /get-all-sessions-summary")
    try:
        sessions_summary = get_all_sessions_summary_mongo()
        if sessions_summary:
            return jsonify({"sessions": sessions_summary}), 200
        else:
            return jsonify({"sessions": []}), 200
    except Exception as e:
        return jsonify({"error": f"Ошибка при получении сводки сессий: {str(e)}"}), 500

@app.route('/get-history', methods=["GET"])
def get_history_route():
    logging.info("🚀 Обработка запроса на /get-history")
    try:
        session_id = request.args.get("session_id", "default")
        if not validate_session_id(session_id):
            return jsonify({"error": "Недопустимый session_id"}), 400
        history = load_conversation(session_id)
        formatted = []
        for msg in history:
            if isinstance(msg["parts"], list):
                if isinstance(msg["parts"][0], dict) and "text" in msg["parts"][0]:
                    content = msg["parts"][0]["text"]
                else:
                    content = msg["parts"][0]
            else:
                content = msg["parts"]
            formatted.append({"role": msg["role"], "content": content})
        return jsonify({"history": formatted}), 200
    except Exception as e:
        return jsonify({"error": f"Ошибка при получении истории: {str(e)}"}), 500

def post_process_ai_response(response_text):
    # Удаляем двойные пробелы и лишние переносы
    response_text = re.sub(r'\s*\n\s*\n\s*', '\n\n', response_text).strip()
    response_text = re.sub(r'\s+', ' ', response_text)
    
    # Исправляем разбитые слова
    response_text = re.sub(r'(\w+)\s+(\w{1,3})\b', r'\1\2', response_text)
    response_text = response_text.replace('руководи телю', 'руководителю')
    response_text = response_text.replace('свидетель ские', 'свидетельские')
    response_text = response_text.replace('скан-копи ю', 'скан-копию')
    response_text = response_text.replace('обратит ься', 'обратиться')
    
    # Если текст не содержит HTML, преобразуем в HTML
    if not re.search(r'<[^>]+>', response_text):
        lines = response_text.split('\n\n')
        formatted_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Проверяем заголовки
            if re.match(r'^[А-Я][А-Яа-я\s]+$', line.strip()) and not line.startswith('-'):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<h3>{line}</h3>')
                continue
                
            # Проверяем списки
            if line.startswith('-') or ':' in line:
                if not in_list:
                    formatted_lines.append('<ul>')
                    in_list = True
                line = line.lstrip('- ').strip()
                if ':' in line and len(line.split(':', 1)) > 1:
                    parts = line.split(':', 1)
                    formatted_lines.append(f'<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>')
                else:
                    formatted_lines.append(f'<li>{line}</li>')
            else:
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<p>{line}</p>')
        
        if in_list:
            formatted_lines.append('</ul>')
        response_text = '\n'.join(formatted_lines)
    
    return response_text

class TestHTMLFormatting(unittest.TestCase):
    def test_clean_and_format_html(self):
        input_text = """
        Юридическая оценка ситуации

        Увольнение без законных оснований является нарушением.

        Что делать:
        - Запросить документы
        - Обратиться в суд
        """
        expected = """
        <h3>Юридическая оценка ситуации</h3>
        <p>Увольнение без законных оснований является нарушением.</p>
        <h3>Что делать</h3>
        <ul>
        <li>Запросить документы</li>
        <li>Обратиться в суд</li>
        </ul>
        """
        result = clean_and_format_html(input_text)
        self.assertEqual(result.strip(), expected.strip())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
