import re
from typing import List, Set

def expand_keywords(keywords: Set[str], synonym_dict: dict) -> Set[str]:
    """Добавляет синонимы из LEGAL_SYNONYMS к найденным ключевым словам."""
    expanded = set(keywords)
    for kw in list(keywords): # Итерируем по копии, чтобы можно было изменять 'expanded'
        for group in synonym_dict.values():
            if kw in group:
                expanded.update(group)
    return expanded

def build_snippet(text: str, keywords: Set[str], window: int = 120, max_snips: int = 3) -> str:
    """
    Возвращает объединённую строку из max_snips фрагментов (… keyword …),
    каждый длиной ≈ 2*window символов.
    """
    if not text:
        return ""

    low = text.lower()
    snippets: List[str] = []
    
    # Сначала пытаемся найти сниппеты по ключевым словам
    for kw in keywords:
        # Используем r'\b' для поиска целых слов
        for m in re.finditer(r'\b' + re.escape(kw) + r'\b', low):
            start = max(0, m.start() - window)
            end   = min(len(text), m.end() + window)
            snippet = text[start:end].strip()
            # Добавляем "..." если текст обрезан
            if start > 0 and not text[start-1].isspace():
                snippet = "..." + snippet
            if end < len(text) and not text[end].isspace():
                snippet = snippet + "..."
            
            snippets.append(snippet)
    
    # Если сниппетов не нашлось или текст очень короткий, просто берем начало
    if not snippets or len(text) < window * 2:
        return text[:window * 2].strip()

    # Убираем дубликаты, сортируем по длине (короче — релевантнее)
    # Используем dict.fromkeys для сохранения порядка вставки и удаления дубликатов
    uniq = list(dict.fromkeys(snippets))
    uniq.sort(key=len)
    
    # Объединяем до max_snips уникальных сниппетов
    return " … ".join(uniq[:max_snips])
