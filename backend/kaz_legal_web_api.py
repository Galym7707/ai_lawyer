# kaz_legal_web_api.py (Версия 4.5 — Переход на MongoDB, Улучшенный UX, строгая юрисдикция РК, приоритет уточняющих вопросов)
from memory import init_db, save_message, load_conversation, delete_conversation, get_all_sessions_summary_mongo # Добавили get_all_sessions_summary_mongo
init_db() # Инициализируем MongoDB соединение при старте приложения

from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
import google.generativeai as genai
import os
import json
import re
from flask_cors import CORS
# import sqlite3 # УДАЛИТЬ: больше не нужен
# from memory import DB_PATH # УДАЛИТЬ: больше не нужен

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 GB
CORS(app, origins=["https://ai-lawyer-tau.vercel.app"]) # Убедитесь, что здесь указан домен вашего фронтенда

# --- AI и база законов ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "text/plain", "temperature": 0.7})

LAW_DB = []

# --- УЛУЧШЕНИЕ: Максимально расширенный словарь синонимов (с добавлением налоговых терминов) ---
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
    'жкх': ['жкх', 'коммунальные услуги', 'управляющая компания', 'тсж', 'оскен', 'отопление', 'вода', 'электричество', 'счет', 'счета'],

    # Социальное право
    'пособие': ['пособи', 'выплата', 'выплат', 'социальное', 'социальн', 'помощь', 'поддержка', 'поддержк', 'льгота', 'льгот', 'компенсация', 'компенсац', 'субсидия'],
    'пенсия': ['пенсион', 'пенсионное', 'выслуга', 'старость', 'по старости', 'инвалидность', 'инвалидн', 'потеря кормильца', 'кормилец'],
    'декрет': ['декретн', 'материнство', 'материнск', 'отцовство', 'отцовск', 'ребенок', 'рождение', 'рожден', 'усыновление', 'усыновлен', 'беременность', 'беремен'],
    'инвалидность': ['инвалид', 'инвалидн', 'ограниченные', 'ограничен', 'возможности', 'группа', 'здоровье', 'реабилитация', 'реабилитац'],
    'льгота': ['льгота', 'льгот', 'привилегия', 'скидка', 'преференция'],

    # Гражданское право
    'договор': ['соглашение', 'соглашен', 'контракт', 'сделка', 'обязательство', 'обязательств', 'условие', 'условия', 'пакт', 'договоренность'],
    'долг': ['задолженность', 'задолженност', 'обязательство', 'обязательств', 'заем', 'займ', 'кредит', 'взыскание', 'взыскан', 'неуплата'],
    'наследство': ['наследование', 'наследован', 'завещание', 'завещан', 'наследник', 'имущество', 'имуществ', 'правопреемство'],
    'развод': ['расторжение', 'расторжен', 'брак', 'супруг', 'супруга', 'семейный', 'семейн', 'алименты', 'раздел имущества'],
    'алименты': ['алимент', 'содержание', 'выплата на ребенка', 'выплата на супруга'],
    'опека': ['опека', 'попечительство', 'усыновление', 'удочерение'],
    'суд': ['судебный', 'иск', 'исковое заявление', 'обращение в суд', 'судебное разбирательство'],
    'исковое заявление': ['иск', 'заявление в суд', 'подать в суд'],

    # Уголовное право
    'преступление': ['преступлен', 'уголовное', 'уголовн', 'правонарушение', 'правонарушен', 'деяние', 'деян', 'состав', 'вина', 'наказание', 'наказан', 'злодеяние', 'проступок'],
    'кража': ['краж', 'хищение', 'хищен', 'присвоение', 'присвоен', 'растрата', 'растрат', 'грабеж', 'разбой'],
    'мошенничество': ['мошенничеств', 'обман', 'афера', 'злоупотребление', 'злоупотребл', 'финансовая пирамида'],
    'полиция': ['полиция', 'мвд', 'задержание', 'допрос', 'сотрудник полиции', 'полицейский'],
    'прокуратура': ['прокурор', 'прокуратура', 'надзор'],
    
    # Административное право
    'штраф': ['административное', 'административн', 'взыскание', 'взыскан', 'наказание', 'наказан', 'нарушение', 'нарушен', 'санкция', 'санкци', 'протокол'],
    'права': ['право', 'правомочие', 'полномочие', 'свобода', 'свобод', 'гарантия', 'гарант', 'защита', 'защит', 'интересы'],
    'ЦОН': ['цон', 'государственные услуги', 'услуга', 'отказ в услуге', 'ошибка в данных', 'очередь'],
    'госорган': ['госорган', 'государственный орган', 'акимат', 'министерство', 'департамент'],

    # Налоговое право (ДОБАВЛЕНО/РАСШИРЕНО)
    'налог': ['налоги', 'налогообложение', 'налоговый', 'ипн', 'кпн', 'ндс', 'пеня', 'штраф', 'декларация', 'налоговая'],
    'доход': ['доходы', 'заработок', 'прибыль', 'выручка', 'заработная плата', 'оклад'],
    'вычет': ['вычеты', 'налоговый вычет', 'льгота', 'льготный', 'освобождение'],
    'ЕНПФ': ['енпф', 'пенсионные отчисления', 'пенсионные накопления'],
    'соцотчисления': ['социальные отчисления', 'соцотчисления', 'соцфонд', 'ОПВ', 'СО', 'ОСМС'],
    'медстрахование': ['обязательное медицинское страхование', 'омс', 'осмс', 'взносы на осмс'],


    # Образование и защита детей
    'учитель': ['учител', 'преподаватель', 'препода', 'педагог', 'наставник', 'воспитатель'],
    'ученик': ['ученик', 'учащийся', 'учащ', 'школьник', 'школьн', 'студент', 'воспитанник', 'воспитан', 'обучающийся'],
    'школа': ['школ', 'училище', 'лицей', 'гимназия', 'колледж', 'образовательное', 'образоват', 'учебное', 'учебн', 'заведение'],
    'ребенок': ['ребен', 'дети', 'несовершеннолетний', 'несовершеннолет', 'малолетний', 'малолет', 'дитя', 'подросток', 'подрост'],
    'насилие': ['насили', 'жестокость', 'жесток', 'принуждение', 'принужден', 'агрессия', 'агресси', 'избиение', 'избиен', 'домашнее', 'побои', 'побо', 'удар', 'бьет', 'физическое', 'психологическое'],
    'опека': ['опека', 'попечительство', 'усыновление', 'удочерение', 'усыновитель'],

    # ПДД и транспорт
    'пдд': ['пдд', 'правила дорожного движения', 'дорожные знаки', 'дорожное движение', 'движение', 'транспорт', 'дорога', 'перекресток', 'полоса', 'светофор', 'зебра', 'ДТП', 'дорожно-транспортное происшествие', 'авария'],
    'самокат': ['самокат', 'электросамокат', 'гироскутер', 'средство индивидуальной мобильности', 'сим'],
    'велосипед': ['велосипед', 'велодорожка', 'велосипедист', 'двухколесный'],
    'автобусная полоса': ['автобусная полоса', 'полоса для общественного транспорта', 'выделенка', 'выделенная полоса'],
    'камера': ['камера', 'фиксация', 'сергек'],

    # Защита прав потребителей
    'потребитель': ['потребитель', 'потребител', 'клиент', 'покупатель', 'покупател'],
    'магазин': ['магазин', 'продавец', 'торговая точка', 'онлайн-магазин', 'интернет-магазин'],
    'товар': ['товар', 'продукция', 'покупка', 'приобретение'],
    'услуга': ['услуга', 'сервис', 'оказание услуг'],
    'возврат': ['возврат', 'обмен', 'вернуть деньги', 'отказ'],
    'претензия': ['претензия', 'жалоба', 'заявление о нарушении'],

    # Цифровая грамотность
    'egov': ['egov', 'электронное правительство', 'портал госуслуг', 'ЭЦП', 'цифровая подпись'],
    'kaspi': ['kaspi', 'каспий', 'платежи', 'мобильный банк'],
    'документ': ['документ', 'форма', 'бланк', 'заявление', 'образец'],

    # Уязвимые группы
    'пенсионер': ['пенсионер', 'пожилой', 'пожилые люди'],
    'сельчанин': ['сельчанин', 'сельский житель'],
    'мигрант': ['мигрант', 'иностранец', 'иностранный гражданин'],
    'казахский': ['казахский', 'казакша', 'қазақша'],
    'русский': ['русский', 'орысша'],
    'английский': ['английский', 'english'],
}


# --- УЛУЧШЕНИЕ: Полный и актуальный словарь источников (с добавлением Налогового кодекса) ---
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

    'Налоговый кодекс': 'https://adilet.zan.kz/rus/docs/K1700000120', # ДОБАВЛЕНО
    'налогов': 'https://adilet.zan.kz/rus/docs/K1700000120', # ДОБАВЛЕНО
    'ипн': 'https://adilet.zan.kz/rus/docs/K1700000120', # ДОБАВЛЕНО
    'ндс': 'https://adilet.zan.kz/rus/docs/K1700000120', # ДОБАВЛЕНО
    'кпн': 'https://adilet.zan.kz/rus/docs/K1700000120', # ДОБАВЛЕНО

    'О жилищных отношениях': 'https://adilet.zan.kz/rus/docs/Z970000254_',
    'жилищ': 'https://adilet.zan.kz/rus/docs/Z970000254_',

    'Об образовании': 'https://adilet.zan.kz/rus/docs/Z070000319_',
    'образован': 'https://adilet.zan.kz/rus/docs/Z070000319_',

    'Правила дорожного движения': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'пдд': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'самокат': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'велосипед': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'средства индивидуальной мобильности': 'https://adilet.zan.kz/rus/docs/V2300033003',
    'о браке и семье': 'https://adilet.zan.kz/rus/docs/K1100000233', # Кодекс о браке и семье
    'кодекс о браке': 'https://adilet.zan.kz/rus/docs/K1100000233',
    'о защите прав потребителей': 'https://adilet.zan.kz/rus/docs/Z1000000300', # Закон о защите прав потребителей
    'потребитель': 'https://adilet.zan.kz/rus/docs/Z1000000300',
    'о государственных услугах': 'https://adilet.zan.kz/rus/docs/Z1300000179', # Закон о государственных услугах
    'госуслуги': 'https://adilet.zan.kz/rus/docs/Z1300000179',
}


# --- Логика поиска и обработки ---
def find_laws_by_keywords(question, min_relevance=12, max_results=8):
    results = []
    question_lower = question.lower()
    question_words = set(re.findall(r'\b\w{3,}\b', question_lower))
    if not LAW_DB:
        print("База законов (LAW_DB) не загружена.")
        return []

    priority_codes = []
    # Обновленная логика приоритизации
    if any(w in question_lower for w in ['увольн', 'работ', 'работодат', 'труд', 'зарплат', 'отпуск', 'больничн']):
        priority_codes.append('трудов')
    if any(w in question_lower for w in ['жилье', 'аренда', 'квартира', 'высел', 'жкх', 'квартплата']):
        priority_codes.append('жилищ')
    if any(w in question_lower for w in ['пенсия', 'пособие', 'декрет', 'инвалидн', 'льгот', 'енпф', 'соцотчисления', 'медстрахование']):
        priority_codes.append('социальн')
    if any(w in question_lower for w in ['развод', 'алименты', 'опека', 'брак', 'семья']):
        priority_codes.append('о браке и семье')
    if any(w in question_lower for w in ['ученик', 'учитель', 'школ', 'образован', 'насилие', 'ребенок', 'подросток']):
        priority_codes.extend(['об образовании', 'уголовн', 'административн'])
    if any(w in question_lower for w in ['штраф', 'полиция', 'прокуратура', 'цон', 'госорган', 'мвд']):
        priority_codes.extend(['об административных правонарушениях', 'уголовн', 'о государственных услугах'])
    if any(w in question_lower for w in ['пдд', 'самокат', 'велосипед', 'дтп']):
        priority_codes.append('правила дорожного движения')
    if any(w in question_lower for w in ['потребитель', 'магазин', 'товар', 'услуга', 'возврат', 'претензия']):
        priority_codes.append('о защите прав потребителей')
    if any(w in question_lower for w in ['документ', 'форма', 'бланк', 'egov', 'kaspi']):
        priority_codes.append('гражданск')
    if any(w in question_lower for w in ['пенсионер', 'сельчанин', 'мигрант', 'иностранец']):
        priority_codes.append('социальн')
    if any(w in question_lower for w in ['налог', 'налогообложение', 'ипн', 'ндс', 'кпн', 'доход', 'вычет', 'декларация']): # Налоговые запросы
        priority_codes.append('налогов')


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

        # УЛУЧШЕНИЕ: Более умная приоритизация кодексов
        for code_key in priority_codes:
            if code_key in title_lower or any(s in title_lower for s in LEGAL_SYNONYMS.get(code_key, [])):
                relevance += 15

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
        # Убедитесь, что папка 'laws' существует и доступна для чтения.
        # В средах типа Railway или Vercel, если файлы включены в сборку,
        # они должны быть доступны относительно корневой директории приложения.
        laws_dir = os.path.join(os.path.dirname(__file__), "laws")
        json_path = os.path.join(laws_dir, "kazakh_laws.json")

        if not os.path.exists(laws_dir):
            print(f"Папка '{laws_dir}' не найдена. Убедитесь, что файл 'kazakh_laws.json' находится в папке 'laws' в корне проекта.")
            return

        with open(json_path, "r", encoding="utf-8") as f: raw_db = json.load(f)
        LAW_DB = preprocess_laws_into_articles(raw_db); print(f"✅ База данных загружена! Статей: {len(LAW_DB)}")
    except FileNotFoundError:
        print(f"❌ Файл '{json_path}' не найден. Убедитесь, что он существует.")
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

load_law_db() # Загружаем базу законов при старте приложения

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
        'о браке и семье': 'Кодекс о браке и семье РК',
        'здоровь': 'Кодекс о здоровье РК',
        'экологич': 'ЭК РК',
        'налогов': 'НК РК', # ОБНОВЛЕНО
        'бюджетн': 'БК РК',
        'таможен': 'ТК ЕАЭС',
        'земельн': 'ЗК РК',
        'лесн': 'ЛК РК',
        'водн': 'ВК РК',
        'недра': 'Кодекс о недрах РК',
        'пдд': 'ПДД РК',
        'самокат': 'ПДД РК',
        'велосипед': 'ПДД РК',
        'о защите прав потребителей': 'Закон о защите прав потребителей РК',
        'о государственных услугах': 'Закон о государственных услугах РК',
        'об образовании': 'Закон об образовании РК',
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
    if filepath.endswith((".docx", ".doc")):
        try:
            import docx
            doc = docx.Document(filepath)
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            print(f"Ошибка при чтении DOCX: {e}")
            return ""
    elif filepath.endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(filepath)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            print(f"Ошибка при чтении PDF: {e}")
            return ""
    elif filepath.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")):
        print("Обработка изображений требует отдельной Vision API логики.")
        return ""
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
            elif 'раздел' in pattern: found_parts.append(f"Раздел {match}")
            elif 'подраздел' in pattern: found_parts.append(f"Подраздел {match}")
            elif 'параграф' in pattern: found_parts.append(f"Параграф {match}")
            elif 'пункт' in pattern or 'п.' in pattern: found_parts.append(f"Пункт {match}")
    return ", ".join(found_parts) if found_parts else None

def convert_full_markdown_to_html(text):
    text = text.strip()
    paragraphs = re.split(r'\n\s*\n', text)
    html_output = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if re.match(r'\*\*.+?:?\*\*', para) or re.match(r'#+\s*.+', para):
            para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para)
            para = re.sub(r'#+\s*(.+)', r'\1', para)
            html_output.append(f"<h3>{para}</h3>")
        elif re.match(r'^[•*-] ', para) or re.match(r'^\d+\. ', para):
            lines = para.split('\n')
            list_tag_start = "<ul>" if re.match(r'^[•*-] ', para) else "<ol>"
            list_tag_end = "</ul>" if re.match(r'^[•*-] ', para) else "</ol>"
            list_items = []
            for line in lines:
                line = line.strip()
                if not line: continue
                clean_line = re.sub(r'^[•*-]\s*', '', line)
                clean_line = re.sub(r'^\d+\.\s*', '', clean_line)
                clean_line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', clean_line)
                list_items.append(f"<li>{clean_line}</li>")
            html_output.append(list_tag_start + "".join(list_items) + list_tag_end)
        elif re.match(r'^> ', para):
            quote_content = re.sub(r'^> ', '', para)
            quote_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', quote_content)
            html_output.append(f"<blockquote>{quote_content}</blockquote>")
        else:
            para = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', para)
            html_output.append(f"<p>{para}</p>")

    return "".join(html_output)


# --- ИСПРАВЛЕНИЕ: Финальная, самая надежная инструкция для ИИ ---
PROMPT_TEMPLATE = """
Ты — высококвалифицированный юрист-консультант, специализирующийся **ИСКЛЮЧИТЕЛЬНО на законодательстве Республики Казахстан**. Твоя главная задача — предоставлять точные, понятные и актуальные юридические консультации гражданам Казахстана.

**КРАЙНЕ ВАЖНО: ОТВЕЧАЙ ТОЛЬКО НА ОСНОВЕ ЗАКОНОВ РЕСПУБЛИКИ КАЗАХСТАН. Категорически запрещено упоминать, ссылаться или сравнивать с законодательством любых других стран (например, России, РФ, НДФЛ, СНГ, ЕС, США и т.п.). Всегда помни, что твоя юрисдикция — только Казахстан.**

**1. ПРИОРИТЕТ: АКТИВНЫЙ ЗАПРОС ДОПОЛНИТЕЛЬНОЙ ИНФОРМАЦИИ.**
Если для формирования исчерпывающего и точного ответа на текущий вопрос пользователя требуется любая личная или уточняющая информация (например, возраст, доход, семейное положение, стаж работы, конкретные даты, детали документа, местоположение), **ТЫ ДОЛЖЕН НЕЗАМЕДЛИТЕЛЬНО И АКТИВНО ЗАДАТЬ ЭТИ УТОЧНЯЮЩИЕ ВОПРОСЫ**.
**Всегда объясни, почему тебе нужна эта информация и как она поможет в решении проблемы пользователя.**
**Ни в коем случае НЕ ДАВАЙ ПОЛНОГО ОТВЕТА или общих рекомендаций, пока не получишь все необходимые данные.**
**Пример запроса дополнительной информации:**
"Для того чтобы я мог дать точный ответ по вашей ситуации с налогами, мне нужно знать следующее:
* Ваш ежемесячный доход (размер заработной платы);
* Есть ли у вас иждивенцы (например, дети, их возраст);
* Применяются ли к вам какие-либо налоговые вычеты (например, по ипотеке, образованию, лечению).
Пожалуйста, предоставьте эту информацию, и я смогу рассчитать приблизительную сумму налога и дать конкретные рекомендации, а также составить план действий по законодательству Казахстана."

Не запрашивай информацию, которая не требуется для текущего вопроса.

**2. ОТВЕТ НА ОСНОВЕ ЗАКОНОВ КАЗАХСТАНА (после получения всей необходимой информации):**

* Объясни, **что говорит закон Казахстана** по этой ситуации, ссылаясь на конкретные статьи кодексов или законов РК, которые были загружены в твою базу знаний.
* Укажи, **нарушены ли права пользователя** в соответствии с законодательством РК, и какие конкретно.
* Приведи **конкретные, детализированные пошаговые инструкции**, которые человек может предпринять для решения своей проблемы. **Не просто "обратитесь", а "ЧТО делать при обращении"**: какие документы подготовить (с перечислением), куда именно обратиться (адреса, телефоны, если известны из контекста), какие сроки и процедуры.
* Если уместно, **предложи шаблон заявления** или его ключевые пункты (например, в полицию, работодателю, в ЦОН, акимат, претензию продавцу), чтобы пользователь мог сразу использовать его.
* Пиши **исключительно простыми словами**, избегай юридического жаргона. Ответ должен быть понятен даже школьнику.
* Если законов по теме нет или ситуация явно вне юрисдикции РК (что крайне маловероятно, учитывая твою специализацию, но если такое произошло — это исключение), так и напиши, но предложи общие рекомендации, если это возможно, БЕЗ ССЫЛОК НА ЗАКОНЫ ДРУГИХ СТРАН.

**Форматируй ответ красиво и структурировано:**
* Используй **жирный текст** для выделения ключевых моментов.
* Используй заголовки (например, **Что говорит закон?**, **Что делать?**, **Ваши дальнейшие действия**, **Шаблон документа**).
* Используй списки (маркированные или нумерованные) для пошаговых инструкций и перечислений.
* Не придумывай фактов — отвечай честно, даже если нет ответа.

**Важно: Ты являешься полноценным юристом-консультантом. Никогда не добавляй в конце фразы вроде "это лишь шаблон", "не является юридической консультацией", "обратитесь к специалисту", "я ИИ" или "я не человек". Представь, что ты реальный юрист, которому клиенты могут доверять и верить, и который способен решить проблему на месте, предоставляя исчерпывающие инструкции.**
"""


# УЛУЧШЕНИЕ: Расширенный промпт для анализа файла
FILE_ANALYSIS_PROMPT = """
Ты — опытный юрист из Казахстана. Тебе предоставлен следующий документ для анализа.

---
**Содержимое документа:**
{text}
---

**Дополнительный вопрос или комментарий от клиента (если есть):**
{question}

**Твоя задача:**
1.  **Проанализируй документ.** Определи его тип (договор, заявление, справка и т.д.) и его основные положения.
2.  **Выяви ключевые пункты**, которые наиболее важны для клиента в контексте его запроса (если он есть).
3.  **Определи потенциальные риски и проблемы** для клиента, связанные с этим документом. На что стоит обратить особое внимание?
4.  **Скажи, можно ли доверять документу** — нет ли подозрительных, несправедливых или потенциально опасных условий, не соответствующих законодательству Казахстана.
5.  **Дай конкретные рекомендации** по дальнейшим действиям клиента относительно этого документа.
6.  **Ответь простыми словами**, ясно и по делу. Избегай юридического жаргона.
7.  Если документ не относится к юридической сфере или не содержит достаточной информации для анализа, объясни это.

**Форматируй красиво:**
* Используй **жирный текст** для выделения ключевых моментов.
* Используй заголовки (например, **Анализ документа**, **Ключевые пункты**, **Риски и рекомендации**).
* Используй списки (маркированные или нумерованные) для перечислений.
* Не используй фразы типа «я ИИ» или «я как модель».
"""


# --- Финальная архитектура с двумя маршрутами ---

@app.route("/ask", methods=["POST"])
def ask_streaming():
    data = request.json
    question = data.get("question", "").strip()
    session_id = data.get("session_id", "default")
    if not question:
        return jsonify({"error": "Пустой вопрос", "session_id": session_id}), 400

    def generate_text():
        try:
            history = load_conversation(session_id)
            temp_history_for_prompt = history + [{"role": "user", "parts": [question]}]

            # При отправке истории в Gemini, она должна быть в формате, который понимает модель.
            # Если вы хотите передать найденные законы как контекст, это нужно делать здесь.
            # На данный момент, PROMPT_TEMPLATE уже достаточно включает роль юриста и юрисдикцию.
            # Добавление законов в контекст, если они найдены, может выглядеть так:
            laws_found = find_laws_by_keywords(question)
            laws_context_for_ai = ""
            if laws_found:
                laws_context_for_ai = "\n\n**Релевантная информация из законодательства РК:**\n"
                for i, law in enumerate(laws_found[:5]): # Отправляем до 5 самых релевантных законов
                    laws_context_for_ai += f"### {law.get('title', 'Статья')}\n{law.get('text', '')[:1500]}...\n\n" # Обрезаем текст для экономии токенов

            # Формируем полный запрос для модели, включая контекст законов
            # Добавляем laws_context_for_ai в начало или конец PROMPT_TEMPLATE или в отдельные части истории.
            # Для простоты, пока будем добавлять к вопросу, если законы найдены.
            
            # Вариант 1: Добавить законы в историю как системное сообщение (наиболее правильный)
            model_history_with_laws = []
            if laws_context_for_ai:
                model_history_with_laws.append({"role": "system", "parts": [PROMPT_TEMPLATE + laws_context_for_ai]})
            else:
                model_history_with_laws.append({"role": "system", "parts": [PROMPT_TEMPLATE]})

            # Добавляем предыдущую историю чата
            model_history_with_laws.extend(history)
            # Добавляем текущий вопрос пользователя
            model_history_with_laws.append({"role": "user", "parts": [question]})


            stream = model.generate_content(
                model_history_with_laws, # Передаем всю историю с контекстом
                stream=True
            )
            full_reply = ""
            for chunk in stream:
                if chunk.text:
                    full_reply += chunk.text
                    yield chunk.text
            
            save_message(session_id, "user", question)
            save_message(session_id, "model", full_reply)
        except Exception as e:
            print(f"❌ Ошибка в стриме /ask: {e}")
            yield "Произошла ошибка при генерации ответа ИИ. Пожалуйста, попробуйте еще раз."
    return Response(stream_with_context(generate_text()), mimetype='text/plain; charset=utf-8', headers={"X-Session-Id": session_id})

@app.route("/process-full-text", methods=["POST"])
def process_full_text():
    data = request.json
    full_ai_text = data.get("full_ai_text", "")
    question = data.get("question", "").strip()
    session_id = data.get("session_id", "default")

    if not full_ai_text:
        return jsonify({"error": "Отсутствует текст ИИ", "session_id": session_id}), 400

    try:
        formatted_ai_html = convert_full_markdown_to_html(full_ai_text)
        laws_found = find_laws_by_keywords(question)
        law_section_html = format_laws(laws_found)
        final_html = formatted_ai_html + law_section_html
        return jsonify({"html": final_html, "session_id": session_id})
    except Exception as e:
        print(f"❌ Ошибка в /process-full-text: {e}")
        return jsonify({"error": "Ошибка при финальной обработке", "session_id": session_id}), 500

# --- Главная страница и статика ---
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

# --- /analyze-file: анализ файла + вопрос пользователя ---
@app.route("/analyze-file", methods=["POST"])
def analyze_file():
    try:
        file = request.files.get("file")
        question = request.form.get("question", "").strip()
        session_id = request.form.get("session_id", "default")
        if not file:
            return jsonify({"error": "Файл не получен", "session_id": session_id}), 400

        # Vercel и Railway имеют временные файловые системы, /tmp подходит для временных файлов
        filepath = os.path.join("/tmp", file.filename) 
        file.save(filepath)

        if file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")):
            import PIL.Image
            img = PIL.Image.open(filepath)
            
            vision_prompt_parts = [
                FILE_ANALYSIS_PROMPT.format(text="[Изображение документа]", question=question),
                img
            ]
            response = model.generate_content(vision_prompt_parts) # Использовать основную модель, если vision model не настроена отдельно

        else: # Для текстовых документов (PDF, DOCX)
            text = extract_text_from_file(filepath)
            if not text:
                os.remove(filepath)
                return jsonify({"error": "Не удалось извлечь текст из файла или файл пустой.", "session_id": session_id}), 400
            
            prompt_for_text_file = FILE_ANALYSIS_PROMPT.format(text=text[:8000], question=question)
            response = model.generate_content(prompt_for_text_file)

        os.remove(filepath) # Удаляем временный файл после обработки

        if not hasattr(response, "text") or not response.text:
            return jsonify({"error": "AI юрист не смог проанализировать файл или файл пустой.", "session_id": session_id}), 400
        
        save_message(session_id, "user", f"Анализ файла: {file.filename}. Вопрос: {question}")
        save_message(session_id, "model", response.text)

        return jsonify({"analysis": response.text, "session_id": session_id})
    except Exception as e:
        print(f"❌ analyze_file error: {e}")
        session_id = request.form.get("session_id", "default")
        return jsonify({"error": f"Server error: {str(e)}", "session_id": session_id}), 500

# --- Маршрут для загрузки истории сообщений ---
@app.route("/get-history", methods=["GET"])
def get_history():
    session_id = request.args.get("session_id", "default")
    history = load_conversation(session_id)
    formatted_history = []
    for entry in history:
        content = entry['parts'][0] if isinstance(entry['parts'], list) and entry['parts'] else ''
        formatted_history.append({"role": entry['role'], "content": content})
    return jsonify({"history": formatted_history})

# --- Маршрут для получения сводки всех сессий для отображения в сайдбаре ---
@app.route("/get-all-sessions-summary", methods=["GET"])
def get_all_sessions_summary():
    try:
        # Используем новую функцию для MongoDB
        sessions_summary = get_all_sessions_summary_mongo()
        return jsonify({"sessions": sessions_summary})
    except Exception as e:
        print(f"❌ Ошибка в /get-all-sessions-summary: {e}")
        return jsonify({"error": f"Ошибка сервера при получении сводки сессий: {str(e)}"}), 500


# --- Маршрут для удаления истории сообщений ---
@app.route("/clear-history", methods=["POST"])
def clear_history_route():
    session_id = request.json.get("session_id", "default")
    delete_conversation(session_id)
    return jsonify({"message": "История очищена", "session_id": session_id})


if __name__ == '__main__':
    load_law_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
