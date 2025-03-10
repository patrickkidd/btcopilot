import re
from pathlib import Path
import logging

_log = logging.getLogger(__name__)


nlp = None


def split_markdown_semantically(
    markdown_text=None,
    file_path=None,
    min_chunk_size=200,
    max_chunk_size=2000,
    spacy_model="en_core_web_sm",
):
    """
    Split markdown text or a markdown file into semantic chunks using spaCy and headings.

    Args:
        markdown_text (str, optional): Markdown content to split. Use this or file_path.
        file_path (str or Path, optional): Path to markdown file. Use this or markdown_text.
        min_chunk_size (int): Minimum length (in characters) for a chunk.
        max_chunk_size (int): Maximum length (in characters) before splitting.
        spacy_model (str): spaCy model for sentence splitting.

    Returns:
        list[str]: List of semantically meaningful string chunks.

    Raises:
        ValueError: If neither markdown_text nor file_path is provided.
        FileNotFoundError: If file_path doesn’t exist.
    """
    global nlp

    import spacy

    # Load spaCy model
    if not nlp:
        _log.info(f"Loading spaCy model '{spacy_model}'")
        try:
            nlp = spacy.load(spacy_model)
        except OSError:
            raise OSError(
                f"Can't find spaCy model '{spacy_model}'. Run 'python -m spacy download {spacy_model}' to install it."
            )
        _log.info(f"Loaded spaCy model '{spacy_model}'")

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

    # Process with spaCy
    doc = nlp(markdown_text)

    for line in markdown_text.splitlines():
        line = line.strip()
        heading_match = re.match(heading_pattern, line)
        if heading_match:
            # Save current chunk if it’s big enough
            if current_chunk and len(current_chunk) >= min_chunk_size:
                chunks.append(current_chunk.strip())
            # Start new chunk with heading
            current_chunk = line + "\n"
            buffer = ""
        else:
            buffer += line + "\n"
            # Split buffer when it exceeds max size or ends
            if len(current_chunk) + len(buffer) > max_chunk_size or not buffer.strip():
                if buffer.strip():
                    buffer_doc = nlp(buffer)
                    for sent in buffer_doc.sents:
                        if (
                            len(current_chunk) + len(sent.text) > max_chunk_size
                            and current_chunk
                        ):
                            chunks.append(current_chunk.strip())
                            current_chunk = sent.text + "\n"
                        else:
                            current_chunk += sent.text + "\n"
                buffer = ""

    # Process remaining buffer
    if buffer.strip():
        buffer_doc = nlp(buffer)
        for sent in buffer_doc.sents:
            if len(current_chunk) + len(sent.text) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sent.text + "\n"
            else:
                current_chunk += sent.text + "\n"

    # Append final chunk if it meets size
    if current_chunk.strip() and len(current_chunk) >= min_chunk_size:
        chunks.append(current_chunk.strip())

    return chunks
