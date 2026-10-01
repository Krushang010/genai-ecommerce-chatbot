import json
import re
from typing import Any

from groq import Groq

from src.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
)


groq_client = Groq(api_key=GROQ_API_KEY)


# --------------------------------------------------
# Empty product search state
# --------------------------------------------------

EMPTY_PRODUCT_STATE = {
    "product_type": None,
    "brand": None,
    "min_price": None,
    "max_price": None,
    "min_rating": None,
    "min_discount": None,
    "limit": None,
    "sort": None,
}


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def normalize_product_state(
    state: dict | None
) -> dict:

    normalized = EMPTY_PRODUCT_STATE.copy()

    if state:
        for key in normalized:
            if key in state:
                normalized[key] = state[key]

    # Clean string fields
    for key in ["product_type", "brand", "sort"]:
        value = normalized.get(key)

        if isinstance(value, str):
            value = value.strip()

            if value.lower() in {
                "",
                "none",
                "null",
                "any",
                "no preference",
            }:
                value = None

        normalized[key] = value

    # Numeric fields
    for key in [
        "min_price",
        "max_price",
        "min_rating",
        "min_discount",
    ]:
        value = normalized.get(key)

        if value is not None:
            try:
                normalized[key] = float(value)
            except (TypeError, ValueError):
                normalized[key] = None

    # Limit
    if normalized["limit"] is not None:
        try:
            normalized["limit"] = int(
                normalized["limit"]
            )
        except (TypeError, ValueError):
            normalized["limit"] = None

    return normalized


def extract_json(text: str) -> dict | None:

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        match = re.search(
            r"\{.*\}",
            text,
            re.DOTALL,
        )

        if not match:
            return None

        try:
            return json.loads(
                match.group(0)
            )

        except json.JSONDecodeError:
            return None


# --------------------------------------------------
# Product conversational memory
# --------------------------------------------------

def update_product_state(
    query: str,
    previous_state: dict | None,
) -> tuple[dict, bool]:
    """
    Returns:
        updated_state
        related_to_product_context
    """

    previous_state = normalize_product_state(
        previous_state
    )

    prompt = f"""
You manage the search state of an e-commerce product assistant.

You are given:

PREVIOUS PRODUCT SEARCH STATE:
{json.dumps(previous_state, indent=2)}

CURRENT USER MESSAGE:
{query}

Your job is to determine the COMPLETE product search state
the user wants after the current message.

Return ONLY valid JSON in this exact structure:

{{
    "related": true,
    "state": {{
        "product_type": null,
        "brand": null,
        "min_price": null,
        "max_price": null,
        "min_rating": null,
        "min_discount": null,
        "limit": null,
        "sort": null
    }}
}}

Allowed sort values:

- "best"
- "price_asc"
- "price_desc"
- "rating_desc"
- "discount_desc"
- "reviews_desc"
- null


IMPORTANT RULES:

1. "related" must be true when the message:
   - starts a product search
   - modifies a product search
   - refines previous results
   - removes a previous filter
   - asks "what about another brand?"
   - changes price/rating/discount/quantity/sorting

2. "related" must be false for unrelated requests such as:
   - explain quantum physics
   - calculate mathematics
   - write code
   - unrelated general questions

3. Return the FULL desired state, not only changed fields.


FOLLOW-UP EXAMPLES:

Previous:
brand = Nike
max_price = 3000
product_type = shoes

Current:
"What about Adidas?"

New full state:
brand = Adidas
max_price = 3000
product_type = shoes


Previous:
brand = Adidas
max_price = 3000

Current:
"Only those rated above 4"

New full state:
brand = Adidas
max_price = 3000
min_rating = 4


REMOVING CONSTRAINTS:

Previous:
brand = Adidas

Current:
"Any brand would be fine"

New state:
brand = null

Preserve other relevant filters.


Previous:
min_rating = 4

Current:
"Forget about the rating"

New state:
min_rating = null


FRESH COMPLETE REQUESTS:

If the user writes a complete new product request,
use ONLY the constraints mentioned in that new request.

Do NOT keep old filters that the new request does not mention.

Example:

Previous state:
brand = Adidas
max_price = 2500
min_rating = 4
limit = 1
sort = best

Current:
"Show me shoes under 2500 but the best 1 only"

New state:

product_type = shoes
brand = null
min_price = null
max_price = 2500
min_rating = null
min_discount = null
limit = 1
sort = best


INTERPRETATIONS:

"best"
→ sort = "best"

"highest rated"
→ sort = "rating_desc"

"cheapest"
→ sort = "price_asc"

"highest discount"
→ sort = "discount_desc"

"most reviewed"
→ sort = "reviews_desc"

"best 1 only"
→ limit = 1 and sort = "best"

"top 5"
→ limit = 5

"under 2500"
→ max_price = 2500

"above rating 4"
→ min_rating = 4

Never invent filters the user did not request.
"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
        )

        raw_output = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        parsed = extract_json(raw_output)

        if not parsed:
            return previous_state, False

        related = bool(
            parsed.get("related", False)
        )

        new_state = normalize_product_state(
            parsed.get(
                "state",
                previous_state,
            )
        )

        return new_state, related

    except Exception as error:
        print(
            f"Product context error: {error}"
        )

        return previous_state, False


# --------------------------------------------------
# Convert structured state → standalone query
# --------------------------------------------------

def build_product_query(
    state: dict
) -> str:

    state = normalize_product_state(state)

    product_type = (
        state["product_type"]
        or "products"
    )

    brand = state["brand"]

    if brand:
        query = (
            f"Show me {brand} "
            f"{product_type}"
        )
    else:
        query = (
            f"Show me {product_type}"
        )

    # Price
    if state["min_price"] is not None:
        query += (
            f" above {state['min_price']:g} rupees"
        )

    if state["max_price"] is not None:
        query += (
            f" under {state['max_price']:g} rupees"
        )

    # Rating
    if state["min_rating"] is not None:
        query += (
            f" with rating above "
            f"{state['min_rating']:g}"
        )

    # Discount
    if state["min_discount"] is not None:
        query += (
            f" with discount above "
            f"{state['min_discount']:g} percent"
        )

    # Sorting
    sort_map = {
        "best": "Sort by best overall.",
        "price_asc": "Sort by cheapest first.",
        "price_desc": "Sort by highest price first.",
        "rating_desc": "Sort by highest rated first.",
        "discount_desc": "Sort by highest discount first.",
        "reviews_desc": "Sort by most reviewed first.",
    }

    sort_value = state.get("sort")

    if sort_value in sort_map:
        query += " " + sort_map[sort_value]

    # Limit
    if state["limit"] is not None:
        query += (
            f" Return only "
            f"{state['limit']} result"
        )

        if state["limit"] != 1:
            query += "s"

        query += "."

    return query


# --------------------------------------------------
# FAQ contextualization
# --------------------------------------------------

def contextualize_faq_query(
    query: str,
    previous_query: str | None,
) -> str:

    if not previous_query:
        return query

    prompt = f"""
You are a query contextualizer for an e-commerce FAQ assistant.

Rewrite the CURRENT QUERY into a complete standalone question
ONLY when it depends on the previous FAQ question.

Do not answer the question.

PREVIOUS FAQ QUERY:
{previous_query}

CURRENT QUERY:
{query}

Examples:

Previous:
"What is your return policy?"

Current:
"How many days exactly?"

Output:
"How many days do I have to return a product?"


If the current query is already a new standalone question,
return it unchanged.

Return ONLY the rewritten question.
"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
        )

        return (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

    except Exception as error:
        print(
            f"FAQ context error: {error}"
        )

        return query