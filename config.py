# shared config - all services read from here

import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# service ports
EMBEDDING_SERVICE_PORT = int(os.getenv("EMBEDDING_SERVICE_PORT", 8001))
RAG_SERVICE_PORT = int(os.getenv("RAG_SERVICE_PORT", 8002))
VISION_SERVICE_PORT = int(os.getenv("VISION_SERVICE_PORT", 8003))

# service urls (override these in docker)
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", f"http://localhost:{EMBEDDING_SERVICE_PORT}")
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", f"http://localhost:{RAG_SERVICE_PORT}")
VISION_SERVICE_URL = os.getenv("VISION_SERVICE_URL", f"http://localhost:{VISION_SERVICE_PORT}")

DB_PATH = os.getenv("DB_PATH", "data/embeddings.db")

# rag settings
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
TOP_K = int(os.getenv("TOP_K", 3))

KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "knowledge_base")
