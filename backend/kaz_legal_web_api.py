from flask import Flask, request, jsonify, send_from_directory
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

# --- ОПТИМИЗАЦИЯ: Глобальные переменные для пред-обработанных данных ---
# В эту базу мы сложим уже полностью подготовленные для поиска статьи
LAW_DB_PREPROCESSED = []
# Эта структура позволит мгновенно находить синонимы
SYNONYM_TO_KEY_MAP = {}

# 🧠 Расширенный словарь синонимов и морфологии
LEGAL_SYNONYMS = {
    # ... (ваш словарь синонимов остается без изменений) ...
    'увольнение': ['увольн', 'расторж', 'прекращ', 'освобожд', 'уволь', 'расторгн', 'прекрат', 'дисциплинар', 'сокращ'],
    'зарплата': ['заработн', 'оплат', 'выплат', 'вознаграж', 'жалован', 'доход', 'премиальн', 'надбавк', 'зарплат'],
    'отпуск': ['отпуск', 'отдых', 'каникул', 'выходн', 'перерыв', 'отгул'],
    'больничный': ['больнич', 'нетрудоспособн', 'болезн', 'лечен', 'лист', 'временн', 'инвалидн'],
    'работа': ['труд', 'работ', 'служб', 'деятельност', 'занятост', 'профессион', 'должност'],
    'работник': ['сотрудник', 'служащ', 'персонал', 'кадр', 'работяг', 'трудящ'],
    'работодатель': ['наниматель', 'предприятие', 'организаци', 'компани', 'учрежден', 'руководител'],
    'жилье': ['жилищ', 'квартир', 'дом', 'помещен', 'недвижимост', 'собственност', 'владен'],
    'аренда': ['аренд', 'найм', 'съем', 'поднайм', 'договор', 'плата'],
    'квартплата': ['коммунальн', 'услуг', 'содержан', 'эксплуатац', 'ремонт'],
    'выселение': ['выселен', 'изъят', 'освобожден', 'выдворен'],
    'пособие': ['пособи', 'выплат', 'социальн', 'помощ', 'поддержк', 'льгот', 'компенсац'],
    'пенсия': ['пенсион', 'выслуг', 'старост', 'инвалидн', 'потеря', 'кормилец'],
    'декрет': ['декретн', 'материнск', 'отцовск', 'ребенок', 'рожден', 'усыновлен'],
    'инвалидность': ['инвалидн', 'ограничен', 'группа', 'здоровье', 'реабилитац'],
    'договор': ['соглашен', 'контракт', 'сделк', 'обязательств', 'условие'],
    'долг': ['задолженност', 'обязательств', 'займ', 'кредит', 'взыскан'],
    'наследство': ['наследован', 'завещан', 'наследник', 'имуществ', 'право'],
    'развод': ['расторжен', 'брак', 'супруг', 'семейн', 'алимент'],
    'преступление': ['уголовн', 'правонарушен', 'деян', 'состав', 'вин', 'наказан'],
    'кража': ['хищен', 'присвоен', 'растрат', 'грабеж', 'разбой'],
    'мошенничество': ['обман', 'мошенн', 'афер', 'злоупотребл'],
    'штраф': ['администрат', 'взыскан', 'наказан', 'нарушен', 'санкци'],
    'права': ['правомочи', 'полномочи', 'свобод', 'гарант', 'защит'],
    'учитель': ['учител', 'преподавател', 'педагог', 'учительниц', 'препод'],
    'ученик': ['учащ', 'школьн', 'слушател', 'студент', 'воспитан'],
    'школа': ['школ', 'училищ', 'лицей', 'гимназ', 'колледж', 'образоват', 'учебн'],
    'насилие': ['насили', 'жесток', 'принужден', 'агресси', 'избиен', 'домашн', 'насильствен'],
    'побои': ['побо', 'избиен', 'рукоприкладств', 'удар', 'телесн', 'насильств']
}


# --- ОПТИМИЗАЦИЯ: Улучшенный и ускоренный поиск статей ---
def find_laws_by_keywords(question, max_results=5):
    results = []
    question_lower = question.lower()
    # Получаем уникальные слова из вопроса
    question_words = set(word for word in question_lower.split() if len(word) >= 3)
    
    print(f"🔍 Поиск по запросу: '{question}'")
    
    if not LAW_DB_PREPROCESSED:
        print("⚠️ Предварительно обработанная база данных пуста!")
        return []

    # --- ОПТИМИЗАЦИЯ: Расширение синонимами теперь гораздо быстрее ---
    expanded_terms = set(question_words)
    for word in question_words:
        # Ищем основное понятие через нашу новую карту синонимов
        key_term = SYNONYM_TO_KEY_MAP.get(word)
        if key_term:
            # Если нашли, добавляем все его синонимы
            expanded_terms.update(LEGAL_SYNONYMS.get(key_term, []))

    print(f"🔎 Расширенные термины поиска: {list(expanded_terms)[:10]}...")

    # --- ОПТИМИЗАЦИЯ: Итерируемся по пред-обработанной базе ---
    for entry in LAW_DB_PREPROCESSED:
        # Все данные уже в нижнем регистре и готовы к поиску
        title_lower = entry["title_lower"]
        combined_text_lower = entry["combined_text_lower"]
        
        # --- ОПТИМИЗАЦИЯ: Передаем готовые наборы слов для быстрого поиска ---
        relevance = calculate_relevance(
            question_lower, 
            expanded_terms, 
            title_lower, 
            combined_text_lower,
            entry["title_words"], # Набор слов из заголовка
            entry["text_words"]  # Набор слов из текста
        )

        if relevance > 0:
            # Копируем оригинальные данные статьи (не обработанные)
            result_entry = entry["original_data"].copy()
            result_entry["relevance"] = relevance
            results.append(result_entry)
            
    results.sort(key=lambda x: x["relevance"], reverse=True)
    print(f"📋 Найдено релевантных статей: {len(results)}")
    return results[:max_results]


# --- ОПТИМИЗАЦИЯ: Функция расчета релевантности теперь работает с множествами (sets) ---
def calculate_relevance(question, expanded_terms, title_lower, combined_text_lower, title_words, text_words):
    relevance = 0
    
    # 1. Точное совпадение фразы (остается без изменений)
    if question in combined_text_lower:
        relevance += 25  # Немного увеличим вес
    
    # --- ОПТИМИЗАЦИЯ: Проверка вхождения в МНОЖЕСТВО намного быстрее, чем в строку ---
    # 2. Совпадение в заголовке
    for term in expanded_terms:
        if term in title_words:
            relevance += 8
    
    # 3. Совпадение в тексте
    for term in expanded_terms:
        if term in text_words:
            relevance += 3

    # 4. Контекстный поиск (также теперь работает с множествами)
    context_boost = calculate_context_boost(expanded_terms, text_words)
    relevance += context_boost
    
    return relevance

# --- ОПТИМИЗАЦИЯ: Контекстный анализ тоже работает с множествами ---
def calculate_context_boost(question_terms, content_words):
    # Трудовые отношения
    if any(term in question_terms for term in ['увольн', 'работ', 'труд', 'зарплат']):
        if any(word in content_words for word in ['трудов', 'работник', 'работодатель', 'договор']):
            return 5
    # Жилищные вопросы
    if any(term in question_terms for term in ['квартир', 'дом', 'жилье', 'аренд']):
        if any(word in content_words for word in ['жилищ', 'собственност', 'найм']):
            return 5
    # Социальные вопросы
    if any(term in question_terms for term in ['пособи', 'пенси', 'льгот']):
        if any(word in content_words for word in ['социальн', 'выплат', 'поддержк']):
            return 5
    return 0


# --- ОПТИМИЗАЦИЯ: Главная функция загрузки и ОБРАБОТКИ базы данных ---
def load_and_preprocess_db():
    global LAW_DB_PREPROCESSED, SYNONYM_TO_KEY_MAP
    
    # --- Шаг 1: Создаем карту синонимов для быстрого доступа ---
    for key, synonyms in LEGAL_SYNONYMS.items():
        for synonym in synonyms:
            SYNONYM_TO_KEY_MAP[synonym] = key
    print("✅ Карта синонимов создана.")

    # --- Шаг 2: Загружаем и обрабатываем базу законов ---
    try:
        with open("laws/kazakh_laws.json", "r", encoding="utf-8") as f:
            raw_db = json.load(f)
        
        # Разделяем кодексы на отдельные статьи (как и раньше)
        articles = preprocess_laws_into_articles(raw_db)
        
        # --- Шаг 3: Проводим тяжелую обработку КАЖДОЙ статьи ОДИН РАЗ ---
        for article in articles:
            title_lower = article.get("title", "").lower()
            text_lower = article.get("text", "").lower()
            
            # Создаем наборы слов для БЫСТРОГО поиска
            title_words = set(re.findall(r'\b\w{3,}\b', title_lower))
            text_words = set(re.findall(r'\b\w{3,}\b', text_lower))

            LAW_DB_PREPROCESSED.append({
                "original_data": article, # Сохраняем оригинальные данные для вывода
                "title_lower": title_lower,
                "combined_text_lower": f"{title_lower} {text_lower}",
                "title_words": title_words,
                "text_words": text_words
            })
            
        print(f"✅ База данных загружена и обработана! Статей в базе: {len(LAW_DB_PREPROCESSED)}")
        if LAW_DB_PREPROCESSED:
            print(f"📋 Пример обработанной записи: {list(LAW_DB_PREPROCESSED[0].keys())}")

    except Exception as e:
        print(f"❌ Ошибка загрузки или обработки базы законов: {e}")
        LAW_DB_PREPROCESSED = []

# Вспомогательная функция для разделения на статьи (ваш код, немного почищен)
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
                if current_title:
                    records.append({
                        "title": f"{code_name}: {current_title}",
                        "text": " ".join(buffer).strip(),
                        "source": source,
                    })
                buffer = [line] if len(line.split()) < 5 else [] # Начинаем буфер с коротких заголовков
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

# Запускаем загрузку и обработку при старте сервера
load_and_preprocess_db()


# --- Остальные функции (форматирование, эндпоинты) остаются почти без изменений ---
# ... (здесь идут ваши функции determine_source_by_content, format_laws, extract_article_info, 
# determine_code_name, PROMPT_TEMPLATE, convert_markdown_to_html, и все @app.route) ...

# 🎨 Определение источника по содержанию
def determine_source_by_content(content):
    content_lower = content.lower()
    source_mapping = {
        'уголовный кодекс': 'https://adilet.zan.kz/rus/docs/K1400000226',
        'уголовн': 'https://adilet.zan.kz/rus/docs/K1400000226',
        'кодекс об административных правонарушениях': 'https://adilet.zan.kz/rus/docs/K1400000235',
        'администрат': 'https://adilet.zan.kz/rus/docs/K1400000235',
        'социальный кодекс': 'https://adilet.zan.kz/rus/docs/K2300000224',
        'социальн': 'https://adilet.zan.kz/rus/docs/K2300000224',
        'экологический кодекс': 'https://adilet.zan.kz/rus/docs/K2100000400',
        'экологич': 'https://adilet.zan.kz/rus/docs/K2100000400',
        'гражданский кодекс': 'https://adilet.zan.kz/rus/docs/K990000409_',
        'гражданск': 'https://adilet.zan.kz/rus/docs/K990000409_',
        'водный кодекс': 'https://adilet.zan.kz/rus/docs/K2500000178',
        'водн': 'https://adilet.zan.kz/rus/docs/K2500000178',
        'гражданский процессуальный кодекс': 'https://adilet.zan.kz/rus/docs/K1500000377',
        'процессуальн': 'https://adilet.zan.kz/rus/docs/K1500000377',
        'предпринимательский кодекс': 'https://adilet.zan.kz/rus/docs/K1500000375',
        'предпринимательск': 'https://adilet.zan.kz/rus/docs/K1500000375',
        'бюджетный кодекс': 'https://adilet.zan.kz/rus/docs/K2500000171',
        'бюджетн': 'https://adilet.zan.kz/rus/docs/K2500000171',
        'трудовой кодекс': 'https://adilet.zan.kz/rus/docs/K1500000414',
        'трудов': 'https://adilet.zan.kz/rus/docs/K1500000414',
        'семейный кодекс': 'https://adilet.zan.kz/rus/docs/K1100000518',
        'семейн': 'https://adilet.zan.kz/rus/docs/K1100000518',
        'налоговый кодекс': 'https://adilet.zan.kz/rus/docs/K1700000120',
        'налогов': 'https://adilet.zan.kz/rus/docs/K1700000120',
        'земельный кодекс': 'https://adilet.zan.kz/rus/docs/K030000442_',
        'земельн': 'https://adilet.zan.kz/rus/docs/K030000442_'
    }
    for keyword, url in source_mapping.items():
        if keyword in content_lower:
            return url
    return "https://adilet.zan.kz"

# 📄 Форматируем статьи с подробными источниками (ваш код с tooltip)
def format_laws(laws):
    if not laws:
        return "<br><div style='background: #fff3cd; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #ffc107;'>⚠️ <strong>По вашему запросу подходящих статей не найдено.</strong><br><small style='color: #856404;'>Попробуйте переформулировать вопрос или используйте другие ключевые слова.</small></div>"

    output = "<br><div style='background: #e8f4fd; padding: 20px; border-radius: 10px; margin: 15px 0; border-left: 4px solid #0066cc;'>"
    output += "<h3 style='color: #0066cc; margin-top: 0;'>📚 Релевантные статьи законодательства РК</h3>"

    for i, law in enumerate(laws, 1):
        title = law.get('title', 'Без названия')
        text = law.get('text', 'Текст недоступен')
        source = law.get('source', 'https://adilet.zan.kz')
        relevance = law.get('relevance', 0)
        article_info = extract_article_info(title)
        code_name = determine_code_name(title + " " + text)
        preview = text[:400] + "..." if len(text) > 400 else text

        output += f"<div style='background: white; margin: 15px 0; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>"
        output += f"<div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;'>"
        output += f"<h4 style='color: #0066cc; margin: 0; flex: 1;'>{i}. {title}</h4>"
        output += f"</div>"
        
        if article_info:
            output += f"<div style='background: #f8f9fa; padding: 8px; border-radius: 4px; margin: 8px 0;'><strong style='color: #495057;'>📍 {article_info}</strong></div>"
        
        output += f"<div style='background: #fafbfc; padding: 10px; border-left: 3px solid #dee2e6; margin: 10px 0;'><p style='margin: 0; color: #555; line-height: 1.5;'>{preview}</p></div>"
        
        output += f"<div style='display: flex; justify-content: space-between; align-items: center; margin-top: 12px;'>"
        output += f"<span style='color: #6c757d; font-size: 13px;'><strong>Источник:</strong> {code_name}</span>"
        
        tooltip_html_text = "Это 'очки релевантности', а не проценты. Чем выше значение, тем больше статья соответствует вашему запросу. Очки начисляются за совпадения ключевых слов в заголовке и тексте статьи."
        relevance_display = f"""
        <div class="tooltip-container">
            <span style='background: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; white-space: nowrap;'>
                📊 Релевантность: {relevance}
            </span>
            <span class="tooltip-text">{tooltip_html_text}</span>
        </div>
        """
        
        output += f"<div style='display: flex; align-items: center; gap: 15px;'>"
        output += relevance_display
        output += f"<a href='{source}' target='_blank' style='background: #007bff; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: 500;'>🔗 Читать полностью</a>"
        output += f"</div>"
        
        output += f"</div></div>"

    output += "</div>"
    return output

# 🔍 Извлечение информации о статье
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

# 📖 Определение названия кодекса
def determine_code_name(content):
    content_lower = content.lower()
    code_mapping = {
        'уголовн': 'Уголовный кодекс РК',
        'администрат': 'Кодекс об административных правонарушениях РК',
        'социальн': 'Социальный кодекс РК',
        'экологич': 'Экологический кодекс РК',
        'гражданск': 'Гражданский кодекс РК',
        'водн': 'Водный кодекс РК',
        'процессуальн': 'Гражданский процессуальный кодекс РК',
        'предпринимательск': 'Предпринимательский кодекс РК',
        'бюджетн': 'Бюджетный кодекс РК',
        'трудов': 'Трудовой кодекс РК',
        'семейн': 'Семейный кодекс РК',
        'налогов': 'Налоговый кодекс РК',
        'земельн': 'Земельный кодекс РК'
    }
    for keyword, name in code_mapping.items():
        if keyword in content_lower:
            return name
    return "Законодательство РК"

# 🧠 PROMPT для ИИ-юриста
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

Пример хорошего форматирования:
**Что делать:**
1. **Обратитесь в суд** с исковым заявлением
2. **Соберите документы:** договор, справки, чеки
• Сохраните все переписки
• Сделайте фотокопии документов

**Шаблон заявления**
[текст шаблона]

Вот вопрос пользователя: 
---
{question}
"""

# 🎨 Конвертация Markdown в HTML
def convert_markdown_to_html(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'^• ', '<span class="bullet">🔸</span> ', text, flags=re.MULTILINE)
    text = re.sub(r'^\* ', '<span class="bullet">🔸</span> ', text, flags=re.MULTILINE)
    text = re.sub(r'^- ', '<span class="bullet">🔸</span> ', text, flags=re.MULTILINE)
    text = re.sub(r'^(\d+)\. ', r'<strong class="number">\1.</strong> ', text, flags=re.MULTILINE)
    lines = text.split('\n')
    formatted = []
    for line in lines:
        if '<span class="bullet">' in line or '<strong class="number">' in line:
            formatted.append(f'<div class="list-item">{line}</div>')
        else:
            formatted.append(line)
    return '\n'.join(formatted)

# 🔁 POST /ask
@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "Пустой вопрос"}), 400

        try:
            laws_found = find_laws_by_keywords(question)
            law_section = format_laws(laws_found)
        except Exception as e:
            print(f"❌ Ошибка поиска в базе: {e}")
            law_section = "<br><div style='background: #fff3cd; padding: 15px; border-radius: 8px; margin: 10px 0;'>⚠️ <strong>Временные проблемы с поиском в базе законов.</strong></div>"

        try:
            prompt = PROMPT_TEMPLATE.format(question=question)
            response = model.generate_content(prompt)
            if response.text:
                formatted = convert_markdown_to_html(response.text)
                final = f"{formatted}{law_section}"
                return jsonify({"answer": final})
            else:
                return jsonify({"error": "ИИ не дал ответа"}), 500
        except Exception as e:
            print(f"❌ Ошибка ИИ: {e}")
            return jsonify({"error": f"Ошибка обращения к ИИ: {str(e)}"}), 500
            
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

# 🌐 Главная страница
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# 📁 Служебные файлы
@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
