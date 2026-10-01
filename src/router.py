from semantic_router import Route
from semantic_router.routers import SemanticRouter
from semantic_router.encoders import HuggingFaceEncoder

from src.config import EMBEDDING_MODEL


# -----------------------------
# Encoder
# -----------------------------

encoder = HuggingFaceEncoder(
    name=EMBEDDING_MODEL
)


# -----------------------------
# Routes
# -----------------------------

faq_route = Route(
    name="faq",
    utterances=[
        "What is your return policy?",
        "How can I track my order?",
        "What payment methods are accepted?",
        "How long does a refund take?",
        "Can I cancel my order?",
        "Do you offer international shipping?",
        "What should I do if my product is damaged?",
        "Can I use a promo code?",
        "Are there any ongoing sales or promotions?"
    ]
)


product_route = Route(
    name="product",
    utterances=[
        "Show me Nike shoes under 5000",
        "What are the cheapest shoes available?",
        "Show products with rating above 4.5",
        "Which Campus shoes have the highest discount?",
        "Suggest Puma shoes under 3000",
        "Show me the top rated products",
        "Show me 5 shoes under 1500 rupees",
        "Which products have the biggest discount?",
        "How many products are available?"
    ]
)


smalltalk_route = Route(
    name="smalltalk",
    utterances=[
        "Hello",
        "Hi",
        "How are you?",
        "What is your name?",
        "Who are you?",
        "Are you a robot?",
        "What can you do?"
    ]
)


# -----------------------------
# Router
# -----------------------------

router = SemanticRouter(
    encoder=encoder,
    routes=[
        faq_route,
        product_route,
        smalltalk_route
    ],
    auto_sync="local"
)

router.set_threshold(0.40)


# -----------------------------
# Public routing function
# -----------------------------

def route_query(query: str):
    result = router(query)

    return result.name


# -----------------------------
# Local test
# -----------------------------

if __name__ == "__main__":
    test_queries = [
        "My product arrived damaged",
        "Show me Puma shoes under 3000",
        "Hey, how are you?",
        "Explain quantum physics"
    ]

    for query in test_queries:
        print(
            query,
            "→",
            route_query(query)
        )