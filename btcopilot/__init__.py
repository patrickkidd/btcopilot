EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# LLM_MODEL = "mistral"
LLM_MODEL = "deepseek-r1:14b"

from .engine import Engine, Response

from .app import create_app
