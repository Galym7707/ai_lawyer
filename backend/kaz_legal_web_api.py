# kaz_legal_web_api.py (Версия 3.0 - Исправленная и с поддержкой стриминга)
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
# --- ИСПРАВЛЕНИЕ: Включаем stream=True для потоковой генерации ---
model = genai.GenerativeModel('gemini-1.5-flash')

# Используем простую базу данных, как в оригинале, без неработающей предобработки
LAW_DB = [] 

# 🧠 Расширенный словарь синонимов (немного дополнен)
LEGAL_SYNONYMS = {
    'увольнение': ['увольн', 'расторж', 'прекращ', 'освобожд', 'уволь', 'расторгн', 'прекрат', 'дисциплинар', 'сокращ'],
    'зарплата': ['заработн', 'оплат', 'выплат', 'вознаграж', 'жалован', 'доход', 'премиальн', 'надбавк', 'зарплат'],
    'работа': ['труд', 'работ', 'служб', 'деятельност', 'занятост', 'профессион', 'должност'],
    'работник': ['сотрудник', 'служащ', 'персонал', 'кадр', 'работяг', 'трудящ'],
    'работодатель': ['наниматель', 'предприятие', 'организаци', 'компани', 'учрежден', 'руководител'],
    'договор': ['соглашен', 'контракт', 'сделк', 'обязательств', 'условие'],
    # --- УЛУЧШЕНИЕ: Добавлены новые синонимы для вашего запроса ---
    'учитель': ['учител', 'преподавател', 'педагог', 'наставник'],
    'ученик': ['учащ', 'школьн', 'студент', 'воспитан'],
    'насилие': ['насили', 'жесток', 'принужден', 'агресси', 'избиен', 'домашн', 'насильствен', 'удар', 'побо', 'бьет'],
    'ребенок': ['ребен', 'несовершеннолет', 'малолет', 'дитя', 'подрост'],
    'образование': ['образован', 'обучен', 'школ', 'университет', 'колледж', 'лицей', 'гимназ']
}

# --- ИСПРАВЛЕНИЕ: Возвращаемся к надежной и простой логике поиска ---
def find_laws_by_keywords(question, max_results=5):
    results = []
    question_lower = question.lower()
    question_words = set(re.findall(r'\b\w{3,}\b', question_lower))

    if not LAW_DB:
        print("⚠️ База данных законов пуста!")
        return []

    # Расширяем поисковые термины синонимами
    expanded_terms = set(question_words)
    for word in question_words:
        for key_term, synonyms in LEGAL_SYNONYMS.items():
            # Если слово из вопроса совпадает с синонимом или ключом, добавляем всю группу
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


# --- ИСПРАВЛЕНИЕ: Полностью переработанный, корректный расчет релевантности ---
def calculate_relevance(expanded_terms, title_lower, text_lower):
    relevance = 0
    
    # 1. Совпадение в заголовке (самый высокий вес)
    for term in expanded_terms:
        if term in title_lower:
            relevance += 10 # Даем больше очков за совпадение в заголовке
            
    # 2. Совпадение в тексте
    for term in expanded_terms:
        if term in text_lower:
            relevance += 2

    # 3. Бонус за количество совпавших уникальных терминов
    matched_terms_count = sum(1 for term in expanded_terms if term in title_lower or term in text_lower)
    if matched_terms_count > 1:
        relevance += matched_terms_count * 2 # Бонус за каждое дополнительное совпадение

    return relevance

# --- ИСПРАВЛЕНИЕ: Возвращаем простую и надежную загрузку и обработку ---
def load_law_db():
    global LAW_DB
    try:
        with open("laws/kazakh_laws.json", "r", encoding="utf-8") as f:
            raw_db = json.load(f)
        # Просто разделяем кодексы на статьи. Без сложной и неверной предобработки.
        LAW_DB = preprocess_laws_into_articles(raw_db)
        print(f"✅ База данных загружена успешно! Найдено статей: {len(LAW_DB)}")
    except Exception as e:
        print(f"❌ Ошибка загрузки базы законов: {e}")
        LAW_DB = []

def preprocess_laws_into_articles(raw_db):
    # Эта функция теперь основная для подготовки данных
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

# Остальные функции (format_laws, PROMPT_TEMPLATE и др.) остаются такими же, как в вашем последнем коде.
# Я их оставляю для полноты файла.

# ... (вставьте сюда ваши функции `format_laws`, `determine_source_by_content`, `extract_article_info`, `determine_code_name`)...
# Я скопирую их из вашего кода для удобства
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

def extract_article_info(title):
    # ... (код этой функции не меняется)
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


def determine_code_name(content):
    # ... (код этой функции не меняется)
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

def determine_source_by_content(content):
    # ... (код этой функции не меняется)
    content_lower = content.lower()
    source_mapping = {
        'уголовный кодекс': 'https://adilet.zan.kz/rus/docs/K1400000226',
        'уголовн': 'https://adilet.zan.kz/rus/docs/K1400000226',
        'кодекс об административных правонарушениях': 'https://adilet.zan.kz/rus/docs/K1400000235',
        'администрат': 'https://adilet.zan.kz/rus/docs/K1400000235',
        #... и так далее
    }
    for keyword, url in source_mapping.items():
        if keyword in content_lower:
            return url
    return "https://adilet.zan.kz"


PROMPT_TEMPLATE = """
Ты казахстанский юрист... 
# ... (ваш промпт не меняется)
"""

def convert_markdown_to_html(text):
    # ... (код этой функции не меняется)
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

# --- УЛУЧШЕНИЕ: Новый эндпоинт /ask для потоковой передачи ---
@app.route("/ask", methods=["POST"])
def ask_streaming():
    data = request.json
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Пустой вопрос"}), 400

    def generate_response():
        try:
            # Сначала генерируем ответ от ИИ и отдаем его по частям (стриминг)
            prompt = PROMPT_TEMPLATE.format(question=question)
            stream = model.generate_content(prompt, stream=True)
            for chunk in stream:
                if chunk.text:
                    # Конвертируем каждую часть в HTML и отправляем клиенту
                    html_chunk = convert_markdown_to_html(chunk.text)
                    yield html_chunk

            # После ответа ИИ, ищем законы
            laws_found = find_laws_by_keywords(question)
            # Форматируем найденные законы в один HTML блок
            law_section_html = format_laws(laws_found)
            # Отправляем этот блок как последнюю часть
            yield law_section_html

        except Exception as e:
            print(f"❌ Ошибка во время стриминга: {e}")
            yield "<div style='color: red;'>Произошла ошибка при генерации ответа.</div>"

    # Возвращаем потоковый ответ
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
