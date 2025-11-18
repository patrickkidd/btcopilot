import re
from pathlib import Path
import logging

_log = logging.getLogger(__name__)


_nltk_initialized = False


def _ensure_nltk():
    global _nltk_initialized
    if not _nltk_initialized:
        import nltk
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            _log.info("Downloading NLTK punkt tokenizer")
            nltk.download('punkt', quiet=True)
            nltk.download('punkt_tab', quiet=True)
        _nltk_initialized = True


def split_markdown_semantically(
    markdown_text=None,
    file_path=None,
    min_chunk_size=200,
    max_chunk_size=2000,
    spacy_model="en_core_web_sm",
):
    """
    Split markdown text or a markdown file into semantic chunks using NLTK and headings.

    Args:
        markdown_text (str, optional): Markdown content to split. Use this or file_path.
        file_path (str or Path, optional): Path to markdown file. Use this or markdown_text.
        min_chunk_size (int): Minimum length (in characters) for a chunk.
        max_chunk_size (int): Maximum length (in characters) before splitting.
        spacy_model (str): Deprecated, kept for compatibility.

    Returns:
        list[str]: List of semantically meaningful string chunks.

    Raises:
        ValueError: If neither markdown_text nor file_path is provided.
        FileNotFoundError: If file_path doesn't exist.
    """
    _ensure_nltk()
    import nltk

    # Handle input source
    if markdown_text is None and file_path is None:
        raise ValueError("Must provide either markdown_text or file_path")
    if file_path:
        file_path = Path(file_path)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()

    # Normalize newlines
    markdown_text = markdown_text.replace("\r\n", "\n").replace("\r", "\n")

    # Define regex for headings
    heading_pattern = r"^(#+)\s+(.+)$"

    chunks = []
    current_chunk = ""
    buffer = ""

    def split_sentences(text):
        return nltk.sent_tokenize(text)

    for line in markdown_text.splitlines():
        line = line.strip()
        heading_match = re.match(heading_pattern, line)
        if heading_match:
            if current_chunk and len(current_chunk) >= min_chunk_size:
                chunks.append(current_chunk.strip())
            current_chunk = line + "\n"
            buffer = ""
        else:
            buffer += line + "\n"
            if len(current_chunk) + len(buffer) > max_chunk_size or not buffer.strip():
                if buffer.strip():
                    for sent in split_sentences(buffer):
                        if (
                            len(current_chunk) + len(sent) > max_chunk_size
                            and current_chunk
                        ):
                            chunks.append(current_chunk.strip())
                            current_chunk = sent + "\n"
                        else:
                            current_chunk += sent + "\n"
                buffer = ""

    if buffer.strip():
        for sent in split_sentences(buffer):
            if len(current_chunk) + len(sent) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sent + "\n"
            else:
                current_chunk += sent + "\n"

    if current_chunk.strip() and len(current_chunk) >= min_chunk_size:
        chunks.append(current_chunk.strip())

    return chunks
