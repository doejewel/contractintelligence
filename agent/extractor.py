import pypdf
import re
from pathlib import Path


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract and clean text from a PDF file."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text_parts = []
    with open(path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")

    full_text = "\n\n".join(text_parts)
    # Clean excessive whitespace while preserving structure
    full_text = re.sub(r'\n{4,}', '\n\n\n', full_text)
    full_text = re.sub(r' {3,}', '  ', full_text)
    return full_text.strip()


def extract_text_from_string(content: str) -> str:
    """Pass-through for raw text contracts (for testing)."""
    return content.strip()


def truncate_for_context(text: str, max_chars: int = 12000) -> str:
    """Truncate contract text to fit within LLM context window."""
    if len(text) <= max_chars:
        return text
    # Keep beginning and end — most important clauses live there
    half = max_chars // 2
    return (
        text[:half]
        + f"\n\n... [TRUNCATED: {len(text) - max_chars} characters omitted] ...\n\n"
        + text[-half:]
    )