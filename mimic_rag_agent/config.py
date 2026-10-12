import os
from dotenv import load_dotenv
load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "./data/mimic_demo")
STORAGE_DIR = os.getenv("STORAGE_DIR", "./storage")
SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(STORAGE_DIR, "db_plus.sqlite"))
FAISS_DIR = os.getenv("FAISS_DIR", os.path.join(STORAGE_DIR, "faiss_index"))
BM25_PATH = os.getenv("BM25_PATH", os.path.join(STORAGE_DIR, "bm25.pkl"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# Weights
ALPHA_BM25 = float(os.getenv("ALPHA_BM25", "0.35"))
BETA_VECTOR = float(os.getenv("BETA_VECTOR", "0.55"))
GAMMA_META = float(os.getenv("GAMMA_META", "0.10"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
