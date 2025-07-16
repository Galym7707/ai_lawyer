from memory import init_db, save_message, load_conversation, delete_conversation, get_all_sessions_summary_mongo
from flask import Flask, request, jsonify, Response, stream_with_context, make_response
import google.generativeai as genai
import os
import json
import re
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
import jamspell
import unittest

# Load environment variables
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16 MB

# Custom CORS Middleware
cors_origins = os.getenv('CORS_ORIGINS', 'https://ai-lawyer-tau.vercel.app,http://localhost:5000,http://127.0.0.1:5000').split(',')
logging.info(f"✅ CORS configured for origins: {cors_origins}")

def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    if origin in cors_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = cors_origins[0]  # Fallback to primary origin
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = '86400'
    logging.info(f"Response headers: {response.headers}")
    return response

@app.after_request
def apply_cors(response):
    return add_cors_headers(response)

@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    response = make_response()
    return add_cors_headers(response)

# Инициализация AI и Базы Законов
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    logging.error("❌ GEMINI_API_KEY не установлен. Приложение не может запуститься.")
    raise EnvironmentError("GEMINI_API_KEY is not set.")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "text/plain", "temperature": 0.7})
vision_model = genai.GenerativeModel('gemini-1.5-flash')

# Инициализация JamSpell для коррекции текста
try:
    jsp = jamspell.TSpellCorrector()
    if not jsp.LoadLangModel('ru.bin'):
        logging.error("❌ Не удалось загрузить модель JamSpell ru.bin. Убедитесь, что файл присутствует.")
        raise FileNotFoundError("ru.bin not found")
    logging.info("✅ Модель JamSpell успешно загружена.")
except Exception as e:
    logging.error(f"❌ Ошибка при загрузке JamSpell: {e}")
    raise

LAW_DB = []
LAW_INDEX = {}
LEGAL_SYNONYMS = {
    'увольнение': ['уволен', 'увольняет', 'сокращение', 'расторжение договора', 'прекращение трудового договора', 'расчет', 'увольнение'],
    'отпуск': ['отпускные', 'ежегодный отпуск', 'трудовой отпуск', 'больничный', 'декретный отпуск'],
    'зарплата': ['заработная плата', 'оплата труда', 'выплата', 'аванс', 'расчет', 'оклад', 'премия'],
    'трудовой договор': ['трудовой контракт', 'договор', 'соглашение о труде', 'контракт'],
    'работодатель': ['компания', 'фирма', 'предприятие', 'начальник', 'руководство', 'организация'],
    'работник': ['сотрудник', 'персонал', 'служащий', 'подчиненный'],
    'ИП': ['индивидуальный предприниматель', 'предприниматель', 'ИПшник', 'частник'],
    'УСН': ['упрощенная система налогообложения', 'упрощенка'],
    'налог': ['налоги', 'налоговый', 'сбор', 'пошлина', 'НДС', 'КПН', 'ИПН', 'социальный налог', 'отчисления', 'взносы'],
    'ЕНП': ['единый совокупный платеж'],
    'патент': ['специальный налоговый режим на основе патента'],
    'декларация': ['налоговая декларация', 'отчетность'],
    'срок': ['сроки', 'период', 'дата'],
    'штраф': ['пени', 'взыскание'],
    'развод': ['расторжение брака', 'развод', 'алименты', 'раздел имущества'],
    'брак': ['женитьба', 'семейный союз', 'супружество'],
    'алименты': ['выплаты на ребенка', 'содержание'],
    'имущество': ['недвижимость', 'активы', 'собственность'],
    'кража': ['хищение', 'воровство'],
    'мошенничество': ['обман', 'афера'],
    'преступление': ['правонарушение', 'уголовное дело'],
    'наказание': ['срок', 'тюрьма', 'штраф', 'лишение свободы'],
    'нарушение': ['проступок', 'правонарушение'],
    'протокол': ['административный протокол'],
    'договор': ['контракт', 'соглашение'],
    'возмещение ущерба': ['компенсация', 'возмещение убытков'],
    'иск': ['исковое заявление', 'судебный иск'],
    'собственность': ['право собственности', 'имущество'],
    'закон': ['кодекс', 'нормативный акт', 'постановление', 'правила'],
    'статья': ['пункт', 'часть', 'подпункт'],
    'суд': ['судебный орган', 'правосудие', 'истец', 'ответчик'],
    'жалоба': ['обращение', 'заявление', 'петиция'],
    'консультация': ['совет', 'помощь', 'разъяснение'],
    'документ': ['бумага', 'справка', 'акт', 'удостоверение'],
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
    text = re.sub(r'\s*\n\s*\n\s*', '\n\n', text).strip()
    text = re.sub(r'\s+', ' ', text)
    text = jsp.FixFragment(text)
    lines = text.split('\n\n')
    formatted_lines = []
    in_list = False
    expected_sections = {
        'юридическая оценка': 'Юридическая оценка ситуации',
        'действие': 'Действие',
        'рекомендации': 'Рекомендации',
        'необходимая информация': 'Необходимая информация',
        'экстренные контакты': 'Экстренные контакты'
    }
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^SECTION:\s*[А-Я][А-Яа-я\s]+$', line.strip()) or line.strip().lower() in [k.lower() for k in expected_sections]:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            heading = line.replace('SECTION:', '').strip()
            formatted_lines.append(f'<h3>{expected_sections.get(heading.lower(), heading)}</h3>')
            if heading.lower() == 'необходимая информация':
                formatted_lines.append('<p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>')
            elif heading.lower() == 'экстренные контакты':
                formatted_lines.append('<p><strong>В экстренных случаях обращайтесь:</strong></p>')
            continue
        if line.startswith('LIST_ITEM:') or line.startswith('-') or re.match(r'^\d+\.\s+', line):
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            line = re.sub(r'^\d+\.\s+', '', line.lstrip('- ').strip())
            line = line.replace('LIST_ITEM:', '').strip()
            if ':' in line and len(line.split(':', 1)) > 1:
                parts = line.split(':', 1)
                label = parts[0].strip()
                if 'рекомендации' in formatted_lines[-1].lower():
                    label = {
                        'напишите работодателю': 'Письменное требование',
                        'обратитесь в территориальное': 'Обращение в инспекцию труда',
                        'подготовьте исковое': 'Исковое заявление',
                        'собирайте все': 'Документы',
                        'сообщите о случившемся': 'Уведомление родителей',
                        'обратитесь в полицию': 'Обращение в полицию',
                        'обратитесь в медицинское учреждение': 'Медицинский осмотр',
                        'сохраните все доказательства': 'Сбор доказательств',
                        'по возможности соберите': 'Свидетельские показания',
                        'рассмотрите возможность': 'Жалоба в органы образования'
                    }.get(label.lower(), label)
                elif 'необходимая информация' in formatted_lines[-1].lower():
                    label = {
                        'ваш трудовой договор': 'Трудовой договор',
                        'точная сумма задолженности': 'Сумма задолженности',
                        'дата последней выплаты': 'Дата последней выплаты',
                        'наличие каких-либо соглашений': 'Соглашения о задержке',
                        'причины задержки': 'Причины задержки',
                        'подробное описание инцидента': 'Описание инцидента',
                        'степень тяжести полученных травм': 'Степень травм',
                        'свидетели': 'Свидетели',
                        'данные об учителе': 'Данные об учителе',
                        'данные о школе': 'Данные о школе'
                    }.get(label.lower(), label)
                formatted_lines.append(f'<li><strong>{label}:</strong> {parts[1].strip()}</li>')
            else:
                formatted_lines.append(f'<li>{line}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            if 'юридическая оценка' in formatted_lines[-1].lower():
                formatted_lines.append(f'<p><strong>Юридическая оценка:</strong> {line}</p>')
            else:
                formatted_lines.append(f'<p>{line}</p>')
    if in_list:
        formatted_lines.append('</ul>')
    result = '\n'.join(formatted_lines)
    result = re.sub(r'<p>\s*</p>', '', result)
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
    if not validate_html(text):
        logging.warning("⚠️ Исправление неверного HTML")
        text = f'<p>{text}</p>'
    allowed_tags = ['p', 'ul', 'li', 'h3', 'strong']
    allowed_attrs = {'strong': ['style']}
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attrs, strip=True)

def generate_response_stream(model, messages, session_id):
    ai_response_content = ""
    accumulated_text = ""
    try:
        for chunk in model.generate_content(messages, stream=True):
            if chunk.text:
                accumulated_text += chunk.text
                if re.search(r'\n\n', accumulated_text) or len(accumulated_text) > 150:
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
    return text_content

@app.route("/ask", methods=["POST"])
def ask_route():
    logging.info("🚀 Обработка запроса на /ask")
    try:
        data = request.get_json()
        user_question = data.get("question", "")
        session_id = data.get("session_id", "default")
        if not validate_session_id(session_id):
            response = jsonify({"error": "Недопустимый session_id"})
            return add_cors_headers(response), 400
        if not user_question:
            response = jsonify({"error": "Пустой вопрос"})
            return add_cors_headers(response), 400
        history = load_conversation(session_id)
        full_history = history + [{"role": "user", "parts": [user_question]}]
        relevant_laws = find_relevant_laws(user_question)
        law_context = ""
        if relevant_laws:
            law_context = "SECTION: Релевантные законы\n"
            for law in relevant_laws:
                law_context += f"LIST_ITEM: {law['title']}: {law['snippet']}\n"
            law_context += "\n"
        system_instruction = """
        Ты - ИИ-юрист, специализирующийся исключительно на законодательстве Республики Казахстан.
        Твоя задача — давать точные, полные и основанные на законодательстве ответы в виде простого текста.
        Форматируй ответ с четкими разделами, используя маркер "SECTION:" для каждого заголовка и "LIST_ITEM:" для каждого элемента списка. НИКОГДА не пропускай эти маркеры.
        Всегда начинай с раздела "SECTION: Юридическая оценка" и укажи, нарушено ли право, какая ответственность, какие законы применяются.
        Затем добавь "SECTION: Действие" с рекомендациями, что делать и куда обращаться, даже если данных мало.
        Если применимо, добавь "SECTION: Рекомендации" с подробными шагами, используя "LIST_ITEM:" для каждого пункта.
        Если данных недостаточно, добавь "SECTION: Необходимая информация" со списком вопросов, каждый с "LIST_ITEM:".
        Всегда заканчивай разделом "SECTION: Экстренные контакты" с номерами:
        LIST_ITEM: Полиция: 102
        LIST_ITEM: Единый номер экстренных служб: 112
        Ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
        Используй официальный, но понятный язык. Не используй звездочки для цензуры; перефразируй, если нужно.
        Предоставляй практические советы и шаблоны документов, если применимо.
        НИКОГДА не используй HTML, Markdown, номера (1., 2.), или дефисы (-) для списков — только "SECTION:" и "LIST_ITEM:".
        Пример ответа:
        SECTION: Юридическая оценка
        Увольнение без законных оснований является нарушением.
        SECTION: Действие
        Обратитесь в суд.
        SECTION: Рекомендации
        LIST_ITEM: Направьте работодателю письменное требование.
        LIST_ITEM: Обратитесь в инспекцию труда.
        SECTION: Необходимая информация
        LIST_ITEM: Ваш трудовой договор: Предоставьте копию.
        LIST_ITEM: Приказ об увольнении: Укажите дату и причину.
        SECTION: Экстренные контакты
        LIST_ITEM: Полиция: 102
        LIST_ITEM: Единый номер экстренных служб: 112
        {law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях, но предупреждай, что информация требует проверки по актуальным законам РК."}
        """
        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history
        response = Response(stream_with_context(generate_response_stream(model, messages_for_model, session_id)), mimetype='text/html')
        return add_cors_headers(response)
    except Exception as e:
        logging.error(f"❌ Ошибка в /ask: {e}")
        response = jsonify({"error": f"Ошибка сервера при обработке запроса: {str(e)}"})
        return add_cors_headers(response), 500

@app.route("/upload-document", methods=["POST"])
def upload_document_route():
    logging.info("🚀 Обработка запроса на /upload-document")
    try:
        user_file = request.files.get('file')
        user_question = request.form.get("question", "")
        session_id = request.form.get("session_id", "default")
        if not validate_session_id(session_id):
            response = jsonify({"error": "Недопустимый session_id"})
            return add_cors_headers(response), 400
        if not user_file:
            response = jsonify({"error": "Файл не предоставлен"})
            return add_cors_headers(response), 400
        file_mimetype = user_file.mimetype
        logging.info(f"📁 Получен файл: {user_file.filename} с MIME-типом: {file_mimetype}")
        file_content_text = process_file_content(file_stream=user_file.stream, mimetype=file_mimetype)
        if file_content_text is None:
            response = jsonify({"error": "Неподдерживаемый или поврежденный тип файла."})
            return add_cors_headers(response), 400
        file_message_content = f"SECTION: Загруженный документ\nПользователь загрузил документ ({user_file.filename}). Содержимое документа:\n{file_content_text[:2000]}...\n"
        history = load_conversation(session_id)
        full_history = history + [{"role": "user", "parts": [file_message_content]}]
        if user_question:
            full_history.append({"role": "user", "parts": [user_question]})
        combined_text_for_search = file_content_text + " " + user_question
        relevant_laws = find_relevant_laws(combined_text_for_search)
        law_context = ""
        if relevant_laws:
            law_context = "SECTION: Релевантные законы\n"
            for law in relevant_laws:
                law_context += f"LIST_ITEM: {law['title']}: {law['snippet']}\n"
            law_context += "\n"
        system_instruction = """
        Ты - ИИ-юрист, специализирующийся исключительно на законодательстве Республики Казахстан.
        Твоя задача — давать точные, полные и основанные на законодательстве ответы в виде простого текста.
        Форматируй ответ с четкими разделами, используя маркер "SECTION:" для каждого заголовка и "LIST_ITEM:" для каждого элемента списка. НИКОГДА не пропускай эти маркеры.
        Всегда начинай с раздела "SECTION: Юридическая оценка" и укажи, нарушено ли право, какая ответственность, какие законы применяются.
        Затем добавь "SECTION: Действие" с рекомендациями, что делать и куда обращаться, даже если данных мало.
        Если применимо, добавь "SECTION: Рекомендации" с подробными шагами, используя "LIST_ITEM:" для каждого пункта.
        Если данных недостаточно, добавь "SECTION: Необходимая информация" со списком вопросов, каждый с "LIST_ITEM:".
        Всегда заканчивай разделом "SECTION: Экстренные контакты" с номерами:
        LIST_ITEM: Полиция: 102
        LIST_ITEM: Единый номер экстренных служб: 112
        Ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
        Используй официальный, но понятный язык. Не используй звездочки для цензуры; перефразируй, если нужно.
        Предоставляй практические советы и шаблоны документов, если применимо.
        НИКОГДА не используй HTML, Markdown, номера (1., 2.), или дефисы (-) для списков — только "SECTION:" и "LIST_ITEM:".
        Пример ответа:
        SECTION: Юридическая оценка
        Увольнение без законных оснований является нарушением.
        SECTION: Действие
        Обратитесь в суд.
        SECTION: Рекомендации
        LIST_ITEM: Направьте работодателю письменное требование.
        LIST_ITEM: Обратитесь в инспекцию труда.
        SECTION: Необходимая информация
        LIST_ITEM: Ваш трудовой договор: Предоставьте копию.
        LIST_ITEM: Приказ об увольнении: Укажите дату и причину.
        SECTION: Экстренные контакты
        LIST_ITEM: Полиция: 102
        LIST_ITEM: Единый номер экстренных служб: 112
        {law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях, но предупреждай, что информация требует проверки по актуальным законам РК."}
        """
        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history
        response = Response(stream_with_context(generate_response_stream(model, messages_for_model, session_id)), mimetype='text/html')
        return add_cors_headers(response)
    except Exception as e:
        logging.error(f"❌ Ошибка в /upload-document: {e}")
        response = jsonify({"error": f"Ошибка сервера при обработке документа: {str(e)}"})
        return add_cors_headers(response), 500

@app.route('/get-all-sessions-summary', methods=["GET"])
def get_all_sessions_summary_route():
    logging.info("🚀 Обработка запроса на /get-all-sessions-summary")
    try:
        sessions_summary = get_all_sessions_summary_mongo()
        response = jsonify({"sessions": sessions_summary if sessions_summary else []})
        return add_cors_headers(response), 200
    except Exception as e:
        logging.error(f"❌ Ошибка при получении сводки сессий: {str(e)}")
        response = jsonify({"error": f"Ошибка при получении сводки сессий: {str(e)}"})
        return add_cors_headers(response), 500

@app.route('/get-history', methods=["GET"])
def get_history_route():
    logging.info("🚀 Обработка запроса на /get-history")
    try:
        session_id = request.args.get("session_id", "default")
        if not validate_session_id(session_id):
            response = jsonify({"error": "Недопустимый session_id"})
            return add_cors_headers(response), 400
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
        response = jsonify({"history": formatted})
        return add_cors_headers(response), 200
    except Exception as e:
        logging.error(f"❌ Ошибка при получении истории: {str(e)}")
        response = jsonify({"error": f"Ошибка при получении истории: {str(e)}"})
        return add_cors_headers(response), 500

class TestHTMLFormatting(unittest.TestCase):
    def test_clean_and_format_html(self):
        input_text = """
        SECTION: Юридическая оценка
        Невыплата заработной платы является нарушением.
        SECTION: Действие
        Обратитесь в суд.
        SECTION: Рекомендации
        LIST_ITEM: Направьте работодателю письменное требование.
        LIST_ITEM: Обратитесь в инспекцию труда.
        SECTION: Необходимая информация
        LIST_ITEM: Ваш трудовой договор: Предоставьте копию.
        LIST_ITEM: Точная сумма задолженности: Укажите сумму.
        SECTION: Экстренные контакты
        LIST_ITEM: Полиция: 102
        LIST_ITEM: Единый номер экстренных служб: 112
        """
        expected = """
        <h3>Юридическая оценка ситуации</h3>
        <p><strong>Юридическая оценка:</strong> Невыплата заработной платы является нарушением.</p>
        <h3>Действие</h3>
        <p>Обратитесь в суд.</p>
        <h3>Рекомендации</h3>
        <ul>
        <li><strong>Письменное требование:</strong> Направьте работодателю письменное требование.</li>
        <li><strong>Обращение в инспекцию труда:</strong> Обратитесь в инспекцию труда.</li>
        </ul>
        <h3>Необходимая информация</h3>
        <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
        <ul>
        <li><strong>Трудовой договор:</strong> Предоставьте копию.</li>
        <li><strong>Сумма задолженности:</strong> Укажите сумму.</li>
        </ul>
        <h3>Экстренные контакты</h3>
        <p><strong>В экстренных случаях обращайтесь:</strong></p>
        <ul>
        <li><strong>Полиция:</strong> 102</li>
        <li><strong>Единый номер экстренных служб:</strong> 112</li>
        </ul>
        """
        result = clean_and_format_html(input_text)
        self.assertEqual(result.strip(), expected.strip())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
