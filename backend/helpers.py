# -*- coding: utf-8 -*-
import re
from typing import List, Set, Dict

def expand_keywords(keywords: Set[str], synonym_dict: Dict[str, List[str]]) -> Set[str]:
    """
    Расширяет множество ключевых слов за счёт синонимов.
    Включает и ключ, и его синонимы; также если исходное слово совпадает с
    одним из синонимов — берётся вся группа.

    Ожидается, что входные keywords уже в lower().
    """
    expanded: Set[str] = set()
    for kw in keywords:
        found = False
        for key, syns in synonym_dict.items():
            group = set([key]) | set(syns)
            if kw in group:
                expanded |= group
                found = True
        if not found:
            expanded.add(kw)
    return expanded

def build_snippet(text: str, keywords: Set[str], window: int = 120, max_snips: int = 3) -> str:
    """
    Формирует сниппет из переданного текста.
    Ищет ключевые слова (как целые слова) и вырезает фрагменты длиной 2*window
    вокруг каждого найденного. Если ничего не найдено — возвращает начало текста.
    """
    if not text:
        return ""

    low = text.lower()
    snippets: List[str] = []
    for kw in keywords:
        if not kw:
            continue
        pattern = r"\b" + re.escape(kw) + r"\b"
        for m in re.finditer(pattern, low):
            start = max(0, m.start() - window)
            end = min(len(text), m.end() + window)
            snippet = text[start:end].strip()
            if start > 0 and (start < len(text)) and not text[start - 1].isspace():
                snippet = "..." + snippet
            if end < len(text) and not text[end:end+1].isspace():
                snippet = snippet + "..."
            snippets.append(snippet)

    if not snippets or len(text) < window * 2:
        return text[: window * 2].strip()

    uniq = list(dict.fromkeys(snippets))  # de-dupe, сохраняем порядок
    uniq.sort(key=len)
    return " … ".join(uniq[:max_snips])
