import sqlite3

import chromadb
import pandas as pd
from chromadb.utils import embedding_functions

from src.config import (
    FAQ_CSV_PATH,
    PRODUCT_CSV_PATH,
    DB_PATH,
    CHROMA_PATH,
    FAQ_COLLECTION_NAME,
    EMBEDDING_MODEL,
)


# --------------------------------------------------
# SQLite product database
# --------------------------------------------------

def product_database_ready() -> bool:

    if not DB_PATH.exists():
        return False

    try:
        with sqlite3.connect(DB_PATH) as conn:
            result = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                AND name='product'
                """
            ).fetchone()

        return result is not None

    except sqlite3.Error:
        return False


def create_product_database():

    print("Creating product database...")

    df = pd.read_csv(PRODUCT_CSV_PATH)

    required_columns = {
        "product_link",
        "title",
        "brand",
        "price",
        "discount",
        "avg_rating",
        "total_ratings",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing product columns: {missing_columns}"
        )

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sqlite3.connect(DB_PATH) as conn:

        df.to_sql(
            "product",
            conn,
            if_exists="replace",
            index=False,
        )

        # Useful indexes for filtering/ranking
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_product_brand
            ON product(brand)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_product_price
            ON product(price)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_product_rating
            ON product(avg_rating)
            """
        )

    print(
        f"Product database ready: {len(df)} products"
    )


# --------------------------------------------------
# FAQ Chroma vector store
# --------------------------------------------------

def create_faq_vectorstore():

    print("Checking FAQ vector store...")

    faq_df = pd.read_csv(
        FAQ_CSV_PATH
    )

    required_columns = {
        "question",
        "answer",
    }

    missing_columns = (
        required_columns
        - set(faq_df.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Missing FAQ columns: {missing_columns}"
        )

    CHROMA_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    embedding_function = (
        embedding_functions
        .SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
    )

    chroma_client = (
        chromadb.PersistentClient(
            path=str(CHROMA_PATH)
        )
    )

    collection = (
        chroma_client
        .get_or_create_collection(
            name=FAQ_COLLECTION_NAME,
            embedding_function=embedding_function,
        )
    )

    # Only ingest on a fresh environment
    if collection.count() == 0:

        documents = (
            faq_df["question"]
            .astype(str)
            .tolist()
        )

        metadatas = [
            {
                "answer": str(answer)
            }
            for answer
            in faq_df["answer"]
        ]

        ids = [
            f"faq_{i}"
            for i
            in range(len(faq_df))
        ]

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        print(
            f"FAQ vector store ready: "
            f"{collection.count()} FAQs"
        )

    else:
        print(
            f"FAQ vector store already ready: "
            f"{collection.count()} FAQs"
        )


# --------------------------------------------------
# Application bootstrap
# --------------------------------------------------

def ensure_data_ready():

    if not product_database_ready():
        create_product_database()

    create_faq_vectorstore()


# --------------------------------------------------
# Manual test
# --------------------------------------------------

if __name__ == "__main__":

    ensure_data_ready()

    print("\nAll application data is ready.")