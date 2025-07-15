from memory import init_db, save_message, load_conversation, delete_conversation, get_all_sessions_summary_mongo
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
import google.generativeai as genai
import os
import json
import re
from flask_cors import CORS
import bleach  # Для очистки HTML от XSS
from concurrent.futures import ThreadPoolExecutor  # Для асинхронных вызовов
from PIL import Image  # Для обработки изображений
import io  # Для работы с байтовыми потоками
from docx import Document  # Для чтения .docx
from PyPDF2 import PdfReader  # Для чтения .pdf
import logging  # Для логирования
from lxml import html
# --- НОВОЕ: Импортируем helpers ---
from helpers import expand_keywords, build_snippet
import unittest
# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 100  #(100 МБ)
CORS(app, origins=["https://ai-lawyer-tau.vercel.app", "http://localhost:5000", "http://127.0.0.1:5000"])

# --- Инициализация AI и Базы Законов ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "text/plain", "temperature": 0.7})
vision_model = genai.GenerativeModel('gemini-1.5-flash')  # Модель для анализа изображений

LAW_DB = []  # Теперь это будет использоваться как кэш или для специализированного поиска
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
# --- Инициализация MongoDB ---
MONGO_URI = os.getenv("MONGO_URI")
if MONGO_URI:
    init_db()  # Инициализируем MongoDB соединение при старте приложения
else:
    logging.error("❌ Ошибка: Переменная окружения MONGO_URI не установлена. Подключение к MongoDB невозможно.")

executor = ThreadPoolExecutor(max_workers=4)  # Пул потоков для асинхронной обработки
load_law_db()
# --- Загрузка базы законов ---
def load_law_db(path="laws/kazakh_laws_db.json"):
    global LAW_DB
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            LAW_DB = json.load(f)
        logging.info(f"✅ Загружено {len(LAW_DB)} статей из базы законов.")
        build_law_index()
    else:
        logging.warning(f"⚠️ База законов не найдена по пути: {path}. Поиск будет ограничен.")



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

def clean_and_format_html(text):
    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Заменяем ** на <strong> теги
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Заменяем * на <em> теги
    text = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'<em>\1</em>', text)
    
    # Исправляем разбитые слова (как "руководи телю" или "скан-копи ю")
    text = re.sub(r'(\w+)\s+(\w{1,3})\b', r'\1\2', text)
    
    # Разбиваем текст на абзацы и списки
    paragraphs = text.split('\n\n')
    formatted_lines = []
    in_list = False
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
            
        # Проверяем, является ли это заголовком (например, "Юридическая оценка ситуации")
        if re.match(r'^[А-Я][А-Яа-я\s]+$', paragraph):
            formatted_lines.append(f'<h3>{paragraph}</h3>')
            continue
            
        # Проверяем, является ли это началом списка
        if re.match(r'^[А-Яа-я\s]+:', paragraph) or paragraph.startswith('-'):
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            # Удаляем начальный дефис, если есть
            paragraph = paragraph.lstrip('- ').strip()
            if ':' in paragraph:
                parts = paragraph.split(':', 1)
                formatted_lines.append(f'<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>')
            else:
                formatted_lines.append(f'<li>{paragraph}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            formatted_lines.append(f'<p>{paragraph}</p>')
    
    if in_list:
        formatted_lines.append('</ul>')
    
    result = '\n'.join(formatted_lines)
    
    # Очищаем от пустых тегов и дублирующих пробелов
    result = re.sub(r'<p>\s*</p>', '', result)
    result = re.sub(r'<p>\s*(<strong>[^<]+</strong>)\s*([^<]+)', r'<p>\1 \2</p>', result)
    
    # Исправляем обрезанные слова
    result = result.replace('скан-копи ю', 'скан-копию')
    
    return result

# Замените функцию sanitize_html_output на эту улучшенную версию:



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
        text = f'<p>{text}</p>'  # Fallback to wrapping in <p> if invalid
    allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'em', 'i', 'li', 'ol', 'p', 'strong', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'span', 'div', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'hr', 's', 'del', 'ins', 'img']
    allowed_attrs = {'*': ['class', 'style'], 'a': ['href', 'title'], 'img': ['src', 'alt', 'width', 'height']}
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

# --- Маршрут для обработки текстовых запросов ---
@app.route("/ask", methods=["POST"])
def ask_route():
    try:
        data = request.get_json()
        user_question = data.get("question", "")
        session_id = data.get("session_id", "default")

        if not user_question:
            return jsonify({"error": "Пустой вопрос"}), 400

        # Загружаем историю для текущей сессии
        history = load_conversation(session_id)
        
        # Добавляем текущий вопрос пользователя в историю
        full_history = history + [{"role": "user", "parts": [user_question]}]

        # Поиск релевантных законов на основе вопроса
        relevant_laws = find_relevant_laws(user_question)
        law_context = ""
        if relevant_laws:
            law_context = "<ul>"
            for law in relevant_laws:
                law_context += f"<li><strong>{law['title']}</strong>: {law['snippet']}</li>"
            law_context += "</ul>"

        # Добавляем контекст законов к запросу для AI
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
        2.  **Точность и актуальность:** Отвечай максимально точно и полно, ссылаясь на конкретные статьи законов, нормативные акты или общепринятые юридические практики РК, если это возможно.
        3.  **Уточняющие вопросы:** Если вопрос нечеткий, слишком общий или требует конкретизации для применения норм РК, задавай уточняющие вопросы. Например: "Пожалуйста, уточните, какой аспект [тема] вас интересует в рамках законодательства РК (например, трудовой договор, испытательный срок, приказ о приеме на работу)?"
        4.  **Практическая помощь:**
            * **Шаблоны и образцы:** Если запрос касается оформления документов (жалоба, заявление, договор, приказ и т.п.), и у тебя есть соответствующий шаблон или четкий алгоритм его составления в базе знаний, предложи его пользователю. Указывай, что это образец и может требовать адаптации.
            * **Полезные советы/лайфхаки:** Предоставляй практические советы и рекомендации, помогающие пользователю в решении юридических вопросов, избегая типичных ошибок.
        5.  **Экстренные контакты и справочная информация:**
            * Если вопрос явно или косвенно касается экстренных ситуаций, правонарушений, чрезвычайных происшествий или необходимости связаться с государственными органами/службами, предоставь соответствующие контактные данные.
            * В случае необходимости, цитируй контакты из следующего списка. Указывай принадлежность контактов (Казахстан, Алматы) если это уместно.
        
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
        
        {law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях."}
            
        """

        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history

        def generate_stream():
            ai_response_content = ""
            accumulated_text = ""
            try:
                for chunk in model.generate_content(messages_for_model, stream=True):
                    if chunk.text:
                        accumulated_text += chunk.text
                        # Проверяем, есть ли завершенные HTML-структуры
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

        return Response(stream_with_context(generate_stream()), mimetype='text/html')

    except Exception as e:
        logging.error(f"❌ Ошибка в /ask: {e}")
        return jsonify({"error": f"Ошибка сервера при обработке запроса: {str(e)}"}), 500
        

@app.route('/get-all-sessions-summary', methods=["GET"])
def get_all_sessions_summary_route():
    try:
        sessions_summary = get_all_sessions_summary_mongo()  # Получение сводки сессий из MongoDB
        if sessions_summary:
            return jsonify({"sessions": sessions_summary}), 200
        else:
            return jsonify({"sessions": []}), 200
    except Exception as e:
        return jsonify({"error": f"Ошибка при получении сводки сессий: {str(e)}"}), 500

def process_file_content(file_stream, mimetype):
    """
    Обрабатывает файл по его MIME-типу и возвращает извлечённый текст.
    Поддерживает PDF, DOCX, текстовые файлы и изображения.
    """
    text_content = ""
    try:
        if mimetype == 'application/pdf':
            # Для PDF используем PyPDF2
            reader = PdfReader(file_stream)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content += extracted + "\n"
        elif mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            # Для DOCX используем python-docx
            document = Document(file_stream)
            for paragraph in document.paragraphs:
                text_content += paragraph.text + "\n"
        elif mimetype.startswith('image/'):
            # Для изображений используем Gemini Vision Model
            try:
                image = Image.open(file_stream)
                # Отправляем изображение в модель для описания
                response = vision_model.generate_content(
                    ["Опиши этот документ или изображение. Извлеки весь текст и информацию, которая может быть полезна для юриста."],
                    image=image
                )
                text_content = response.text
            except Exception as e:
                logging.error(f"Ошибка обработки изображения: {e}")
                return None
        elif mimetype.startswith('text/'):
            # Текстовые файлы
            text_content = file_stream.read().decode('utf-8', errors='ignore')
        else:
            logging.warning(f"⚠️ Неподдерживаемый тип файла: {mimetype}")
            return None
    except Exception as e:
        logging.error(f"❌ Ошибка при обработке файла {mimetype}: {e}")
        return None
    return text_content


@app.route("/upload-document", methods=["POST"])
def upload_document_route():
    try:
        user_file = request.files.get('file')
        user_question = request.form.get("question", "")  # Вопрос, сопровождающий файл
        session_id = request.form.get("session_id", "default")

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
            law_context = "\n\nРелевантные статьи законодательства Казахстана:\n"
            for law in relevant_laws:
                law_context += f"- **{law['title']}**: {law['snippet']}\n"
            logging.info(f"🔍 Найдены релевантные законы для документа и запроса.")

        system_instruction = f"""Ты - ИИ-юрист, специализирующийся исключительно на законодательстве Республики Казахстан.
            Твоя задача — давать точные, полные и основанные на законодательстве ответы.
            Всегда ссылайся на конкретные статьи законов или нормативные акты РК, если это возможно.
            {law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях, но всегда предупреждай, что информация требует проверки по актуальным законам РК."}
        """

        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history

        def generate_document_stream():
            ai_response_content = ""
            accumulated_text = ""
            try:
                for chunk in model.generate_content(messages_for_model, stream=True):
                    if chunk.text:
                        accumulated_text += chunk.text
                        if '.' in accumulated_text or '\n' in accumulated_text or len(accumulated_text) > 100:
                            cleaned_chunk = sanitize_html_output(accumulated_text)
                            if not re.search(r'<[^>]+>', cleaned_chunk):
                                cleaned_chunk = f'<p>{cleaned_chunk}</p>'
                            ai_response_content += cleaned_chunk
                            yield cleaned_chunk
                            accumulated_text = ""
                if accumulated_text:
                    cleaned_chunk = sanitize_html_output(accumulated_text)
                    if not re.search(r'<[^>]+>', cleaned_chunk):
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
        
        return Response(stream_with_context(generate_document_stream()), mimetype='text/html')
    except Exception as e:
        logging.error(f"❌ Ошибка в /upload-document: {e}")
        return jsonify({"error": f"Ошибка сервера при обработке документа: {str(e)}"}), 500

# --- Основной маршрут для фронтенда ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/get-history', methods=["GET"])
def get_history_route():
    try:
        session_id = request.args.get("session_id", "default")
        history = load_conversation(session_id)
        # Привести к простому виду (user/model + content) для фронта:
        formatted = []
        for msg in history:
            # msg["parts"] может быть списком словарей или строк
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

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

def post_process_ai_response(response_text):
    """
    Дополнительная обработка ответа AI для исправления форматирования
    """
    # Удаляем двойные пробелы
    response_text = re.sub(r'\s+', ' ', response_text)
    
    # Исправляем разбитые слова
    response_text = re.sub(r'(\w+)\s+(\w{1,3})\b', r'\1\2', response_text)
    
    # Если в тексте нет HTML тегов, создаем структуру
    if not re.search(r'<[^>]+>', response_text):
        # Разбиваем на абзацы
        paragraphs = response_text.split('\n\n')
        formatted_paragraphs = []
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # Проверяем, является ли это списком
            if ':' in paragraph and len(paragraph.split(':')) > 1:
                lines = paragraph.split('\n')
                if len(lines) > 1:
                    # Это список
                    formatted_paragraphs.append('<ul>')
                    for line in lines:
                        line = line.strip()
                        if ':' in line:
                            parts = line.split(':', 1)
                            formatted_paragraphs.append(f'<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>')
                        elif line:
                            formatted_paragraphs.append(f'<li>{line}</li>')
                    formatted_paragraphs.append('</ul>')
                else:
                    formatted_paragraphs.append(f'<p>{paragraph}</p>')
            else:
                formatted_paragraphs.append(f'<p>{paragraph}</p>')
        
        response_text = '\n'.join(formatted_paragraphs)
    
    # Исправляем специфические проблемы
    response_text = response_text.replace('руководи телю', 'руководителю')
    response_text = response_text.replace('свидетель ские', 'свидетельские')
    
    return response_text

if __name__ == '__main__':
    # Для Railway:
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
