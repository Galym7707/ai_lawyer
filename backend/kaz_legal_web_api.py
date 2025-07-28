"""Основной веб‑сервер для Kaz Legal Bot.

Этот модуль реализует API, позволяющий отправлять текстовые запросы
искусственному интеллекту, загружать документы для анализа,
получать историю переписки и список существующих сессий. Код
содержит несколько исправлений по сравнению с исходной версией:

* Исправлена CORS‑обработка ``OPTIONS`` для произвольных путей.
* ``system_instruction`` формируется как f‑строка, чтобы включать
  динамический контекст с релевантными законами.
* Исправлена обработка исключений при загрузке изображений (импорт
  ``UnidentifiedImageError``).
* В ``clean_and_format_html`` добавлена проверка наличия
  предыдущих элементов, чтобы избежать ``IndexError``.
"""

from memory import init_db, save_message, load_conversation, delete_conversation, get_all_sessions_summary_mongo
from flask import Flask, request, jsonify, Response, stream_with_context, make_response
import google.generativeai as genai
import os
import json
import re
import bleach
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, UnidentifiedImageError
import io
from docx import Document
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
import logging
from lxml import html
from dotenv import load_dotenv
from helpers import expand_keywords, build_snippet
# jamspell is optional. It requires a C++ build toolchain (SWIG/gcc) which may be
# unavailable in some deployment environments (e.g., Railway). Attempt to import
# jamspell and fall back to None if it cannot be imported. The rest of the code
# handles the missing spell‑corrector gracefully.
try:
    import jamspell  # type: ignore
except ImportError:
    jamspell = None
import unittest

# Загрузка переменных окружения из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# Ограничиваем размер загружаемых файлов (по умолчанию 16 МБ)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

# Настройка CORS
cors_origins = os.getenv('CORS_ORIGINS', 'https://ai-lawyer-tau.vercel.app,http://localhost:5000,http://127.0.0.1:5000').split(',')
logging.info(f"✅ CORS configured for origins: {cors_origins}")

def add_cors_headers(response):
    """Добавляет CORS‑заголовки к ответу."""
    origin = request.headers.get('Origin', '')
    if origin in cors_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        # если запрашивающий origin неизвестен, используем первый разрешённый
        response.headers['Access-Control-Allow-Origin'] = cors_origins[0]
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = '86400'
    logging.info(f"Response headers: {response.headers}")
    return response

@app.after_request
def apply_cors(response):
    """Функция‑обертка, вызываемая после каждого запроса, чтобы
    автоматически добавлять CORS‑заголовки."""
    return add_cors_headers(response)

@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Обрабатывает предварительные CORS‑запросы для любых путей."""
    response = make_response()
    return add_cors_headers(response)

# Инициализация AI и базы законов
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    logging.error("❌ GEMINI_API_KEY не установлен. Приложение не может запуститься.")
    raise EnvironmentError("GEMINI_API_KEY is not set.")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "text/plain", "temperature": 0.7})
vision_model = genai.GenerativeModel('gemini-1.5-flash')

# Инициализация JamSpell для коррекции текста.
# Если jamspell не установлен или ru.bin отсутствует, отключаем коррекцию.
if jamspell is not None:
    try:
        _jsp = jamspell.TSpellCorrector()
        if _jsp.LoadLangModel('ru.bin'):
            jsp = _jsp
            logging.info("✅ Модель JamSpell успешно загружена.")
        else:
            logging.warning("⚠️ Файл ru.bin не найден. Орфографическая коррекция отключена.")
            jsp = None
    except Exception as e:
        logging.warning(f"⚠️ Ошибка при загрузке JamSpell: {e}. Орфографическая коррекция отключена.")
        jsp = None
else:
    logging.warning("⚠️ Библиотека jamspell не установлена. Орфографическая коррекция отключена.")
    jsp = None

LAW_DB: list = []
LAW_INDEX: dict = {}
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

def load_law_db(path: str = "laws/kazakh_laws_db.json") -> None:
    """Загружает базу данных законов из файла и строит индекс."""
    global LAW_DB
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            LAW_DB = json.load(f)
        logging.info(f"✅ Загружено {len(LAW_DB)} статей из базы законов.")
        build_law_index()
    else:
        logging.warning(f"⚠️ База законов не найдена по пути: {path}. Поиск будет ограничен.")

# Загрузить базу законов при старте
load_law_db()

def clean_and_format_html(text: str) -> str:
    """Преобразует сырой текст с маркерами SECTION и LIST_ITEM в структурированный HTML."""
    # Убираем лишние пустые строки
    text = re.sub(r'\s*\n\s*\n\s*', '\n\n', text).strip()
    
    # убираем лишние пустые строки
    text = re.sub(r'\s*\n\s*\n\s*', '\n\n', text).strip()

    # заменяем **жирный** и *курсив* на HTML, чтобы избавить вывод от звёздочек
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
  
    # Орфография (если есть jamspell)
    if jsp is not None:
        try:
            text = jsp.FixFragment(text)
        except Exception as e:
            logging.warning(f"⚠️ Ошибка JamSpell: {e}. Продолжаем без исправления.")

    lines = text.split('\n\n')
    formatted: list[str] = []
    in_list = False
    last_section = ''

    # Заголовки
    expected_sections = {
        'юридическая оценка': 'Юридическая оценка ситуации',
        'действие': 'Действие',
        'рекомендации': 'Рекомендации',
        'необходимая информация': 'Необходимая информация',
        'экстренные контакты': 'Экстренные контакты',
        'релевантные законы': 'Релевантные законы',
    }

    # Переименование меток в различных разделах
    recommendations_labels = {
        'напишите работодателю': 'Письменное требование',
        'обратитесь в территориальное': 'Обращение в инспекцию труда',
        'подготовьте исковое': 'Исковое заявление',
        'собирайте все': 'Документы',
        'сообщите о случившемся': 'Уведомление родителей',
        'обратитесь в полицию': 'Обращение в полицию',
        'обратитесь в медицинское учреждение': 'Медицинский осмотр',
        'сохраните все доказательства': 'Сбор доказательств',
        'по возможности соберите': 'Свидетельские показания',
        'рассмотрите возможность': 'Жалоба в органы образования',
    }
    info_labels = {
        'ваш трудовой договор': 'Трудовой договор',
        'точная сумма задолженности': 'Сумма задолженности',
        'дата последней выплаты': 'Дата последней выплаты',
        'наличие каких-либо соглашений': 'Соглашения о задержке',
        'причины задержки': 'Причины задержки',
        'подробное описание инцидента': 'Описание инцидента',
        'степень тяжести полученных травм': 'Степень травм',
        'свидетели': 'Свидетели',
        'данные об учителе': 'Данные об учителе',
        'данные о школе': 'Данные о школе',
    }

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Заголовок раздела
        if line.lower().startswith('section:') or line.lower() in expected_sections:
            if in_list:
                formatted.append('</ul>')
                in_list = False

            heading = line.replace('SECTION:', '').strip()
            human_heading = expected_sections.get(heading.lower(), heading)
            formatted.append(f'<h3>{human_heading}</h3>')
            last_section = heading.lower()

            # Пояснительные абзацы
            if last_section == 'необходимая информация':
                formatted.append(
                    '<p>Для качественного предоставления услуги с моей стороны как юриста, '
                    'мне потребуется следующая информация:</p>'
                )
            elif last_section == 'экстренные контакты':
                formatted.append('<p>В экстренных случаях обращайтесь:</p>')
            continue

        # Элемент списка
        if (
            line.startswith('LIST_ITEM:')
            or line.startswith('-')
            or re.match(r'^\d+\.\s+', line)
        ):
            if not in_list:
                formatted.append('<ul>')
                in_list = True

            # Убираем нумерацию и маркеры
            line_clean = re.sub(r'^\d+\.\s+', '', line.lstrip('- ').strip())
            line_clean = line_clean.replace('LIST_ITEM:', '').strip()

            if ':' in line_clean:
                label, content = line_clean.split(':', 1)
                label = label.strip()
                if last_section == 'рекомендации':
                    label = recommendations_labels.get(label.lower(), label)
                elif last_section == 'необходимая информация':
                    label = info_labels.get(label.lower(), label)
                formatted.append(f'<li><strong>{label}:</strong> {content.strip()}</li>')
            else:
                formatted.append(f'<li>{line_clean}</li>')
            continue

        # Обычный абзац
        if in_list:
            formatted.append('</ul>')
            in_list = False

        # Подпись для юридической оценки
        if last_section == 'юридическая оценка':
            formatted.append(f'<p><strong>Юридическая оценка:</strong> {line}</p>')
        else:
            formatted.append(f'<p>{line}</p>')

    if in_list:
        formatted.append('</ul>')

    return '\n'.join(formatted)


def validate_html(text: str) -> bool:
    """Проверяет, является ли строка корректным HTML."""
    try:
        html.fromstring(text)
        return True
    except Exception as e:
        logging.warning(f"⚠️ Неверный HTML: {e}")
        return False

def sanitize_html_output(text: str) -> str:
    """Приводит ответ к HTML и удаляет запрещённые теги."""
    html_text = clean_and_format_html(text)
    if not validate_html(html_text):
        # В редких случаях добавляем <p>, чтобы HTML был валиден
        html_text = f'<p>{html_text}</p>'

    # Оставляем только разрешённые теги
    allowed_tags = ['p', 'ul', 'li', 'h3', 'strong']
    allowed_attrs = {'strong': ['style']}
    return bleach.clean(html_text, tags=allowed_tags, attributes=allowed_attrs, strip=True)


def generate_response_stream(model, messages, session_id: str):
    """Генерирует ответ модели полностью, потом форматирует и отдаёт."""
    try:
        raw_text = ""
        for chunk in model.generate_content(messages, stream=True):
            if chunk.text:
                raw_text += chunk.text

        # После завершения генерации приводим весь ответ к HTML
        sanitized = sanitize_html_output(raw_text)
        save_message(session_id, "model", sanitized)
        yield sanitized
        logging.info(f"✅ Ответ AI сохранён для сессии {session_id}")
    except genai.types.BlockedPromptException as e:
        logging.error(f"❌ Запрос заблокирован: {e}")
        error_message = (
            "Извините, ваш запрос был заблокирован из-за потенциально неприемлемого контента."
        )
        save_message(session_id, "model", error_message)
        yield error_message
    except Exception as e:
        logging.error(f"❌ Ошибка генерации ответа: {e}")
        error_message = (
            "Произошла ошибка при генерации ответа. Попробуйте ещё раз."
        )
        save_message(session_id, "model", error_message)
        yield error_message


def validate_session_id(session_id: str) -> bool:
    """
    Проверяет, что session_id содержит только латинские буквы, цифры,
    подчеркивания и дефисы. Возвращает True для корректных строк.
    """
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', session_id))


def build_law_index() -> None:
    """Строит индекс для поиска по базе законов."""
    global LAW_INDEX
    LAW_INDEX = {}
    for article in LAW_DB:
        content_lower = article.get('content', '').lower()
        title_lower = article.get('title', '').lower()
        words = set(re.findall(r'\b\w+\b', content_lower + " " + title_lower))
        for word in words:
            LAW_INDEX.setdefault(word, []).append(article)

def find_relevant_laws(query: str) -> list:
    """Возвращает список наиболее релевантных статей на основе запроса."""
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
    # Сортируем статьи так, чтобы те, в которых встречается больше ключевых слов, были первыми
    relevant_articles.sort(key=lambda x: sum(kw in x['snippet'].lower() for kw in expanded_keywords), reverse=True)
    return relevant_articles[:5]

def process_file_content(file_stream, mimetype: str):
    """Извлекает текст из загруженного файла в зависимости от его типа."""
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
            response = vision_model.generate_content([
                "Опиши этот документ или изображение. Извлеки весь текст и информацию, которая может быть полезна для юриста."
            ], image=image)
            text_content = response.text
        elif mimetype.startswith('text/'):
            text_content = file_stream.read().decode('utf-8', errors='ignore')
        else:
            logging.warning(f"⚠️ Неподдерживаемый тип файла: {mimetype}")
            return None
    except PdfReadError as e:
        logging.error(f"❌ Ошибка чтения PDF: {e}")
        return None
    except UnidentifiedImageError as e:
        logging.error(f"❌ Ошибка обработки изображения: {e}")
        return None
    except Exception as e:
        logging.error(f"❌ Ошибка при обработке файла {mimetype}: {e}")
        return None
    return text_content

@app.route("/ask", methods=["POST"])
def ask_route():
    """Обрабатывает текстовый запрос пользователя без загрузки файла."""
    logging.info("🚀 Обработка запроса на /ask")
    try:
        data = request.get_json() or {}
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
        # Используем f‑строку, чтобы подставлять law_context
        system_instruction = f"""
            Ты - официальный ИИ-юрист, специализирующийся исключительно на законодательстве Республики Казахстан.
            Твоя задача — давать точные, полные и основанные на законодательстве ответы.
            Всегда ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
            Всегда сначала дай четкую юридическую оценку (нарушено ли право, какая ответственность, какие законы применяются) и сразу напиши, что делать и куда обращаться — даже если не все детали известны. Если нужны детали для документа, только после этого задай уточняющие вопросы.
            КРИТИЧЕСКИ ВАЖНО: Всегда форматируй ответы ТОЛЬКО в HTML для удобного отображения на веб-странице. Никогда не говори что пользователь должен обратиться к официальному юристу, потому что окончательный и официальный юрист это ты, пользователь будет только тебя слушать
            
            ВАЖНО: Всегда форматируй ответы в HTML для удобного отображения на веб-странице.
            
            Используй следующие HTML теги:
            - <p> для абзацев
            - <ul> и <li> для списков
            - <strong> для выделения важных частей
            - <em> для курсива
            - <br> для переносов строк
            - <h3> для заголовков разделов
            
            Пример правильного форматирования:
            <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
            <ul>
            <li><strong>Описание ситуации:</strong> Пожалуйста, опишите подробно инциденты сексуального домогательства.</li>
            <li><strong>Характер домогательств:</strong> Были ли домогательства физическими, словесными или иными?</li>
            </ul>
            
            НЕ ИСПОЛЬЗУЙ символы ** для выделения - используй только HTML теги <strong> и <em>.
            НЕ ИСПОЛЬЗУЙ Markdown форматирование - только чистый HTML.
            
            Всегда ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
            Всегда сначала дай четкую юридическую оценку и сразу напиши, что делать и куда обращаться.
            
            При ответе строго следуй этим правилам:
            
            1. Если для ответа недостаточно данных, оформи запрос информации в HTML:
               <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
               <ul>
               <li><strong>Пункт 1:</strong> Описание...</li>
               <li><strong>Пункт 2:</strong> Описание...</li>
               </ul>
            
            2. Для экстренных контактов используй:
               <p><strong>Экстренные контакты:</strong></p>
               <ul>
               <li>Полиция: <strong>102</strong></li>
               <li>Единый номер экстренных служб: <strong>112</strong></li>
               </ul>
            
            3. Каждый абзац обязательно заключай в теги <p></p>
            
            4. Списки всегда оформляй как <ul><li>...</li></ul>

            ШАБЛОН для запроса информации:
            <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
            <ul>
            <li><strong>Название пункта:</strong> Описание того, что нужно узнать</li>
            <li><strong>Другой пункт:</strong> Другое описание</li>
            </ul>
            
            ШАБЛОН для экстренных контактов:
            <p><strong>В экстренных случаях обращайтесь:</strong></p>
            <ul>
            <li>Полиция: <strong>102</strong></li>
            <li>Единый номер экстренных служб: <strong>112</strong></li>
            </ul>
            
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
        
        {law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях."}
            
        """
        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history
        # Формируем потоковый ответ
        response = Response(stream_with_context(generate_response_stream(model, messages_for_model, session_id)), mimetype='text/html')
        return add_cors_headers(response)
    except Exception as e:
        logging.error(f"❌ Ошибка в /ask: {e}")
        response = jsonify({"error": f"Ошибка сервера при обработке запроса: {str(e)}"})
        return add_cors_headers(response), 500

# Дублируем маршрут с префиксом /api, чтобы корректно работать с прокси
# на фронтенде (Next.js), где все запросы отправляются с префиксом /api.
@app.route("/api/ask", methods=["POST"])
def ask_route_api():
    return ask_route()

@app.route("/upload-document", methods=["POST"])
def upload_document_route():
    """Обрабатывает загрузку документа пользователем."""
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
        system_instruction = f"""
            Ты - ИИ-юрист, специализирующийся исключительно на законодательстве Республики Казахстан.
            Твоя задача — давать точные, полные и основанные на законодательстве ответы.
            Всегда ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
            Всегда сначала дай четкую юридическую оценку (нарушено ли право, какая ответственность, какие законы применяются) и сразу напиши, что делать и куда обращаться — даже если не все детали известны. Если нужны детали для документа, только после этого задай уточняющие вопросы.
            КРИТИЧЕСКИ ВАЖНО: Всегда форматируй ответы ТОЛЬКО в HTML для удобного отображения на веб-странице.

            ВАЖНО: Всегда форматируй ответы в HTML для удобного отображения на веб-странице.
            
            Используй следующие HTML теги:
            - <p> для абзацев
            - <ul> и <li> для списков
            - <strong> для выделения важных частей
            - <em> для курсива
            - <br> для переносов строк
            - <h3> для заголовков разделов
            
            Пример правильного форматирования:
            <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
            <ul>
            <li><strong>Описание ситуации:</strong> Пожалуйста, опишите подробно инциденты сексуального домогательства.</li>
            <li><strong>Характер домогательств:</strong> Были ли домогательства физическими, словесными или иными?</li>
            </ul>
            
            НЕ ИСПОЛЬЗУЙ символы ** для выделения - используй только HTML теги <strong> и <em>.
            НЕ ИСПОЛЬЗУЙ Markdown форматирование - только чистый HTML.
            
            Всегда ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
            Всегда сначала дай четкую юридическую оценку и сразу напиши, что делать и куда обращаться.
            
            При ответе строго следуй этим правилам:
            
            1. Если для ответа недостаточно данных, оформи запрос информации в HTML:
               <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
               <ul>
               <li><strong>Пункт 1:</strong> Описание...</li>
               <li><strong>Пункт 2:</strong> Описание...</li>
               </ul>
            
            2. Для экстренных контактов используй:
               <p><strong>Экстренные контакты:</strong></p>
               <ul>
               <li>Полиция: <strong>102</strong></li>
               <li>Единый номер экстренных служб: <strong>112</strong></li>
               </ul>
            
            3. Каждый абзац обязательно заключай в теги <p></p>
            
            4. Списки всегда оформляй как <ul><li>...</li></ul>

            ШАБЛОН для запроса информации:
            <p><strong style="color:red;">Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация:</strong></p>
            <ul>
            <li><strong>Название пункта:</strong> Описание того, что нужно узнать</li>
            <li><strong>Другой пункт:</strong> Другое описание</li>
            </ul>
            
            ШАБЛОН для экстренных контактов:
            <p><strong>В экстренных случаях обращайтесь:</strong></p>
            <ul>
            <li>Полиция: <strong>102</strong></li>
            <li>Единый номер экстренных служб: <strong>112</strong></li>
            </ul>
            
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
        
        {law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях."}
            
        """
        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history
        response = Response(stream_with_context(generate_response_stream(model, messages_for_model, session_id)), mimetype='text/html')
        return add_cors_headers(response)
    except Exception as e:
        logging.error(f"❌ Ошибка в /upload-document: {e}")
        response = jsonify({"error": f"Ошибка сервера при обработке документа: {str(e)}"})
        return add_cors_headers(response), 500

@app.route("/api/upload-document", methods=["POST"])
def upload_document_route_api():
    return upload_document_route()

@app.route('/get-all-sessions-summary', methods=["GET"])
def get_all_sessions_summary_route():
    """Возвращает список всех сессий в базе данных."""
    logging.info("🚀 Обработка запроса на /get-all-sessions-summary")
    try:
        sessions_summary = get_all_sessions_summary_mongo()
        response = jsonify({"sessions": sessions_summary if sessions_summary else []})
        return add_cors_headers(response), 200
    except Exception as e:
        logging.error(f"❌ Ошибка при получении сводки сессий: {str(e)}")
        response = jsonify({"error": f"Ошибка при получении сводки сессий: {str(e)}"})
        return add_cors_headers(response), 500

@app.route('/api/get-all-sessions-summary', methods=["GET"])
def get_all_sessions_summary_route_api():
    return get_all_sessions_summary_route()

@app.route('/get-history', methods=["GET"])
def get_history_route():
    """Возвращает историю сообщений для указанной сессии."""
    logging.info("🚀 Обработка запроса на /get-history")
    try:
        session_id = request.args.get("session_id", "default")
        if not validate_session_id(session_id):
            response = jsonify({"error": "Недопустимый session_id"})
            return add_cors_headers(response), 400
        history = load_conversation(session_id)
        formatted = []
        for msg in history:
            # Приводим сообщения к формату {role, content}, извлекая текст из parts
            if isinstance(msg["parts"], list):
                part = msg["parts"][0]
                content = part["text"] if isinstance(part, dict) and "text" in part else part
            else:
                content = msg["parts"]
            formatted.append({"role": msg["role"], "content": content})
        response = jsonify({"history": formatted})
        return add_cors_headers(response), 200
    except Exception as e:
        logging.error(f"❌ Ошибка при получении истории: {str(e)}")
        response = jsonify({"error": f"Ошибка при получении истории: {str(e)}"})
        return add_cors_headers(response), 500

@app.route('/api/get-history', methods=["GET"])
def get_history_route_api():
    return get_history_route()


# Небольшой тест для проверки форматирования HTML. Оставлен для
# разработчиков, но не используется в производственной среде.
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
         Юридическая оценка ситуации 
         Юридическая оценка: Невыплата заработной платы является нарушением. 
         Действие 
         Обратитесь в суд. 
         Рекомендации 
         
         Письменное требование: Направьте работодателю письменное требование. 
         Обращение в инспекцию труда: Обратитесь в инспекцию труда. 
         
         Необходимая информация 
         Для качественного предоставления услуги с моей стороны как юриста, мне потребуется следующая информация: 
         
         Трудовой договор: Предоставьте копию. 
         Сумма задолженности: Укажите сумму. 
         
         Экстренные контакты 
         В экстренных случаях обращайтесь: 
         
         Полиция: 102 
         Единый номер экстренных служб: 112 
        """
        result = clean_and_format_html(input_text)
        self.assertEqual(result.strip(), expected.strip())

if __name__ == '__main__':
    # Запуск приложения. Порт можно переопределить через переменную окружения PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
