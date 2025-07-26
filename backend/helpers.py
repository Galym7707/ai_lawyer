import re
from typing import List, Set, Dict

def expand_keywords(keywords: Set[str], synonym_dict: Dict[str, List[str]]) -> Set[str]:
    """Расширяет множество ключевых слов за счёт синонимов.

    Каждый найденный ключ выводится в результирующее множество вместе с
    синонимами из ``synonym_dict``. Это позволяет находить статьи в базе
    законов по наиболее релевантным терминам.
    """
    expanded = set(keywords)
    # Итерируем по копии, чтобы можно было изменять ``expanded`` во время цикла
    for kw in list(keywords):
        for group in synonym_dict.values():
            if kw in group:
                expanded.update(group)
    return expanded

def build_snippet(text: str, keywords: Set[str], window: int = 120, max_snips: int = 3) -> str:
    """Формирует сниппет из переданного текста.

    Ищет в тексте ключевые слова и вырезает фрагменты длиной ``2*window``
    символов вокруг каждого найденного слова. Если ключевые слова не
    найдены или текст короткий, возвращает начало текста. Возвращает
    объединённую строку не длиннее ``max_snips`` фрагментов, отделённых
    многоточием.
    """
    if not text:
        return ""

    low = text.lower()
    snippets: List[str] = []
    # Сначала пытаемся найти сниппеты по ключевым словам
    for kw in keywords:
        # Ищем только целые слова
        pattern = r'\b' + re.escape(kw) + r'\b'
        for m in re.finditer(pattern, low):
            start = max(0, m.start() - window)
            end = min(len(text), m.end() + window)
            snippet = text[start:end].strip()
            # Добавляем многоточие, если текст обрезан
            if start > 0 and not text[start - 1].isspace():
                snippet = "..." + snippet
            if end < len(text) and not text[end].isspace():
                snippet = snippet + "..."
            snippets.append(snippet)

    # Если ничего не нашли или текст слишком короткий — возвращаем начало
    if not snippets or len(text) < window * 2:
        return text[:window * 2].strip()

    # Убираем дубликаты, упорядочиваем по длине (короткие фрагменты считаем более релевантными)
    uniq = list(dict.fromkeys(snippets))
    uniq.sort(key=len)
    # Объединяем до ``max_snips`` уникальных сниппетов
    return " … ".join(uniq[:max_snips])
