import re
from html import unescape

import bleach
from bleach.css_sanitizer import CSSSanitizer

# Tags/atributos aceitos para conteúdo rico gerado pelo editor TipTap.
RICH_TEXT_TAGS = [
    'p',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'strong',
    'b',
    'em',
    'i',
    'u',
    's',
    'strike',
    'code',
    'pre',
    'ul',
    'ol',
    'li',
    'blockquote',
    'br',
    'hr',
    'a',
    'span',
]

RICH_TEXT_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'p': ['style'],
    'h1': ['style'],
    'h2': ['style'],
    'h3': ['style'],
    'h4': ['style'],
    'h5': ['style'],
    'h6': ['style'],
    'li': ['style'],
    'blockquote': ['style'],
    'span': ['style'],
}

RICH_TEXT_CSS = CSSSanitizer(allowed_css_properties=['text-align'])


def sanitize_rich_text(value: str) -> str:
    """Sanitiza conteúdo HTML rico, mantendo tags do editor TipTap."""
    if not isinstance(value, str):
        return value
    return bleach.clean(
        value,
        tags=RICH_TEXT_TAGS,
        attributes=RICH_TEXT_ATTRIBUTES,
        css_sanitizer=RICH_TEXT_CSS,
        strip=True,
    ).strip()


def plain_text(value: str) -> str:
    """Extrai o texto puro de um HTML rico, ignorando marcação de formatação.

    Remove tags, decodifica entidades e normaliza espaços em branco, permitindo
    comparar o conteúdo semântico de dois HTMLs independentemente da
    formatação.
    """
    if not isinstance(value, str):
        return ''
    text = re.sub(r'<[^>]*>', '', value)
    text = unescape(text)
    return re.sub(r'\s+', ' ', text).strip()
