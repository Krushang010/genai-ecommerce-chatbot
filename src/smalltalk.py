from groq import Groq

from src.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
)


groq_client = Groq(api_key=GROQ_API_KEY)


def smalltalk_chain(query: str) -> str:
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a friendly e-commerce chatbot assistant. "
                    "Respond briefly and naturally. "
                    "Keep the conversation related to the shopping assistant "
                    "when appropriate."
                )
            },
            {
                "role": "user",
                "content": query
            }
        ],
        temperature=0.3
    )

    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    print(smalltalk_chain("Hey, how are you?"))