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
    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\s*\n\s*\n\s*', '\n\n', text).strip()
    text = re.sub(r'\s+', ' ', text)
    
    # Исправляем разбитые слова
    text = re.sub(r'(\w+)\s+(\w{1,3})\b', r'\1\2', text)
    text = text.replace('услугис', 'услуги с')
    text = text.replace('стороныкак', 'стороны как')
    text = text.replace('законодательствоРК', 'законодательство РК')
    text = text.replace('запрещатьвам', 'запрещать вам')
    text = text.replace('вероисповеданиявыи', 'вероисповедания вы и')
    text = text.replace('одеждув', 'одежду в')
    text = text.replace('обучениеит', 'обучение и т')
    text = text.replace('Естьли', 'Есть ли')
    
    # Разбиваем текст на строки
    lines = text.split('\n\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Проверяем заголовки
        if re.match(r'^SECTION:\s*[А-Я][А-Яа-я\s]+$', line.strip()):
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            heading = line.replace('SECTION:', '').strip()
            formatted_lines.append(f'<h3>{heading}</h3>')
            continue
            
        # Проверяем списки (LIST_ITEM, дефисы, номера)
        if line.startswith('LIST_ITEM:') or line.startswith('-') or re.match(r'^\d+\.\s+', line):
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            line = re.sub(r'^\d+\.\s+', '', line.lstrip('- ').strip())  # Удаляем номера или дефисы
            line = line.replace('LIST_ITEM:', '').strip()
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
    text = post_process_ai_response(text)
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
            return jsonify({"error": "Недопустимый session_id"}), 400

        if not user_question:
            return jsonify({"error": "Пустой вопрос"}), 400

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
        Форматируй ответ с четкими разделами, используя маркеры "SECTION:" для заголовков и "LIST_ITEM:" для элементов списков.
        Всегда начинай с раздела "SECTION: Юридическая оценка" и укажи, нарушено ли право, какая ответственность, какие законы применяются.
        Затем добавь "SECTION: Действие" с рекомендациями, что делать и куда обращаться, даже если данных мало.
        Если применимо, добавь "SECTION: Рекомендации" с подробными шагами.
        Если данных недостаточно, добавь "SECTION: Необходимая информация" со списком вопросов, где каждый вопрос начинается с "LIST_ITEM:".
        Всегда заканчивай разделом "SECTION: Экстренные контакты" с номерами:
        LIST_ITEM: Полиция: 102
        LIST_ITEM: Единый номер экстренных служб: 112
        Ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
        Используй официальный, но понятный язык. Не используй звездочки для цензуры; перефразируй, если нужно.
        Предоставляй практические советы и шаблоны документов, если применимо.
        Не используй HTML или Markdown, только простой текст с маркерами SECTION: и LIST_ITEM:.

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
        Форматируй ответ с четкими разделами, используя маркеры "SECTION:" для заголовков и "LIST_ITEM:" для элементов списков.
        Всегда начинай с раздела "SECTION: Юридическая оценка" и укажи, нарушено ли право, какая ответственность, какие законы применяются.
        Затем добавь "SECTION: Действие" с рекомендациями, что делать и куда обращаться, даже если данных мало.
        Если применимо, добавь "SECTION: Рекомендации" с подробными шагами.
        Если данных недостаточно, добавь "SECTION: Необходимая информация" со списком вопросов, где каждый вопрос начинается с "LIST_ITEM:".
        Всегда заканчивай разделом "SECTION: Экстренные контакты" с номерами:
        LIST_ITEM: Полиция: 102
        LIST_ITEM: Единый номер экстренных служб: 112
        Ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
        Используй официальный, но понятный язык. Не используй звездочки для цензуры; перефразируй, если нужно.
        Предоставляй практические советы и шаблоны документов, если применимо.
        Не используй HTML или Markdown, только простой текст с маркерами SECTION: и LIST_ITEM:.

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

        При ответе строго следуй этим правилам:
    
        1.  Если для ответа недостаточно данных, сразу пиши: "Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:" — и далее четко и простым языком формулируй необходимые вопросы к клиенту списком.
            Будь как полноценный реальный юрист, которому клиент может полностью довериться. Никогда не говори пользователю, что ему нужно обратиться за полной информацией куда-то в ЦОН, к другому юристу либо иную организацию. Всю необходимую справочную и практическую информацию давай сам, максимально подробно и понятно.
        2.  Точность и актуальность: Отвечай максимально точно и полно, ссылаясь на конкретные статьи законов, нормативные акты или общепринятые юридические практики РК, если это возможно.
        3.  Уточняющие вопросы: Если вопрос нечеткий, слишком общий или требует конкретизации для применения норм РК, задавай уточняющие вопросы. Например: "Пожалуйста, уточните, какой аспект [тема] вас интересует в рамках законодательства РК (например, трудовой договор, испытательный срок, приказ о приеме на работу)?"
        4.  Практическая помощь:
            Шаблоны и образцы: Если запрос касается оформления документов (жалоба, заявление, договор, приказ и т.п.), и у тебя есть соответствующий шаблон или четкий алгоритм его составления в базе знаний, предложи его пользователю. Указывай, что это образец и может требовать адаптации.
            Полезные советы/лайфхаки: Предоставляй практические советы и рекомендации, помогающие пользователю в решении юридических вопросов, избегая типичных ошибок.
        5.  Экстренные контакты и справочная информация:
            Если вопрос явно или косвенно касается экстренных ситуаций, правонарушений, чрезвычайных происшествий или необходимости связаться с государственными органами/службами, предоставь соответствующие контактные данные.
            В случае необходимости, цитируй контакты из следующего списка. Указывай принадлежность контактов (Казахстан, Алматы) если это уместно.
        
            КОНТАКТЫ ЭКСТРЕННЫХ СЛУЖБ И СПРАВОЧНЫЕ ТЕЛЕФОНЫ (КАЗАХСТАН, АЛМАТЫ):
            Противопожарная служба: 101
            Полиция: 102
            Скорая медицинская помощь: 103
            Аварийная служба газа: 104
            Служба спасения: 109
            Экстренный вызов: 112
            АЛМАТЫЛИФТ: +7 (727) 397 77 70, +7(727) 397 79 26
            ГКП на ПХВ акимата города Алматы "Алматы Қала Жарық": +7 (727) 390 20 40, +7 (727) 390 20 60, + 7 771 718 24 39/56
            ГКП "Алматы Су": +7 727 274-66-66, +7 727 3 777 444
            Единый контакт-центр по вопросам оказания государственных услуг: 8 800 080 7777 (1414)
            Бесплатная справочная служба: +7 727 333 07 07
            Платная справочная служба Казахтелеком: 169
            Заказы междугородних и международных переговоров: 171
            Аэропорт (Алматы): +7 (727) 222 15 51, *727 с мобильного
            ЖД вокзал «Алматы 1» и «Алматы 2»: 105
            Автовокзал «Саяхат»: +7 727 380 74 44
            Автовокзал «Сайран»: +7 727 396 70 63
            Стол находок ДВД г. Алматы: +7 727 292 70 84
            Бюро находок «ПАНиКа»: +7 727 390 99 66, +7 747 390 99 66
            Национальный телефон доверия для детей и молодежи: 150
            Телефон доверия КНБ: 110
            Контакт-центр судебных органов: 1401
            Единый телефон доверия МВД: 1402
            Телефон доверия Министерства сельского хозяйства РК: +7 7172 555 763
            Телефон доверия Агентства РК по делам противодействию коррупции: 1424
            Департамент полиции (Алматы): +7 727 254 40 92, +7 727 254 40 42
            УП Алатауского района: +7 727 227 55 02, +7 727 227 55 28
            УП Алмалинского района: +7 727 254 46 12
            УП Ауэзовского района: +7 727 298 53 02, +7 727 298 53 05 (Отдел полиции при УП Ауэзовского района)
            УП Бостандыкского района: +7 727 254 47 02
            УП Жетысуского района: +7 727 254 49 02, +7 727 254 49 11
            УП Медеуского района: +7 727 254 48 02, +7 727 254 48 72 (Отдел полиции при УП Медеуского района)
            УП Турксибского района: +7 727 298 54 02, +7 727 290 32 27, +7 727 298 54 62 (Отдел полиции при УП Турксибского района)
            Департамент по чрезвычайным ситуациям г. Алматы: +7 727 394 57 39
            Районные отделы по ЧС (Алматы):
                Алмалинский: +7 727 279 48 01, +7 727 390 75 30
                Ауэзовский: +7 727 226 99 15
                Бостандыкский: +7 727 337 87 16
                Жетысуский: +7 727 233 33 45
                Медеуский: +7 727 272 48 93
                Наурызбайский: +7 727 305 05 01
                Турксибский: +7 727 251 59 99
            Казселезащита, эксплуатационное управление: +7 727 269 09 64
            Республиканский опертивно-спасательный отряд: +7 727 372 15 60
            Контакт-центр Фонда «Даму»: 1408
            Контакт-центр Государственный центр по выплате пенсий: 1411
            Контакт-центр Комитет государственных доходов МФ РК: 1412
            Контакт-центр ЕНПФ: 1418
            Горячая линия по земельному вопросу: 1434
            Центр поддержки потребителей Казахтелеком: 160
            Централизованное бюро ремонта Казахтелеком: 165
            Телефон доверия по борьбе с торговлей людьми: 116-16
            Банки (контакт-центры):
                ATF: 8 8000 800 283 (2424)
                AsiaCredit Bank: 3311
                Сбербанк: +7 727 250 30 20 (5030)
                VTB: 5050
                ForteBank: 7575
                Capital Bank Kazakhstan: 6161
                First Heartland Jýsan Bank: 7711
                Eurasian Bank: +7 727 332 77 22
                Kaspi: 9999
                Altyn Bank: +7 727 35 65 777
                Жилстройсбербанк Казахстана: 300
                Bank RBK: 7888
                Al Hilal Bank: 2330
                Halyk Bank: 7111
                Nurbank: 2552
        
        6.  Язык и тон: Используй официальный, но понятный язык. Будь вежливым и профессиональным.
        
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
    # Удаляем лишние пробелы и переносы строк
    response_text = re.sub(r'\s*\n\s*\n\s*', '\n\n', response_text).strip()
    response_text = re.sub(r'\s+', ' ', response_text)
    
    # Исправляем разбитые слова
    response_text = re.sub(r'(\w+)\s+(\w{1,3})\b', r'\1\2', response_text)
    response_text = response_text.replace('услугис', 'услуги с')
    response_text = response_text.replace('стороныкак', 'стороны как')
    response_text = response_text.replace('законодательствоРК', 'законодательство РК')
    response_text = response_text.replace('запрещатьвам', 'запрещать вам')
    response_text = response_text.replace('вероисповеданиявыи', 'вероисповедания вы и')
    response_text = response_text.replace('одеждув', 'одежду в')
    response_text = response_text.replace('обучениеит', 'обучение и т')
    response_text = response_text.replace('Естьли', 'Есть ли')
    
    # Разбиваем текст на разделы
    sections = response_text.split('\n\n')
    formatted_sections = []
    in_list = False
    current_section = None
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        # Определяем тип раздела
        section_lower = section.lower()
        if section_lower.startswith('section: юридическая оценка'):
            if in_list:
                formatted_sections.append('</ul>')
                in_list = False
            formatted_sections.append('<h3>Юридическая оценка ситуации</h3>')
            content = section[len('SECTION: Юридическая оценка'):].strip()
            formatted_sections.append(f'<p><strong>Юридическая оценка:</strong> {content}</p>')
            current_section = 'evaluation'
        elif section_lower.startswith('section: действие'):
            if in_list:
                formatted_sections.append('</ul>')
                in_list = False
            formatted_sections.append('<h3>Действие</h3>')
            content = section[len('SECTION: Действие'):].strip()
            formatted_sections.append(f'<p>{content}</p>')
            current_section = 'action'
        elif section_lower.startswith('section: рекомендации'):
            if in_list:
                formatted_sections.append('</ul>')
                in_list = False
            formatted_sections.append('<h3>Рекомендации</h3>')
            current_section = 'recommendations'
        elif section_lower.startswith('section: необходимая информация'):
            if in_list:
                formatted_sections.append('</ul>')
                in_list = False
            formatted_sections.append('<h3>Необходимая информация</h3>')
            formatted_sections.append('<p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>')
            current_section = 'information'
        elif section_lower.startswith('section: нормативная база'):
            if in_list:
                formatted_sections.append('</ul>')
                in_list = False
            formatted_sections.append('<h3>Нормативная база</h3>')
            content = section[len('SECTION: Нормативная база'):].strip()
            formatted_sections.append(f'<p>{content}</p>')
            current_section = 'laws'
        elif section_lower.startswith('section: экстренные контакты'):
            if in_list:
                formatted_sections.append('</ul>')
                in_list = False
            formatted_sections.append('<h3>Экстренные контакты</h3>')
            formatted_sections.append('<p><strong>В экстренных случаях обращайтесь:</strong></p>')
            current_section = 'contacts'
        else:
            # Обработка содержимого
            if current_section in ['information', 'contacts', 'recommendations'] or section.startswith('LIST_ITEM:') or section.startswith('-') or re.match(r'^\d+\.\s+', section):
                if not in_list:
                    formatted_sections.append('<ul>')
                    in_list = True
                section = re.sub(r'^\d+\.\s+', '', section.lstrip('- ').strip())  # Удаляем номера или дефисы
                section = section.replace('LIST_ITEM:', '').strip()
                if ':' in section and len(section.split(':', 1)) > 1:
                    parts = section.split(':', 1)
                    label = parts[0].strip()
                    if current_section == 'information':
                        label = {'скольковамлет': 'Возраст', 'какого вероисповедания': 'Вероисповедание', 'вчём конкретно': 'Детали запрета', 'есть ли': 'Письменное подтверждение', 'какую форму': 'Предпочитаемая форма обучения', 'какие конкретные статьи': 'Нормативная база'}.get(label.lower(), label)
                    formatted_sections.append(f'<li><strong>{label}:</strong> {parts[1].strip()}</li>')
                else:
                    formatted_sections.append(f'<li>{section}</li>')
            else:
                if in_list:
                    formatted_sections.append('</ul>')
                    in_list = False
                formatted_sections.append(f'<p>{section}</p>')
    
    if in_list:
        formatted_sections.append('</ul>')
    
    result = '\n'.join(formatted_sections)
    result = re.sub(r'<p>\s*</p>', '', result)
    return result

class TestHTMLFormatting(unittest.TestCase):
    def test_clean_and_format_html(self):
        input_text = """
        SECTION: Юридическая оценка
        Запрет на посещение школы является нарушением права на образование.
        
        SECTION: Необходимая информация
        LIST_ITEM: Сколько вам лет?
        LIST_ITEM: Какого вероисповедания вы и ваши родители?
        
        SECTION: Экстренные контакты
        LIST_ITEM: Полиция: 102
        LIST_ITEM: Единый номер экстренных служб: 112
        """
        expected = """
        <h3>Юридическая оценка ситуации</h3>
        <p><strong>Юридическая оценка:</strong> Запрет на посещение школы является нарушением права на образование.</p>
        <h3>Необходимая информация</h3>
        <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
        <ul>
        <li><strong>Возраст:</strong> Сколько вам лет?</li>
        <li><strong>Вероисповедание:</strong> Какого вероисповедания вы и ваши родители?</li>
        </ul>
        <h3>Экстренные контакты</h3>
        <p><strong>В экстренных случаях обращайтесь:</strong></p>
        <ul>
        <li>Полиция: <strong>102</strong></li>
        <li>Единый номер экстренных служб: <strong>112</strong></li>
        </ul>
        """
        result = clean_and_format_html(input_text)
        self.assertEqual(result.strip(), expected.strip())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
