import os
from pathlib import Path
from dotenv import load_dotenv

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")

# Embedding model
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Data paths
DATA_DIR = BASE_DIR / "data"

FAQ_CSV_PATH = DATA_DIR / "raw" / "faq_data.csv"
PRODUCT_CSV_PATH = DATA_DIR / "raw" / "ecommerce_data_final.csv"

DB_PATH = DATA_DIR / "ecommerce.db"
CHROMA_PATH = DATA_DIR / "chroma_db"

# Chroma collection
FAQ_COLLECTION_NAME = "faqs"

# Validation
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing from .env")

if not GROQ_MODEL:
    raise ValueError("GROQ_MODEL is missing from .env")

