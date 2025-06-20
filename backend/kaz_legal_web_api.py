# kaz_legal_web_api.py (Версия 4.0 - Расширенные словари и полные источники)
from memory import init_db, save_message, load_conversation
init_db()
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
import google.generativeai as genai
import os
import json
import re
from flask_cors import CORS

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app, origins=["https://ai-lawyer-tau.vercel.app"])

# 🧠 Настройка Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

LAW_DB = [] 

# --- УЛУЧШЕНИЕ: Максимально расширенный словарь синонимов ---
LEGAL_SYNONYMS = {
    # Трудовые отношения
    'увольнение': ['уволен', 'увольн', 'уволить', 'расторжение', 'расторгнуть', 'расторж', 'прекращение', 'прекращ', 'освобождение', 'освобожд', 'отстранение', 'отстранен', 'сокращение', 'сокращен', 'сокращ', 'дисциплинарное', 'взыскание'],
    'зарплата': ['заработная', 'зарплат', 'оплата', 'оклад', 'выплата', 'выплат', 'вознаграждение', 'вознагражден', 'жалование', 'жалован', 'доход', 'получка', 'премия', 'премиальн', 'надбавка', 'надбавк', 'тариф'],
    'отпуск': ['отпуск', 'отдых', 'каникулы', 'выходной', 'выходн', 'перерыв', 'отгул', 'нерабочий'],
    'больничный': ['больничн', 'нетрудоспособность', 'нетрудоспособн', 'болезнь', 'лечение', 'лечен', 'листок', 'временная', 'инвалидность', 'инвалидн'],
    'работа': ['труд', 'работ', 'служба', 'служб', 'деятельность', 'деятельност', 'занятость', 'профессия', 'профессион', 'должность', 'должност', 'обязанности'],
    'работник': ['сотрудник', 'служащий', 'служащ', 'персонал', 'кадры', 'кадр', 'трудящийся', 'трудящ', 'исполнитель'],
    'работодатель': ['наниматель', 'начальник', 'руководитель', 'руководств', 'предприятие', 'организация', 'организац', 'компания', 'фирма', 'учреждение'],
    
    # Жилищное право
    'жилье': ['жилище', 'жилищ', 'квартира', 'квартир', 'дом', 'помещение', 'помещен', 'недвижимость', 'недвижим', 'собственность', 'собственност', 'владение', 'владен', 'жилплощадь'],
    'аренда': ['аренд', 'арендовать', 'найм', 'наем', 'съем', 'снимать', 'поднаем', 'договор', 'плата', 'арендная'],
    'квартплата': ['коммунальные', 'коммуналк', 'услуги', 'содержание', 'содержан', 'эксплуатация', 'эксплуатац', 'ремонт', 'КУ'],
    'выселение': ['выселен', 'выселить', 'изъятие', 'изъят', 'освобождение', 'освобожден', 'выдворение', 'выдворен'],

    # Социальное право
    'пособие': ['пособи', 'выплата', 'выплат', 'социальное', 'социальн', 'помощь', 'поддержка', 'поддержк', 'льгота', 'льгот', 'компенсация', 'компенсац', 'субсидия'],
    'пенсия': ['пенсион', 'пенсионное', 'выслуга', 'старость', 'по старости', 'инвалидность', 'инвалидн', 'потеря кормильца', 'кормилец'],
    'декрет': ['декретн', 'материнство', 'материнск', 'отцовство', 'отцовск', 'ребенок', 'рождение', 'рожден', 'усыновление', 'усыновлен', 'беременность', 'беремен'],
    'инвалидность': ['инвалид', 'инвалидн', 'ограниченные', 'ограничен', 'возможности', 'группа', 'здоровье', 'реабилитация', 'реабилитац'],

    # Гражданское право
    'договор': ['соглашение', 'соглашен', 'контракт', 'сделка', 'обязательство', 'обязательств', 'условие', 'условия', 'пакт', 'договоренность'],
    'долг': ['задолженность', 'задолженност', 'обязательство', 'обязательств', 'заем', 'займ', 'кредит', 'взыскание', 'взыскан', 'неуплата'],
    'наследство': ['наследование', 'наследован', 'завещание', 'завещан', 'наследник', 'имущество', 'имуществ', 'правопреемство'],
    'развод': ['расторжение', 'расторжен', 'брак', 'супруг', 'супруга', 'семейный', 'семейн', 'алименты', 'раздел имущества'],

    # Уголовное право
    'преступление': ['преступлен', 'уголовное', 'уголовн', 'правонарушение', 'правонарушен', 'деяние', 'деян', 'состав', 'вина', 'наказание', 'наказан', 'злодеяние', 'проступок'],
    'кража': ['краж', 'хищение', 'хищен', 'присвоение', 'присвоен', 'растрата', 'растрат', 'грабеж', 'разбой'],
    'мошенничество': ['мошенничеств', 'обман', 'афера', 'злоупотребление', 'злоупотребл', 'финансовая пирамида'],
    
    # Административное право
    'штраф': ['административное', 'административн', 'взыскание', 'взыскан', 'наказание', 'наказан', 'нарушение', 'нарушен', 'санкция', 'санкци', 'протокол'],
    'права': ['право', 'правомочие', 'полномочие', 'свобода', 'свобод', 'гарантия', 'гарант', 'защита', 'защит', 'интересы'],

    # Образование и защита детей
    'учитель': ['учител', 'преподаватель', 'препода', 'педагог', 'наставник', 'воспитатель'],
    'ученик': ['ученик', 'учащийся', 'учащ', 'школьник', 'школьн', 'студент', 'воспитанник', 'воспитан', 'обучающийся'],
    'школа': ['школ', 'училище', 'лицей', 'гимназия', 'колледж', 'образовательное', 'образоват', 'учебное', 'учебн', 'заведение'],
    'ребенок': ['ребен', 'дети', 'несовершеннолетний', 'несовершеннолет', 'малолетний', 'малолет', 'дитя', 'подросток', 'подрост'],
    'насилие': ['насили', 'жестокость', 'жесток', 'принуждение', 'принужден', 'агрессия', 'агресси', 'избиение', 'избиен', 'домашнее', 'побои', 'побо', 'удар', 'бьет', 'физическое', 'психологическое'],

    # ПДД и транспорт
    'пдд': ['пдд', 'правила дорожного движения', 'дорожные знаки', 'дорожное движение', 'движение', 'транспорт', 'дорога', 'перекресток', 'полоса', 'светофор', 'зебра'],
    'самокат': ['самокат', 'электросамокат', 'гироскутер', 'средство индивидуальной мобильности', 'сим'],
    'велосипед': ['велосипед', 'велодорожка', 'велосипедист', 'двухколесный'],
    'автобусная полоса': ['автобусная полоса', 'полоса для общественного транспорта', 'выделенка', 'выделенная полоса']
}


# --- УЛУЧШЕНИЕ: Полный и актуальный словарь источников ---
SOURCE_MAPPING = {
    'Уголовный кодекс': 'https://adilet.zan.kz/rus/docs/K1400000226',
    'уголовн': 'https://adilet.zan.kz/rus/docs/K1400000226',

    'Об административных правонарушениях': 'https://adilet.zan.kz/rus/docs/K1400000235',
    'административн': 'https://adilet.zan.kz/rus/docs/K1400000235',

    'Гражданский кодекс': 'https://adilet.zan.kz/rus/docs/K940001000_',
    'гражданск': 'https://adilet.zan.kz/rus/docs/K940001000_',

    'Гражданский процессуальный кодекс': 'https://adilet.zan.kz/rus/docs/K1500000377',
    'процессуальн': 'https://adilet.zan.kz/rus/docs/K1500000377',

    'Трудовой кодекс': 'https://adilet.zan.kz/rus/docs/K1500000414',
    'трудов': 'https://adilet.zan.kz/rus/docs/K1500000414',

    'Предпринимательский кодекс': 'https://adilet.zan.kz/rus/docs/K1500000375',
    'предпринимательск': 'https://adilet.zan.kz/rus/docs/K1500000375',

    'Социальный кодекс': 'https://adilet.zan.kz/rus/docs/K2300000224',
    'социальн': 'https://adilet.zan.kz/rus/docs/K2300000224',

    'Экологический кодекс': 'https://adilet.zan.kz/rus/docs/K2100000400',
    'экологич': 'https://adilet.zan.kz/rus/docs/K2100000400',

    'Бюджетный кодекс': 'https://adilet.zan.kz/rus/docs/K080000095_',
    'бюджетн': 'https://adilet.zan.kz/rus/docs/K080000095_',

    'Водный кодекс': 'https://adilet.zan.kz/rus/docs/K1600000049',
    'водн': 'https://adilet.zan.kz/rus/docs/K1600000049',

    'О жилищных отношениях': 'https://adilet.zan.kz/rus/docs/Z970000254_',
    'жилищ': 'https://adilet.zan.kz/rus/docs/Z970000254_',

    'Об образовании': 'https://adilet.zan.kz/rus/docs/Z070000319_',
    'образован': 'https://adilet.zan.kz/rus/docs/Z070000319_',

    'Правила дорожного движения': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'пдд': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'самокат': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'велосипед': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'средства индивидуальной мобильности': 'https://adilet.zan.kz/rus/docs/V2300033003',
}


# --- Логика поиска и обработки ---
def find_laws_by_keywords(question, min_relevance=12, max_results=8):
    results = []
    question_lower = question.lower()
    question_words = set(re.findall(r'\b\w{3,}\b', question_lower))
    if not LAW_DB:
        return []

    priority_codes = []
    if any(w in question_lower for w in ['увольн', 'работ', 'работодат', 'труд', 'зарплат']):
        priority_codes.append('трудов')
    elif any(w in question_lower for w in ['жилье', 'аренда', 'квартира', 'высел']):
        priority_codes.append('жилищ')
    elif any(w in question_lower for w in ['пенсия', 'пособие', 'декрет']):
        priority_codes.append('социальн')
    elif any(w in question_lower for w in ['развод', 'алименты']):
        priority_codes.append('семейн')
    elif any(w in question_lower for w in ['ученик', 'учитель', 'школ', 'удар', 'насили']):
        priority_codes.extend(['уголовн', 'образован', 'административн'])

    expanded_terms = set(question_words)
    for word in question_words:
        for key_term, synonyms in LEGAL_SYNONYMS.items():
            if word in synonyms or word == key_term:
                expanded_terms.update(synonyms)
                expanded_terms.add(key_term)

    for entry in LAW_DB:
        title_lower = entry.get("title", "").lower()
        text_lower = entry.get("text", "").lower()
        relevance = calculate_relevance(expanded_terms, title_lower, text_lower)

        if any(code in title_lower for code in priority_codes):
            relevance += 10

        if relevance >= min_relevance:
            entry_copy = entry.copy()
            entry_copy["relevance"] = relevance
            results.append(entry_copy)

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:max_results]


def calculate_relevance(expanded_terms, title_lower, text_lower):
    relevance = 0;
    for term in expanded_terms:
        if term in title_lower: relevance += 10
        if term in text_lower: relevance += 2
    matched_terms_count = sum(1 for term in expanded_terms if term in title_lower or term in text_lower)
    if matched_terms_count > 1: relevance += matched_terms_count * 2
    return relevance

def load_law_db():
    global LAW_DB
    try:
        with open("laws/kazakh_laws.json", "r", encoding="utf-8") as f: raw_db = json.load(f)
        LAW_DB = preprocess_laws_into_articles(raw_db); print(f"✅ База данных загружена! Статей: {len(LAW_DB)}")
    except Exception as e: print(f"❌ Ошибка загрузки базы: {e}")

def preprocess_laws_into_articles(raw_db):
    records = []; heading_pattern = re.compile(r'^(статья|глава|раздел|подраздел|параграф)', re.IGNORECASE)
    for code_entry in raw_db:
        code_name = code_entry.get("title", "Без названия"); full_text = code_entry.get("text", ""); source = code_entry.get("source") or determine_source_by_content(code_name); items = full_text.splitlines()
        current_title = None; buffer = []
        for line in items:
            line = line.strip()
            if not line: continue
            if heading_pattern.match(line):
                if current_title and buffer: records.append({"title": f"{code_name}: {current_title}", "text": " ".join(buffer).strip(), "source": source})
                buffer = []; current_title = line
            else: buffer.append(line)
        if current_title and buffer: records.append({"title": f"{code_name}: {current_title}", "text": " ".join(buffer).strip(), "source": source})
    return records

load_law_db()

# --- Вспомогательные функции форматирования ---
def determine_source_by_content(content):
    content_lower = content.lower()
    for keyword, url in SOURCE_MAPPING.items():
        if keyword in content_lower: return url
    return "https://adilet.zan.kz"

def determine_code_name(content):
    content_lower = content.lower()
    name_mapping = {
        'уголовн': 'УК РК',
        'административн': 'КоАП РК',
        'гражданск': 'ГК РК',
        'процессуальн': 'ГПК РК',
        'трудов': 'ТК РК',
        'предпринимательск': 'ПК РК',
        'социальн': 'СК РК',
        'семейн': 'Кодекс о браке',
        'здоровь': 'Кодекс о здоровье',
        'экологич': 'ЭК РК',
        'налогов': 'НК РК',
        'бюджетн': 'БК РК',
        'таможен': 'ТК РК',
        'земельн': 'ЗК РК',
        'лесн': 'ЛК РК',
        'водн': 'ВК РК',
        'недра': 'Кодекс о недрах',
        'пдд': 'ПДД РК',
        'самокат': 'ПДД РК',
        'велосипед': 'ПДД РК'
    }
    for keyword, name in name_mapping.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', content_lower):
            return name
    return "Законодательство РК"


def format_laws(laws, shown_limit=5):
    if not laws:
        return "<div class='notice warning'>⚠️ <strong>По вашему запросу подходящих статей не найдено.</strong><br><small>Попробуйте переформулировать вопрос.</small></div>"

    output = "<div class='laws-container'><h3 class='laws-header'>📚 Релевантные статьи законодательства РК</h3>"
    
    total_found = len(laws)
    limited_laws = laws[:shown_limit]

    if total_found > shown_limit:
        output += f"<div class='notice tip'>🔎 Найдено {total_found} статей. Показаны только <strong>{shown_limit}</strong>, потому что ИИ уже дал исчерпывающее объяснение выше.</div>"

    for i, law in enumerate(limited_laws, 1):
        title = law.get('title', 'Без названия')
        text = law.get('text', 'Текст недоступен')
        source = law.get('source') or determine_source_by_content(title)
        relevance = law.get('relevance', 0)
        article_info = extract_article_info(title)
        code_name = determine_code_name(title)
        preview = text[:400] + "..." if len(text) > 400 else text

        output += f"<div class='law-card'><div class='card-header'><h4 class='card-title'>{i}. {title}</h4></div>"
        if article_info:
            output += f"<div class='card-meta'><strong>📍 {article_info}</strong></div>"
        output += f"<div class='card-body'><p>{preview}</p></div>"
        output += f"<div class='card-footer'><span class='card-source'><strong>Источник:</strong> {code_name}</span><div class='footer-actions'>"
        output += f"""<div class="tooltip-container card-relevance"><span>📊 {relevance}</span><span class="tooltip-text">Это 'очки релевантности' — чем выше, тем точнее статья связана с вашим вопросом.</span></div>"""
        output += f"<a href='{source}' target='_blank' class='card-link'>🔗 Читать полностью</a></div></div></div>"

    output += "</div>"
    return output

def extract_text_from_file(filepath):
    if filepath.endswith(".docx"):
        import docx
        doc = docx.Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs])
    elif filepath.endswith(".pdf"):
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        return "\n".join([page.extract_text() for page in reader.pages])
    else:
        return ""


def extract_article_info(title):
    patterns = [r'статья\s*(\d+)', r'ст\.\s*(\d+)', r'глава\s*(\d+)', r'гл\.\s*(\d+)', r'параграф\s*(\d+)', r'пункт\s*(\d+)', r'п\.\s*(\d+)', r'раздел\s*([IVX]+|\d+)', r'подраздел\s*(\d+)']
    found_parts = []; title_lower = title.lower()
    for pattern in patterns:
        matches = re.findall(pattern, title_lower, re.IGNORECASE)
        for match in matches:
            if 'статья' in pattern or 'ст.' in pattern: found_parts.append(f"Статья {match}")
            elif 'глава' in pattern or 'гл.' in pattern: found_parts.append(f"Глава {match}")
    return ", ".join(found_parts) if found_parts else None

def convert_full_markdown_to_html(text):
    text = text.strip()
    paragraphs = re.split(r'\n\s*\n', text)
    html_output = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Обработка заголовков (начинаются с жирного текста и заканчиваются двоеточием)
        if re.match(r'\*\*.+?:\*\*', para):
            para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para)
            html_output.append(f"<h3>{para}</h3>")
        # Обработка списков с тире или маркерами
        elif re.match(r'^[•*-] ', para):
            lines = para.split('\n')
            list_items = [
                f"<li>{re.sub(r'^[•*-] ', '', re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line.strip()))}</li>"
                for line in lines if line.strip()
            ]
            html_output.append("<ul>" + "".join(list_items) + "</ul>")
        # Простой абзац
        else:
            para = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', para)
            html_output.append(f"<p>{para}</p>")

    return "".join(html_output)


# --- ИСПРАВЛЕНИЕ: Финальная, самая надежная инструкция для ИИ ---
PROMPT_TEMPLATE = """
Ты — опытный и самый в мире лучший юрист-консультант, специализирующийся на законах Казахстана. К тебе обращаются обычные люди, чтобы узнать свои права и понять, как действовать.

Ситуация:
---
{question}
---

Отвечай сразу, по делу. Без вступлений, без фраз вроде «что произошло», «пользователь задал вопрос». Просто помоги.

Вот как нужно:

1. Объясни, **что говорит закон**.
2. Укажи, **нарушены ли права**, и какие.
3. Приведи **конкретные шаги**, которые человек может предпринять.
4. При необходимости — **дай шаблон заявления** (например, в полицию, работодателю, акиму).
5. Пиши **простыми словами**, избегай юридического жаргона. Ответ должен быть понятен даже школьнику.
6. Если законов по теме нет — так и напиши.

Форматируй красиво:
- Используй заголовки (**Что говорит закон?**, **Что делать?**, **Шаблон заявления**)
- Используй списки
- Не придумывай фактов — отвечай честно, даже если нет ответа.

Никогда не добавляй в конце фразы вроде "это лишь шаблон", "не является юридической консультацией", "обратитесь к специалисту". Представь, что ты реальный юрист, которому клиенты могут доверять и верить. 

"""

FILE_ANALYSIS_PROMPT = """
Ты — опытный юрист из Казахстана. Ниже содержится полный текст юридического документа:

---
{text}
---

Твоя задача:
1. Определи, какие ключевые пункты в документе наиболее важны для клиента.
2. Выяви риски и возможные проблемы.
3. Скажи, можно ли доверять документу — нет ли подозрительных или опасных условий.
4. Ответь простыми словами, ясно и по делу. Не используй фразы типа «я ИИ».

Если клиент не задал конкретный вопрос, просто сделай честный анализ и укажи, на что обратить внимание. Помни: твоя цель — защитить клиента и предупредить его о рисках.
"""


# --- Финальная архитектура с двумя маршрутами ---

# Маршрут №1: ТОЛЬКО для стриминга текста от ИИ
@app.route("/ask", methods=["POST"])
def ask_streaming():
    data = request.json
    question = data.get("question", "").strip()
    session_id = data.get("session_id", "default")

    if not question:
        return jsonify({"error": "Пустой вопрос"}), 400

    def generate_text():
        try:
            # Загружаем историю
            history = load_conversation(session_id)
            prompt = PROMPT_TEMPLATE.format(question=question)
            history.append({"role": "user", "parts": [prompt]})
            stream = model.generate_content(history, stream=True)

            full_reply = ""
            for chunk in stream:
                if chunk.text:
                    full_reply += chunk.text
                    yield chunk.text
            
            # Сохраняем сообщения
            save_message(session_id, "user", prompt)
            save_message(session_id, "model", full_reply)
        except Exception as e:
            print(f"❌ Ошибка в стриме /ask: {e}")
            yield "Ошибка генерации ответа ИИ."

    return Response(stream_with_context(generate_text()), mimetype='text/plain; charset=utf-8')


# Маршрут №2: ТОЛЬКО для поиска законов и финального форматирования
@app.route("/process-full-text", methods=["POST"])
def process_full_text():
    data = request.json
    question = data.get("question", "").strip()
    full_ai_text = data.get("full_ai_text", "")
    if not question or not full_ai_text:
        return jsonify({"error": "Отсутствует вопрос или текст ИИ"}), 400
    
    try:
        # Форматируем полный текст ответа ИИ в красивый HTML
        formatted_ai_html = convert_full_markdown_to_html(full_ai_text)
        
        # Ищем законы по оригинальному вопросу
        laws_found = find_laws_by_keywords(question)
        law_section_html = format_laws(laws_found)

        # Собираем все вместе
        final_html = formatted_ai_html + law_section_html
        return jsonify({"html": final_html})
    except Exception as e:
        print(f"❌ Ошибка в /process-full-text: {e}")
        return jsonify({"error": "Ошибка при финальной обработке"}), 500

# --- Статические маршруты ---
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

@app.route("/analyze-file", methods=["POST"])
def analyze_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Файл не получен"}), 400

    # Временное сохранение и чтение
    filepath = os.path.join("/tmp", file.filename)
    file.save(filepath)

    text = extract_text_from_file(filepath)  # Эта функция будет разной для docx/pdf
    os.remove(filepath)

    # Применяем промпт
    prompt = FILE_ANALYSIS_PROMPT.format(text=text[:8000])  # Ограничим объем
    response = model.generate_content(prompt)

    return jsonify({"analysis": response.text})


if __name__ == '__main__':
    load_law_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
