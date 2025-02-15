EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# LLM_MODEL = "mistral"
# LLM_MODEL = "mistral:7b-text-q8_0"
LLM_MODEL = "tinyllama"
# LLM_MODEL = "deepseek-r1:14b"
# LLM_MODEL = "deepseek-r1:1.5b"

from .engine import Engine, Response

from .app import create_app
