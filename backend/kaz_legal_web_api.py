# -*- coding: utf-8 -*-
"""
Основной веб-сервер для Kaz Legal Bot.

Этот модуль реализует API, позволяющий отправлять текстовые запросы
искусственному интеллекту, загружать документы для анализа,
получать историю переписки и список существующих сессий. Код
содержит несколько исправлений по сравнению с исходной версией:

* Исправлена CORS-обработка OPTIONS для произвольных путей и добавлен DELETE.
* system_instruction формируется как f-строка (включает контекст законов).
* Исправлена обработка изображений через Gemini Vision.
* В sanitize_html_output разрешены теги <em> и <br>.
* Исправлено построение индекса законов и расширение ключевых слов.
"""

from memory import (
    init_db,
    save_message,
    load_conversation,
    delete_conversation,
    get_all_sessions_summary_mongo,
)
from flask import Flask, request, jsonify, Response, stream_with_context, make_response
import google.generativeai as genai
import os
import json
import re
import bleach
from PIL import Image, UnidentifiedImageError
from docx import Document
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
import logging
from lxml import html
from dotenv import load_dotenv
from helpers import expand_keywords, build_snippet
import unittest

# jamspell опционален
try:
    import jamspell  # type: ignore
except ImportError:
    jamspell = None

# === ENV ===
load_dotenv()
from env_validator import validate_environment_variables
validate_environment_variables()

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

# === CORS ===
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "https://ai-lawyer-tau.vercel.app,http://localhost:5000,http://127.0.0.1:5000",
).split(",")
logging.info(f"✅ CORS configured for origins: {cors_origins}")

def add_cors_headers(response):
    """Добавляет CORS-заголовки к ответу."""
    origin = request.headers.get("Origin", "")
    if origin in cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        # можно не выставлять вовсе, но оставим безопасный дефолт
        response.headers["Access-Control-Allow-Origin"] = cors_origins[0]
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response

@app.after_request
def apply_cors(resp):
    return add_cors_headers(resp)

@app.route("/<path:path>", methods=["OPTIONS"])
def handle_options(path):
    return add_cors_headers(make_response())

# === Gemini init ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    logging.error("❌ GEMINI_API_KEY не установлен. Приложение не может запуститься.")
    raise EnvironmentError("GEMINI_API_KEY is not set.")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"response_mime_type": "text/plain", "temperature": 0.7},
)
vision_model = genai.GenerativeModel("gemini-1.5-flash")

# === JamSpell ===
if jamspell is not None:
    try:
        _jsp = jamspell.TSpellCorrector()
        if _jsp.LoadLangModel("ru.bin"):
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

# === Laws ===
LAW_DB: list = []
LAW_INDEX: dict = {}

# Внимание: в исходнике были дубли ключей. Здесь оставлен один словарь;
# расширение ключевых слов в helpers.expand_keywords учитывает и ключ, и значения.
LEGAL_SYNONYMS = {
    "увольнение": ["уволен", "увольняет", "сокращение", "расторжение договора", "прекращение трудового договора", "расчет"],
    "отпуск": ["отпускные", "ежегодный отпуск", "трудовой отпуск", "больничный", "декретный отпуск"],
    "зарплата": ["заработная плата", "оплата труда", "выплата", "аванс", "расчет", "оклад", "премия"],
    "трудовой договор": ["трудовой контракт", "договор", "соглашение о труде", "контракт"],
    "работодатель": ["компания", "фирма", "предприятие", "начальник", "руководство", "организация"],
    "работник": ["сотрудник", "персонал", "служащий", "подчиненный"],
    "ип": ["индивидуальный предприниматель", "предприниматель", "ипшник", "частник"],
    "усн": ["упрощенная система налогообложения", "упрощенка"],
    "налог": ["налоги", "налоговый", "сбор", "пошлина", "ндс", "кпн", "ипн", "социальный налог", "отчисления", "взносы"],
    "енп": ["единый совокупный платеж"],
    "патент": ["специальный налоговый режим на основе патента"],
    "декларация": ["налоговая декларация", "отчетность"],
    "срок": ["сроки", "период", "дата"],
    "штраф": ["пени", "взыскание", "денежное взыскание", "санкция"],
    "развод": ["расторжение брака", "алименты", "раздел имущества"],
    "брак": ["женитьба", "семейный союз", "супружество"],
    "алименты": ["выплаты на ребенка", "содержание"],
    "имущество": ["недвижимость", "активы", "собственность", "владение", "право собственности"],
    "кража": ["хищение", "воровство", "грабеж", "разбой"],
    "мошенничество": ["обман", "афера", "подлог", "фальсификация"],
    "преступление": ["правонарушение", "уголовное дело", "деяние", "злодеяние"],
    "наказание": ["срок", "тюрьма", "лишение свободы", "санкция", "кара", "взыскание"],
    "нарушение": ["проступок", "правонарушение"],
    "протокол": ["административный протокол", "документ", "акт"],
    "возмещение ущерба": ["компенсация", "возмещение убытков"],
    "иск": ["исковое заявление", "судебный иск", "претензия"],
    "закон": ["кодекс", "нормативный акт", "постановление", "правила"],
    "статья": ["пункт", "часть", "подпункт"],
    "суд": ["судебный орган", "правосудие", "истец", "ответчик"],
    "жалоба": ["обращение", "заявление", "петиция"],
    "консультация": ["совет", "помощь", "разъяснение"],
    "документ": ["бумага", "справка", "акт", "удостоверение"],
    "убийство": ["умышленное убийство", "неосторожное убийство", "покушение на убийство"],
    "насилие": ["физическое насилие", "психологическое насилие", "сексуальное насилие"],
    "следствие": ["расследование", "дознание", "предварительное следствие"],
    "судебный процесс": ["судебное разбирательство", "процесс", "слушание"],
    "доказательства": ["улики", "свидетельства", "материалы дела"],
    "приговор": ["решение суда", "вердикт", "постановление"],
    "договор": ["контракт", "соглашение", "пакт", "договоренность"],
    "обязательство": ["долг", "ответственность", "обязанность"],
    "право": ["законное право", "юридическое право", "привилегия"],
    "сделка": ["операция", "транзакция", "соглашение"],
    "решение суда": ["приговор", "постановление", "вердикт"],
    "апелляция": ["обжалование", "апелляционная жалоба", "вторая инстанция"],
    "кассация": ["кассационная жалоба", "третья инстанция", "надзор"],
    "административное правонарушение": ["административный проступок", "нарушение"],
    "административный арест": ["задержание", "арест", "лишение свободы"],
    "трудовой договор": ["контракт", "соглашение о труде"],
    "работодатель": ["наниматель", "компания", "организация"],
    "работник": ["служащий", "персонал", "сотрудник"],
    "зарплата": ["оплата труда", "вознаграждение", "заработная плата"],
    "отпуск": ["каникулы", "отдых", "трудовой отпуск"],
    "налоговая декларация": ["отчётность", "декларация о доходах"],
    "ндс": ["налог на добавленную стоимость"],
    "кпн": ["корпоративный подоходный налог"],
    "ипн": ["индивидуальный подоходный налог"],
    "социальный налог": ["соцналог", "отчисления"],
    "медицинская помощь": ["лечение", "уход", "медицинские услуги"],
    "пациент": ["больной", "клиент"],
    "врач": ["доктор", "медик", "специалист"],
    "лекарство": ["препарат", "медикамент", "средство"],
    "недра": ["ресурсы", "ископаемые", "полезные ископаемые"],
    "добыча": ["извлечение", "разработка", "эксплуатация"],
    "ресурсы": ["природные ресурсы", "запасы", "богатства"],
    "лицензия": ["разрешение", "право", "сертификат"],
    "контракт": ["договор", "соглашение", "пакт"],
    "жилье": ["квартира", "дом", "недвижимость"],
    "аренда": ["наем", "прокат"],
    "бюджет": ["финансовый план", "смета"],
    "расходы": ["затраты", "издержки", "траты"],
    "доходы": ["прибыль", "заработок", "выручка"],
    "дефицит": ["недостаток", "недостача"],
    "финансирование": ["денежное обеспечение"],
    "таможня": ["таможенный контроль", "таможенный пост"],
    "импорт": ["ввоз"],
    "экспорт": ["вывоз"],
    "пошлина": ["таможенная пошлина", "налог"],
    "предприниматель": ["бизнесмен", "делец", "коммерсант"],
    "бизнес": ["предпринимательство", "коммерция"],
    "компания": ["фирма", "организация", "предприятие"],
    "регистрация": ["оформление", "запись"],
    "выборы": ["голосование", "избрание"],
    "кандидат": ["претендент", "участник"],
    "избиратель": ["голосующий", "электорат"],
    "бюллетень": ["избирательный бюллетень", "голосовательный лист"],
    "опека": ["попечительство", "забота"],
    "усыновление": ["удочерение", "принятие в семью"],
    "экология": ["окружающая среда", "природа"],
    "загрязнение": ["заражение", "отравление"],
    "охрана природы": ["защита природы", "природоохранная деятельность"],
    "военная служба": ["служба в армии", "военная обязанность"],
    "военнослужащий": ["солдат", "офицер", "военный"],
    "призыв": ["мобилизация", "набор"],
    "звание": ["ранг", "чин"],
}

MONGO_URI = os.getenv("MONGO_URI")
if MONGO_URI:
    init_db()
else:
    logging.error("❌ Ошибка: Переменная окружения MONGO_URI не установлена. Подключение к MongoDB невозможно.")

def load_law_db(path: str = "laws/kazakh_laws.json") -> None:
    """Загружает базу данных законов из файла и строит индекс."""
    global LAW_DB
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            LAW_DB = json.load(f)
        logging.info(f"✅ Загружено {len(LAW_DB)} статей из базы законов.")
        build_law_index()
    else:
        logging.warning(f"⚠️ База законов не найдена по пути: {path}. Поиск будет ограничен.")

# === Health ===
@app.route("/health", methods=["GET"])
def health_check():
    import datetime
    cors_config = {
        "origins": list(cors_origins),
        "methods": "GET, POST, DELETE, OPTIONS",
        "headers": "Content-Type, Authorization",
        "credentials": True,
    }
    response_data = {
        "status": "healthy",
        "port": int(os.getenv("PORT", 5000)),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "cors": cors_config,
    }
    return add_cors_headers(jsonify(response_data)), 200

@app.route("/api/health", methods=["GET"])
def health_check_api():
    return health_check()

# === Utils ===
def clean_and_format_html(text: str) -> str:
    """Преобразует сырой текст с маркерами SECTION/LIST_ITEM в HTML."""
    text = re.sub(r"\s*\n\s*\n\s*", "\n\n", text or "").strip()
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)

    if jsp is not None:
        try:
            text = jsp.FixFragment(text)
        except Exception as e:
            logging.warning(f"⚠️ Ошибка JamSpell: {e}. Продолжаем без исправления.")

    lines = (text or "").split("\n\n")
    formatted = []
    in_list = False
    last_section = ""

    expected_sections = {
        "юридическая оценка": "Юридическая оценка ситуации",
        "действие": "Действие",
        "рекомендации": "Рекомендации",
        "необходимая информация": "Необходимая информация",
        "экстренные контакты": "Экстренные контакты",
        "релевантные законы": "Релевантные законы",
    }

    recommendations_labels = {
        "напишите работодателю": "Письменное требование",
        "обратитесь в территориальное": "Обращение в инспекцию труда",
        "подготовьте исковое": "Исковое заявление",
        "собирайте все": "Документы",
        "сообщите о случившемся": "Уведомление родителей",
        "обратитесь в полицию": "Обращение в полицию",
        "обратитесь в медицинское учреждение": "Медицинский осмотр",
        "сохраните все доказательства": "Сбор доказательств",
        "по возможности соберите": "Свидетельские показания",
        "рассмотрите возможность": "Жалоба в органы образования",
    }
    info_labels = {
        "ваш трудовой договор": "Трудовой договор",
        "точная сумма задолженности": "Сумма задолженности",
        "дата последней выплаты": "Дата последней выплаты",
        "наличие каких-либо соглашений": "Соглашения о задержке",
        "причины задержки": "Причины задержки",
        "подробное описание инцидента": "Описание инцидента",
        "степень тяжести полученных травм": "Степень травм",
        "свидетели": "Свидетели",
        "данные об учителе": "Данные об учителе",
        "данные о школе": "Данные о школе",
    }

    for raw_line in lines:
        line = (raw_line or "").strip()
        if not line:
            continue

        if line.lower().startswith("section:") or line.lower() in expected_sections:
            if in_list:
                formatted.append("</ul>")
                in_list = False

            heading = line.replace("SECTION:", "").strip()
            human_heading = expected_sections.get(heading.lower(), heading)
            formatted.append(f"<h3>{human_heading}</h3>")
            last_section = heading.lower()

            if last_section == "необходимая информация":
                formatted.append(
                    "<p>Для качественного предоставления услуги с моей стороны как юриста, "
                    "мне потребуется следующая информация:</p>"
                )
            elif last_section == "экстренные контакты":
                formatted.append("<p>В экстренных случаях обращайтесь:</p>")
            continue

        if line.startswith("LIST_ITEM:") or line.startswith("-") or re.match(r"^\d+\.\s+", line):
            if not in_list:
                formatted.append("<ul>")
                in_list = True

            line_clean = re.sub(r"^\d+\.\s+", "", line.lstrip("- ").strip())
            line_clean = line_clean.replace("LIST_ITEM:", "").strip()

            if ":" in line_clean:
                label, content = line_clean.split(":", 1)
                label = label.strip()
                if last_section == "рекомендации":
                    label = recommendations_labels.get(label.lower(), label)
                elif last_section == "необходимая информация":
                    label = info_labels.get(label.lower(), label)
                formatted.append(f"<li><strong>{label}:</strong> {content.strip()}</li>")
            else:
                formatted.append(f"<li>{line_clean}</li>")
            continue

        if in_list:
            formatted.append("</ul>")
            in_list = False

        if last_section == "юридическая оценка":
            formatted.append(f"<p><strong>Юридическая оценка:</strong> {line}</p>")
        else:
            formatted.append(f"<p>{line}</p>")

    if in_list:
        formatted.append("</ul>")

    return "\n".join(formatted)

def validate_html(text: str) -> bool:
    try:
        html.fromstring(text)
        return True
    except Exception as e:
        logging.warning(f"⚠️ Неверный HTML: {e}")
        return False

def sanitize_html_output(text: str) -> str:
    html_text = clean_and_format_html(text)
    if not validate_html(html_text):
        html_text = f"<p>{html_text}</p>"
    allowed_tags = ["p", "ul", "li", "h3", "strong", "em", "br"]
    allowed_attrs = {"strong": ["style"]}
    return bleach.clean(html_text, tags=allowed_tags, attributes=allowed_attrs, strip=True)

def validate_session_id(session_id: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", session_id or ""))

def build_law_index() -> None:
    """Строит простой инвертированный индекс по title+content."""
    global LAW_INDEX
    LAW_INDEX = {}
    for article in LAW_DB:
        content_lower = (article.get("content", "") or "").lower()
        title_lower = (article.get("title", "") or "").lower()
        words = set(re.findall(r"\b\w+\b", f"{title_lower} {content_lower}"))
        for w in words:
            LAW_INDEX.setdefault(w, []).append(article)

# Определён до вызова
load_law_db()

def find_relevant_laws(query: str) -> list:
    """Возвращает ТОП-5 статей по расширенным ключам."""
    if not LAW_INDEX:
        build_law_index()
    query_lower = (query or "").lower()
    query_keywords = set(re.findall(r"\b\w+\b", query_lower))
    expanded = expand_keywords(query_keywords, LEGAL_SYNONYMS)
    relevant = []
    seen = set()
    for kw in expanded:
        for art in LAW_INDEX.get(kw, []):
            art_id = art.get("id", art.get("title", ""))
            if art_id in seen:
                continue
            snippet = build_snippet(art.get("content", ""), expanded)
            relevant.append(
                {"title": art.get("title", "Без названия"), "link": art.get("link", "#"), "snippet": snippet}
            )
            seen.add(art_id)
    relevant.sort(key=lambda x: sum(kw in (x["snippet"] or "").lower() for kw in expanded), reverse=True)
    return relevant[:5]

def process_file_content(file_stream, mimetype: str):
    """Извлекает текст из PDF/DOCX/IMG/TXT."""
    text_content = ""
    try:
        if mimetype == "application/pdf":
            reader = PdfReader(file_stream)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content += extracted + "\n"
        elif mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            document = Document(file_stream)
            for paragraph in document.paragraphs:
                text_content += paragraph.text + "\n"
        elif mimetype.startswith("image/"):
            # Gemini Vision: контент = [Image, prompt]
            image = Image.open(file_stream)
            resp = vision_model.generate_content(
                [
                    image,
                    "Опиши этот документ или изображение. Извлеки весь текст и полезную для юриста информацию.",
                ]
            )
            text_content = resp.text or ""
        elif mimetype.startswith("text/"):
            text_content = file_stream.read().decode("utf-8", errors="ignore")
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

def generate_response_stream(model_obj, messages, session_id: str):
    """Генерирует ответ, чистит и сохраняет HTML; поток отдаем одним чанком."""
    try:
        raw_text = ""
        for chunk in model_obj.generate_content(messages, stream=True):
            if getattr(chunk, "text", None):
                raw_text += chunk.text

        # Убираем «дисклеймеры»
        unwanted_pattern = (
            r"(?:Важно|Обратите внимание|Примечание):?.*?"
            r"(?:носит общий характер|не является юридической консультацией|"
            r"необходимо обратиться к квалифицированному юристу|правоохранительные органы|другому юристу).*?(?:\.|\n)"
        )
        raw_text = re.sub(unwanted_pattern, "", raw_text, flags=re.IGNORECASE)

        sanitized = sanitize_html_output(raw_text)
        save_message(session_id, "model", sanitized)
        yield sanitized
        logging.info(f"✅ Ответ AI сохранён для сессии {session_id}")
    except Exception as e:
        logging.error(f"❌ Ошибка генерации ответа: {e}")
        error_html = "<p>Произошла ошибка при генерации ответа. Попробуйте ещё раз.</p>"
        save_message(session_id, "model", error_html)
        yield error_html

# === Routes ===
@app.route("/delete-session", methods=["DELETE"])
@app.route("/api/delete-session", methods=["DELETE"])
def delete_session_route():
    session_id = request.args.get("session_id")
    if not session_id or not validate_session_id(session_id):
        return add_cors_headers(jsonify({"error": "Недопустимый session_id"})), 400
    try:
        delete_conversation(session_id)
        return add_cors_headers(jsonify({"status": "ok"})), 200
    except Exception as e:
        logging.error(f"❌ Ошибка удаления сессии: {e}")
        return add_cors_headers(jsonify({"error": "Ошибка удаления сессии"})), 500

@app.route("/ask", methods=["POST"])
def ask_route():
    logging.info("🚀 Обработка запроса на /ask")
    try:
        data = request.get_json() or {}
        user_question = data.get("question", "")
        session_id = data.get("session_id", "default")
        if not validate_session_id(session_id):
            return add_cors_headers(jsonify({"error": "Недопустимый session_id"})), 400
        if not user_question:
            return add_cors_headers(jsonify({"error": "Пустой вопрос"})), 400

        save_message(session_id, "user", user_question)

        history = load_conversation(session_id)
        full_history = history + [{"role": "user", "parts": [user_question]}]

        relevant_laws = find_relevant_laws(user_question)
        law_context = ""
        if relevant_laws:
            law_context = "SECTION: Релевантные законы\n"
            for law in relevant_laws:
                law_context += f"LIST_ITEM: {law['title']}: {law['snippet']}\n"
            law_context += "\n"

        system_instruction = f"""
Ты - официальный ИИ-юрист, специализирующийся на законодательстве Республики Казахстан.
Строго форматируй ответ в HTML (<p>, <ul>/<li>, <strong>, <em>, <br>, <h3>).
Разделы: SECTION/Листай LIST_ITEM при необходимости.

{law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях."}
""".strip()

        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history
        resp = Response(
            stream_with_context(generate_response_stream(model, messages_for_model, session_id)),
            mimetype="text/html",
        )
        return add_cors_headers(resp)
    except Exception as e:
        logging.error(f"❌ Ошибка в /ask: {e}")
        return add_cors_headers(jsonify({"error": f"Ошибка сервера при обработке запроса: {str(e)}"})), 500

@app.route("/api/ask", methods=["POST"])
def ask_route_api():
    return ask_route()

@app.route("/upload-document", methods=["POST"])
def upload_document_route():
    logging.info("🚀 Обработка запроса на /upload-document")
    try:
        user_file = request.files.get("file")
        user_question = request.form.get("question", "")
        session_id = request.form.get("session_id", "default")
        if not validate_session_id(session_id):
            return add_cors_headers(jsonify({"error": "Недопустимый session_id"})), 400
        if not user_file:
            return add_cors_headers(jsonify({"error": "Файл не предоставлен"})), 400

        mimetype = user_file.mimetype
        logging.info(f"📁 Получен файл: {user_file.filename} / {mimetype}")

        file_text = process_file_content(file_stream=user_file.stream, mimetype=mimetype)
        if file_text is None:
            return add_cors_headers(jsonify({"error": "Неподдерживаемый или поврежденный тип файла."})), 400

        file_message_content = (
            f"SECTION: Загруженный документ\nПользователь загрузил документ ({user_file.filename}). "
            f"Содержимое документа:\n{file_text[:2000]}...\n"
        )
        save_message(session_id, "user", file_message_content)
        if user_question:
            save_message(session_id, "user", user_question)

        combined_text = (file_text or "") + " " + (user_question or "")
        relevant_laws = find_relevant_laws(combined_text)
        law_context = ""
        if relevant_laws:
            law_context = "SECTION: Релевантные законы\n"
            for law in relevant_laws:
                law_context += f"LIST_ITEM: {law['title']}: {law['snippet']}\n"
            law_context += "\n"

        system_instruction = f"""
Ты - официальный ИИ-юрист, специализирующийся на законодательстве Республики Казахстан.
Строго форматируй ответ в HTML (<p>, <ul>/<li>, <strong>, <em>, <br>, <h3>).
Разделы: SECTION/Листай LIST_ITEM при необходимости.

{law_context if law_context else "У тебя нет доступа к актуальной базе законодательства. Отвечай на общие юридические вопросы, основываясь на твоих знаниях."}
""".strip()

        history = load_conversation(session_id)
        full_history = history + [{"role": "user", "parts": [user_question]}] if user_question else history
        messages_for_model = [{"role": "user", "parts": [system_instruction]}] + full_history

        resp = Response(
            stream_with_context(generate_response_stream(model, messages_for_model, session_id)),
            mimetype="text/html",
        )
        return add_cors_headers(resp)
    except Exception as e:
        logging.error(f"❌ Ошибка в /upload-document: {e}")
        return add_cors_headers(jsonify({"error": f"Ошибка сервера при обработке документа: {str(e)}"})), 500

@app.route("/api/upload-document", methods=["POST"])
def upload_document_route_api():
    return upload_document_route()

@app.route("/get-all-sessions-summary", methods=["GET"])
def get_all_sessions_summary_route():
    logging.info("🚀 Обработка запроса на /get-all-sessions-summary")
    try:
        sessions_summary = get_all_sessions_summary_mongo()
        return add_cors_headers(jsonify({"sessions": sessions_summary if sessions_summary else []})), 200
    except Exception as e:
        logging.error(f"❌ Ошибка при получении сводки сессий: {str(e)}")
        return add_cors_headers(jsonify({"error": f"Ошибка при получении сводки сессий: {str(e)}"})), 500

@app.route("/api/get-all-sessions-summary", methods=["GET"])
def get_all_sessions_summary_route_api():
    return get_all_sessions_summary_route()

@app.route("/get-history", methods=["GET"])
def get_history_route():
    logging.info("🚀 Обработка запроса на /get-history")
    try:
        session_id = request.args.get("session_id", "default")
        if not validate_session_id(session_id):
            return add_cors_headers(jsonify({"error": "Недопустимый session_id"})), 400
        history = load_conversation(session_id)
        formatted = []
        for msg in history:
            if isinstance(msg.get("parts"), list):
                part = msg["parts"][0]
                content = part["text"] if isinstance(part, dict) and "text" in part else part
            else:
                content = msg.get("parts")
            formatted.append({"role": msg.get("role"), "content": content})
        return add_cors_headers(jsonify({"history": formatted})), 200
    except Exception as e:
        logging.error(f"❌ Ошибка при получении истории: {str(e)}")
        return add_cors_headers(jsonify({"error": f"Ошибка при получении истории: {str(e)}"})), 500

@app.route("/api/get-history", methods=["GET"])
def get_history_route_api():
    return get_history_route()

# === Тест форматтера (локально) ===
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
        result = clean_and_format_html(input_text)
        assert "<h3>Юридическая оценка ситуации</h3>" in result
        assert "<li><strong>Полиция:</strong> 102</li>" in result

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
