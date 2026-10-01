import re
import sqlite3

import pandas as pd
from groq import Groq

from src.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    DB_PATH,
)


# --------------------------------------------------
# LLM client
# --------------------------------------------------

groq_client = Groq(
    api_key=GROQ_API_KEY
)


# --------------------------------------------------
# SQL prompt
# --------------------------------------------------

SQL_PROMPT = """
You convert natural-language e-commerce product questions
into valid SQLite queries.

DATABASE:

Table: product

Columns:
- product_link: TEXT
- title: TEXT
- brand: TEXT
- price: INTEGER
- discount: REAL
- avg_rating: REAL
- total_ratings: INTEGER


RULES:

1. Generate ONLY SELECT queries.

2. Query ONLY the product table.

3. Use SELECT * for normal product searches.

4. Aggregations such as COUNT, AVG, MIN, and MAX are allowed.

5. Brand searches must be case-insensitive:

LOWER(brand) LIKE LOWER('%brand_name%')

6. Interpret sorting requests as follows:

"best" or "best overall"
→ ORDER BY avg_rating DESC, total_ratings DESC

"highest rated"
→ ORDER BY avg_rating DESC

"cheapest"
→ ORDER BY price ASC

"most expensive"
→ ORDER BY price DESC

"highest discount"
→ ORDER BY discount DESC

"most reviewed"
→ ORDER BY total_ratings DESC

7. Respect the requested LIMIT exactly.

Example:

"best 1 only"
→ LIMIT 1

"top 5"
→ LIMIT 5

8. If no number is specified for a normal product list,
use LIMIT 10.

9. Never generate:

INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
REPLACE
PRAGMA
ATTACH
DETACH

10. Return ONLY SQL inside:

<SQL>
...
</SQL>
"""


# --------------------------------------------------
# Aggregate answer prompt
# --------------------------------------------------

AGGREGATE_PROMPT = """
You are a concise e-commerce assistant.

Answer the user's question using ONLY the supplied database result.

Do not mention:
- SQL
- database
- dataframe
- implementation details

Do not invent information.
"""


# --------------------------------------------------
# Generate SQL
# --------------------------------------------------

def generate_sql_query(
    question: str,
) -> str:

    response = (
        groq_client
        .chat
        .completions
        .create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SQL_PROMPT,
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
            temperature=0,
        )
    )

    return (
        response
        .choices[0]
        .message
        .content
        .strip()
    )


# --------------------------------------------------
# Extract SQL
# --------------------------------------------------

def extract_sql(
    response: str,
):

    match = re.search(
        r"<SQL>(.*?)</SQL>",
        response,
        re.DOTALL | re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1).strip()


# --------------------------------------------------
# SQL safety
# --------------------------------------------------

def is_safe_sql(
    query: str,
) -> bool:

    if not query:
        return False

    cleaned = query.strip()

    cleaned_without_end = (
        cleaned
        .rstrip(";")
        .strip()
    )

    # Block multiple statements
    if ";" in cleaned_without_end:
        return False

    if not (
        cleaned_without_end
        .upper()
        .startswith("SELECT")
    ):
        return False

    forbidden_words = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "REPLACE",
        "PRAGMA",
        "ATTACH",
        "DETACH",
    ]

    for word in forbidden_words:

        if re.search(
            rf"\b{word}\b",
            cleaned_without_end,
            re.IGNORECASE,
        ):
            return False

    return True


# --------------------------------------------------
# Execute SQL
# --------------------------------------------------

def run_query(
    query: str,
) -> pd.DataFrame:

    if not is_safe_sql(query):
        raise ValueError(
            "Unsafe SQL query blocked."
        )

    with sqlite3.connect(DB_PATH) as conn:

        # Extra protection
        conn.execute(
            "PRAGMA query_only = ON"
        )

        return pd.read_sql_query(
            query,
            conn,
        )


# --------------------------------------------------
# Deduplicate product results
# --------------------------------------------------

def deduplicate_products(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df

    required = {
        "title",
        "brand",
    }

    if not required.issubset(df.columns):
        return df

    return (
        df
        .drop_duplicates(
            subset=[
                "brand",
                "title",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )


# --------------------------------------------------
# Markdown helpers
# --------------------------------------------------

def clean_markdown_text(
    value,
) -> str:

    if pd.isna(value):
        return "N/A"

    text = str(value)

    # Prevent product titles containing |
    # from breaking Markdown tables
    text = text.replace(
        "|",
        "\\|",
    )

    text = text.replace(
        "\n",
        " ",
    )

    return text


def discount_to_percent(
    value,
) -> str:

    if pd.isna(value):
        return "N/A"

    value = float(value)

    if value <= 1:
        value *= 100

    return f"{value:.0f}%"


# --------------------------------------------------
# Deterministic product presentation
# --------------------------------------------------

def format_product_results(
    df: pd.DataFrame,
) -> str:

    df = deduplicate_products(df)

    lines = [
        "| Product | Brand | Price | Discount | Rating | Link |",
        "|---|---|---:|---:|---:|---|",
    ]

    for _, row in df.iterrows():

        title = clean_markdown_text(
            row.get("title")
        )

        brand = clean_markdown_text(
            row.get("brand")
        )

        price = row.get("price")

        if pd.notna(price):
            price_text = (
                f"₹{float(price):,.0f}"
            )
        else:
            price_text = "N/A"

        discount = discount_to_percent(
            row.get("discount")
        )

        rating = row.get(
            "avg_rating"
        )

        if pd.notna(rating):
            rating_text = (
                f"{float(rating):.1f}"
            )
        else:
            rating_text = "N/A"

        link = row.get(
            "product_link"
        )

        if pd.notna(link):
            link_text = (
                f"[View product]({link})"
            )
        else:
            link_text = "N/A"

        lines.append(
            f"| {title} "
            f"| {brand} "
            f"| {price_text} "
            f"| {discount} "
            f"| {rating_text} "
            f"| {link_text} |"
        )

    return "\n".join(lines)


# --------------------------------------------------
# Aggregate response
# --------------------------------------------------

def generate_aggregate_answer(
    question: str,
    records: list,
) -> str:

    response = (
        groq_client
        .chat
        .completions
        .create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": AGGREGATE_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        f"QUESTION:\n"
                        f"{question}\n\n"
                        f"DATA:\n"
                        f"{records}"
                    ),
                },
            ],
            temperature=0,
        )
    )

    return (
        response
        .choices[0]
        .message
        .content
        .strip()
    )


# --------------------------------------------------
# Detect product-list result
# --------------------------------------------------

def is_product_result(
    df: pd.DataFrame,
) -> bool:

    required_columns = {
        "title",
        "brand",
        "price",
        "discount",
        "avg_rating",
        "product_link",
    }

    return required_columns.issubset(
        df.columns
    )


# --------------------------------------------------
# Complete SQL chain
# --------------------------------------------------

def sql_chain(
    question: str,
) -> str:

    try:

        # ------------------------------------------
        # 1. Natural language → SQL
        # ------------------------------------------

        raw_response = (
            generate_sql_query(
                question
            )
        )


        # ------------------------------------------
        # 2. Extract SQL
        # ------------------------------------------

        sql_query = extract_sql(
            raw_response
        )

        if not sql_query:
            return (
                "Sorry, I couldn't generate "
                "a valid product query."
            )


        print(
            "\nGenerated SQL:"
        )

        print(sql_query)


        # ------------------------------------------
        # 3. Validate
        # ------------------------------------------

        if not is_safe_sql(
            sql_query
        ):
            return (
                "The generated query was "
                "blocked for safety."
            )


        # ------------------------------------------
        # 4. Execute
        # ------------------------------------------

        result_df = run_query(
            sql_query
        )


        if result_df.empty:
            return (
                "No matching products "
                "were found."
            )


        # ------------------------------------------
        # 5A. Product results
        #
        # Format ourselves instead of asking
        # another LLM to rewrite factual rows.
        # ------------------------------------------

        if is_product_result(
            result_df
        ):
            return format_product_results(
                result_df
            )


        # ------------------------------------------
        # 5B. Aggregation results
        # ------------------------------------------

        records = (
            result_df
            .to_dict(
                orient="records"
            )
        )

        return generate_aggregate_answer(
            question=question,
            records=records,
        )


    except Exception as error:

        print(
            f"SQL chain error: {error}"
        )

        return (
            "Sorry, there was a problem "
            "processing your product request."
        )


# --------------------------------------------------
# Local test
# --------------------------------------------------

if __name__ == "__main__":

    test_question = (
        "Show me the best 1 shoe "
        "under 2500 rupees"
    )

    answer = sql_chain(
        test_question
    )

    print(
        "\nAnswer:\n"
    )

    print(answer)