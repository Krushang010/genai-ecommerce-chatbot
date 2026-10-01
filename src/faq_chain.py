from groq import Groq
import chromadb
from chromadb.utils import embedding_functions

from src.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    EMBEDDING_MODEL,
    CHROMA_PATH,
    FAQ_COLLECTION_NAME,
)


# -----------------------------
# Initialize shared components
# -----------------------------

groq_client = Groq(api_key=GROQ_API_KEY)

embedding_function = (
    embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
)

chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_PATH)
)

faq_collection = chroma_client.get_collection(
    name=FAQ_COLLECTION_NAME,
    embedding_function=embedding_function
)


# -----------------------------
# Retrieval
# -----------------------------

def get_relevant_faqs(query: str, top_k: int = 3):
    return faq_collection.query(
        query_texts=[query],
        n_results=top_k
    )


# -----------------------------
# Context construction
# -----------------------------

def build_faq_context(results) -> str:
    context_parts = []

    for question, metadata in zip(
        results["documents"][0],
        results["metadatas"][0]
    ):
        context_parts.append(
            f"FAQ Question: {question}\n"
            f"FAQ Answer: {metadata['answer']}"
        )

    return "\n\n".join(context_parts)


# -----------------------------
# LLM generation
# -----------------------------

def generate_faq_answer(query: str, context: str) -> str:
    prompt = f"""
You are a helpful e-commerce customer support assistant.

Answer the user's question using ONLY the FAQ context provided below.

If the answer cannot be found in the context, say:
"I don't know based on the available FAQ information."

Do not invent policies, prices, timelines, or other information.

FAQ CONTEXT:
{context}

USER QUESTION:
{query}

ANSWER:
"""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()


# -----------------------------
# Complete FAQ chain
# -----------------------------

def faq_chain(query: str, top_k: int = 3) -> str:
    results = get_relevant_faqs(
        query=query,
        top_k=top_k
    )

    context = build_faq_context(results)

    return generate_faq_answer(
        query=query,
        context=context
    )


# -----------------------------
# Local test
# -----------------------------

if __name__ == "__main__":
    test_query = "My product arrived damaged. What should I do?"

    answer = faq_chain(test_query)

    print("Question:", test_query)
    print("Answer:", answer)