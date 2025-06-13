# kaz_legal_web_api.py (Версия 4.0 - Расширенные словари и полные источники)
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
}


# --- УЛУЧШЕНИЕ: Полный и актуальный словарь источников ---
SOURCE_MAPPING = {
    'Уголовный кодекс': 'https://adilet.zan.kz/rus/docs/K1400000226',
    'уголовн': 'https://adilet.zan.kz/rus/docs/K1400000226',
    'Уголовно-процессуальный кодекс': 'https://adilet.zan.kz/rus/docs/K1400000231',
    'Уголовно-исполнительный кодекс': 'https://adilet.zan.kz/rus/docs/K1400000234',

    'Кодекс об административных правонарушениях': 'https://adilet.zan.kz/rus/docs/K1400000235',
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

    'Кодекс о браке (супружестве) и семье': 'https://adilet.zan.kz/rus/docs/K1100000518',
    'семейн': 'https://adilet.zan.kz/rus/docs/K1100000518',
    'брачн': 'https://adilet.zan.kz/rus/docs/K1100000518',

    'Кодекс о здоровье народа и системе здравоохранения': 'https://adilet.zan.kz/rus/docs/K2000000360',
    'здоровь': 'https://adilet.zan.kz/rus/docs/K2000000360',
    'медицин': 'https://adilet.zan.kz/rus/docs/K2000000360',

    'Экологический кодекс': 'https://adilet.zan.kz/rus/docs/K2100000400',
    'экологич': 'https://adilet.zan.kz/rus/docs/K2100000400',
    
    'Налоговый кодекс': 'https://adilet.zan.kz/rus/docs/K1700000120',
    'налогов': 'https://adilet.zan.kz/rus/docs/K1700000120',

    'Бюджетный кодекс': 'https://adilet.zan.kz/rus/docs/K080000095_',
    'бюджетн': 'https://adilet.zan.kz/rus/docs/K080000095_',

    'Таможенный кодекс': 'https://adilet.zan.kz/rus/docs/K1700000123',
    'таможен': 'https://adilet.zan.kz/rus/docs/K1700000123',

    'Земельный кодекс': 'https://adilet.zan.kz/rus/docs/K030000442_',
    'земельн': 'https://adilet.zan.kz/rus/docs/K030000442_',

    'Лесной кодекс': 'https://adilet.zan.kz/rus/docs/K030000473_',
    'лесн': 'https://adilet.zan.kz/rus/docs/K030000473_',

    'Водный кодекс': 'https://adilet.zan.kz/rus/docs/K1600000049',
    'водн': 'https://adilet.zan.kz/rus/docs/K1600000049',

    'Кодекс о недрах и недропользовании': 'https://adilet.zan.kz/rus/docs/K1700000125',
    'недра': 'https://adilet.zan.kz/rus/docs/K1700000125',
}


# --- Надежная логика поиска (Версия 3.0) ---
def find_laws_by_keywords(question, max_results=5):
    results = []
    question_lower = question.lower()
    question_words = set(re.findall(r'\b\w{3,}\b', question_lower))

    if not LAW_DB:
        print("⚠️ База данных законов пуста!")
        return []

    expanded_terms = set(question_words)
    for word in question_words:
        for key_term, synonyms in LEGAL_SYNONYMS.items():
            if word in synonyms or word == key_term:
                expanded_terms.update(synonyms)
                expanded_terms.add(key_term)
    
    print(f"🔎 Расширенные термины поиска: {expanded_terms}")

    for entry in LAW_DB:
        title_lower = entry.get("title", "").lower()
        text_lower = entry.get("text", "").lower()
        
        relevance = calculate_relevance(expanded_terms, title_lower, text_lower)

        if relevance > 0:
            entry_copy = entry.copy()
            entry_copy["relevance"] = relevance
            results.append(entry_copy)
            
    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:max_results]


# --- Корректный расчет релевантности (Версия 3.0) ---
def calculate_relevance(expanded_terms, title_lower, text_lower):
    relevance = 0
    
    for term in expanded_terms:
        if term in title_lower:
            relevance += 10
            
    for term in expanded_terms:
        if term in text_lower:
            relevance += 2

    matched_terms_count = sum(1 for term in expanded_terms if term in title_lower or term in text_lower)
    if matched_terms_count > 1:
        relevance += matched_terms_count * 2

    return relevance


# --- Надежная загрузка и обработка (Версия 3.0) ---
def load_law_db():
    global LAW_DB
    try:
        with open("laws/kazakh_laws.json", "r", encoding="utf-8") as f:
            raw_db = json.load(f)
        LAW_DB = preprocess_laws_into_articles(raw_db)
        print(f"✅ База данных загружена успешно! Найдено статей: {len(LAW_DB)}")
    except Exception as e:
        print(f"❌ Ошибка загрузки базы законов: {e}")
        LAW_DB = []

def preprocess_laws_into_articles(raw_db):
    records = []
    heading_pattern = re.compile(r'^(статья|глава|раздел|подраздел|параграф)', re.IGNORECASE)

    for code_entry in raw_db:
        code_name = code_entry.get("title", "Без названия")
        full_text = code_entry.get("text", "")
        source = code_entry.get("source") or determine_source_by_content(code_name)
        items = full_text.splitlines()
        current_title = None
        buffer = []

        for line in items:
            line = line.strip()
            if not line:
                continue
            
            if heading_pattern.match(line):
                if current_title and buffer:
                    records.append({
                        "title": f"{code_name}: {current_title}",
                        "text": " ".join(buffer).strip(),
                        "source": source,
                    })
                buffer = []
                current_title = line
            else:
                buffer.append(line)

        if current_title and buffer:
            records.append({
                "title": f"{code_name}: {current_title}",
                "text": " ".join(buffer).strip(),
                "source": source,
            })
    return records

load_law_db()


# --- Функции `determine_source_by_content` и `determine_code_name` теперь используют новый полный словарь ---
def determine_source_by_content(content):
    content_lower = content.lower()
    for keyword, url in SOURCE_MAPPING.items():
        if keyword in content_lower:
            return url
    return "https://adilet.zan.kz"

def determine_code_name(content):
    content_lower = content.lower()
    # Инвертируем словарь для получения имени по ключевому слову
    # Это упрощенный вариант, можно сделать и более надежный маппинг
    name_mapping = {
        'уголовн': 'Уголовный кодекс РК',
        'административн': 'КоАП РК',
        'гражданск': 'Гражданский кодекс РК',
        'процессуальн': 'ГПК РК',
        'трудов': 'Трудовой кодекс РК',
        'предпринимательск': 'Предпринимательский кодекс РК',
        'социальн': 'Социальный кодекс РК',
        'семейн': 'Кодекс о браке и семье РК',
        'здоровь': 'Кодекс о здоровье',
        'экологич': 'Экологический кодекс РК',
        'налогов': 'Налоговый кодекс РК',
        'бюджетн': 'Бюджетный кодекс РК',
        'таможен': 'Таможенный кодекс РК',
        'земельн': 'Земельный кодекс РК',
        'лесн': 'Лесной кодекс РК',
        'водн': 'Водный кодекс РК',
        'недра': 'Кодекс о недрах',
    }
    for keyword, name in name_mapping.items():
        if keyword in content_lower:
            return name
    return "Законодательство РК"


# 📄 Форматируем статьи с подробными источниками (без изменений)
def format_laws(laws):
    if not laws:
        # Используем классы для стилизации сообщения об ошибке
        return "<br><div class='notice warning'>⚠️ <strong>По вашему запросу подходящих статей не найдено.</strong><br><small>Попробуйте переформулировать вопрос или используйте другие ключевые слова.</small></div>"

    # Контейнер для всех карточек законов
    output = "<br><div class='laws-container'>"
    output += "<h3 class='laws-header'>📚 Релевантные статьи законодательства РК</h3>"

    for i, law in enumerate(laws, 1):
        title = law.get('title', 'Без названия')
        text = law.get('text', 'Текст недоступен')
        source = law.get('source') or determine_source_by_content(title)
        relevance = law.get('relevance', 0)
        article_info = extract_article_info(title)
        code_name = determine_code_name(title)
        preview = text[:400] + "..." if len(text) > 400 else text

        # Карточка для отдельной статьи
        output += "<div class='law-card'>"
        
        # Заголовок карточки
        output += "<div class='card-header'>"
        output += f"<h4 class='card-title'>{i}. {title}</h4>"
        output += "</div>"
        
        if article_info:
            output += f"<div class='card-meta'><strong>📍 {article_info}</strong></div>"
        
        # Тело карточки с текстом
        output += f"<div class='card-body'><p>{preview}</p></div>"
        
        # Подвал карточки
        output += "<div class='card-footer'>"
        output += f"<span class='card-source'><strong>Источник:</strong> {code_name}</span>"
        
        # Контейнер для правой части подвала (релевантность и кнопка)
        output += "<div class='footer-actions'>"
        
        tooltip_html_text = "Это 'очки релевантности', а не проценты. Чем выше значение, тем больше статья соответствует вашему запросу. Очки начисляются за совпадения ключевых слов в заголовке и тексте статьи."
        output += f"""
        <div class="tooltip-container card-relevance">
            <span>📊 {relevance}</span>
            <span class="tooltip-text">{tooltip_html_text}</span>
        </div>
        """
        output += f"<a href='{source}' target='_blank' class='card-link'>🔗 Читать полностью</a>"
        output += "</div>" # конец footer-actions
        
        output += "</div>" # конец card-footer
        output += "</div>" # конец law-card

    output += "</div>" # конец laws-container
    return output

def extract_article_info(title):
    patterns = [
        r'статья\s*(\d+)', r'ст\.\s*(\d+)', r'глава\s*(\d+)', r'гл\.\s*(\d+)',
        r'параграф\s*(\d+)', r'пункт\s*(\d+)', r'п\.\s*(\d+)',
        r'раздел\s*([IVX]+|\d+)', r'подраздел\s*(\d+)'
    ]
    found_parts = []
    title_lower = title.lower()
    for pattern in patterns:
        matches = re.findall(pattern, title_lower, re.IGNORECASE)
        for match in matches:
            if 'статья' in pattern or 'ст.' in pattern: found_parts.append(f"Статья {match}")
            elif 'глава' in pattern or 'гл.' in pattern: found_parts.append(f"Глава {match}")
            elif 'параграф' in pattern: found_parts.append(f"Параграф {match}")
            elif 'пункт' in pattern or 'п.' in pattern: found_parts.append(f"Пункт {match}")
            elif 'раздел' in pattern: found_parts.append(f"Раздел {match}")
            elif 'подраздел' in pattern: found_parts.append(f"Подраздел {match}")
    return ", ".join(found_parts) if found_parts else None

PROMPT_TEMPLATE = """
Ты казахстанский юрист, который помогает обычным людям разобраться в их правах. 
Твоя задача — объяснить юридические вопросы простыми словами, понятно даже для человека без образования в праве. 

ВАЖНО! Форматируй ответ красиво:
- Используй **жирный текст** для заголовков и важных моментов
- Структурируй информацию списками с • или цифрами  
- Выделяй ключевые действия жирным шрифтом
- Если предлагаешь шаблон документа, выдели его заголовок жирным

Если вопрос касается трудовых споров, аренды жилья или социальных пособий — отвечай чётко, по делу, со ссылкой на соответствующие нормы (если знаешь). 
Избегай сложной юридической лексики. 
Если можешь — предложи шаблон заявления или жалобы в конце ответа. 
Отвечай на русском языке.
Ответ должен быть не более 2500 символов.

Вот вопрос пользователя: 
---
{question}
"""

# 🎨 УЛУЧШЕННАЯ Конвертация Markdown в HTML с поддержкой абзацев
def convert_markdown_to_html(text):
    # 1. Сначала делаем базовые замены для жирного текста, курсива и кода
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)

    # 2. Разделяем весь текст на блоки по пустым строкам (это наши абзацы)
    paragraphs = text.split('\n\n')
    html_output = []

    for para in paragraphs:
        # Убираем лишние пробелы по краям абзаца
        para = para.strip()
        if not para:
            continue

        lines = para.split('\n')
        
        # 3. Проверяем, является ли блок списком
        first_line = lines[0].strip()
        is_list = re.match(r'^[•*-] |^\d+\. ', first_line)

        if is_list:
            # Если это список, обрабатываем каждую строку как элемент списка
            list_items = []
            for line in lines:
                line = re.sub(r'^[•*-] ', '<span class="bullet">🔸</span> ', line.strip())
                line = re.sub(r'^(\d+)\. ', r'<strong class="number">\1.</strong> ', line.strip())
                list_items.append(f'<div class="list-item">{line}</div>')
            html_output.append("".join(list_items))
        else:
            # 4. Если это обычный текст (например, наш шаблон),
            # мы соединяем строки с помощью <br> и оборачиваем всё в тег <p>
            # Это сохранит все переносы строк внутри шаблона.
            html_output.append(f"<p>{'<br>'.join(lines)}</p>")

    # Собираем все обработанные блоки в единый HTML
    return "".join(html_output)

# --- Эндпоинт /ask с потоковой передачей ---
@app.route("/ask", methods=["POST"])
def ask_streaming():
    data = request.json
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Пустой вопрос"}), 400

    def generate_response():
        try:
            prompt = PROMPT_TEMPLATE.format(question=question)
            stream = model.generate_content(prompt, stream=True)
            for chunk in stream:
                if chunk.text:
                    html_chunk = convert_markdown_to_html(chunk.text)
                    yield html_chunk

            laws_found = find_laws_by_keywords(question)
            law_section_html = format_laws(laws_found)
            yield law_section_html

        except Exception as e:
            print(f"❌ Ошибка во время стриминга: {e}")
            yield "<div style='color: red;'>Произошла ошибка при генерации ответа.</div>"

    return Response(stream_with_context(generate_response()), mimetype='text/html')

# Статические маршруты
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
