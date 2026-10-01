import streamlit as st

from src.data_setup import ensure_data_ready


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="E-commerce Chatbot",
    page_icon="🛍️",
    layout="centered",
)


# --------------------------------------------------
# Prepare local application data
# Runs once per Streamlit process
# --------------------------------------------------

@st.cache_resource
def bootstrap_application():
    ensure_data_ready()
    return True


bootstrap_application()


# --------------------------------------------------
# Import application components AFTER data bootstrap
# --------------------------------------------------

from src.router import route_query
from src.faq_chain import faq_chain
from src.sql_chain import sql_chain
from src.smalltalk import smalltalk_chain

from src.context import (
    EMPTY_PRODUCT_STATE,
    update_product_state,
    build_product_query,
    contextualize_faq_query,
)


# --------------------------------------------------
# Chat layout
# --------------------------------------------------

def display_message(
    role: str,
    content: str,
):

    if role == "user":

        left_space, message_col = (
            st.columns([1, 3])
        )

        with message_col:

            with st.chat_message(
                "user"
            ):
                st.markdown(
                    content
                )

    else:

        message_col, right_space = (
            st.columns([3, 1])
        )

        with message_col:

            with st.chat_message(
                "assistant"
            ):
                st.markdown(
                    content
                )


# --------------------------------------------------
# Main chatbot orchestration
# --------------------------------------------------

def ask(
    query: str,
):

    # ----------------------------------------------
    # First try normal semantic routing
    # ----------------------------------------------

    route = route_query(
        query
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "Original Query:"
    )

    print(query)

    print(
        "\nInitial Route:"
    )

    print(route)


    # ==============================================
    # PRODUCT
    # ==============================================

    if route == "product":

        new_state, related = (
            update_product_state(
                query=query,
                previous_state=(
                    st.session_state
                    .product_state
                ),
            )
        )

        standalone_query = (
            build_product_query(
                new_state
            )
        )

        print(
            "\nProduct State:"
        )

        print(
            new_state
        )

        print(
            "\nStandalone Product Query:"
        )

        print(
            standalone_query
        )

        response = sql_chain(
            standalone_query
        )

        return (
            response,
            "product",
            standalone_query,
            new_state,
        )


    # ==============================================
    # POSSIBLE PRODUCT FOLLOW-UP
    #
    # Semantic router may return None for:
    #
    # "What about Adidas?"
    # "Only above 4"
    # "Any brand is fine"
    # "Make budget 2500"
    # ==============================================

    if (
        route is None
        and
        st.session_state
        .last_business_route
        == "product"
    ):

        new_state, related = (
            update_product_state(
                query=query,
                previous_state=(
                    st.session_state
                    .product_state
                ),
            )
        )

        if related:

            standalone_query = (
                build_product_query(
                    new_state
                )
            )

            print(
                "\nProduct Follow-up State:"
            )

            print(
                new_state
            )

            print(
                "\nStandalone Product Query:"
            )

            print(
                standalone_query
            )

            response = sql_chain(
                standalone_query
            )

            return (
                response,
                "product",
                standalone_query,
                new_state,
            )


    # ==============================================
    # FAQ
    # ==============================================

    if route == "faq":

        previous_faq = None

        if (
            st.session_state
            .last_business_route
            == "faq"
        ):
            previous_faq = (
                st.session_state
                .last_faq_query
            )

        standalone_query = (
            contextualize_faq_query(
                query=query,
                previous_query=(
                    previous_faq
                ),
            )
        )

        print(
            "\nStandalone FAQ Query:"
        )

        print(
            standalone_query
        )

        response = faq_chain(
            standalone_query
        )

        return (
            response,
            "faq",
            standalone_query,
            None,
        )


    # ==============================================
    # POSSIBLE FAQ FOLLOW-UP
    # ==============================================

    if (
        route is None
        and
        st.session_state
        .last_business_route
        == "faq"
    ):

        standalone_query = (
            contextualize_faq_query(
                query=query,
                previous_query=(
                    st.session_state
                    .last_faq_query
                ),
            )
        )

        rerouted = route_query(
            standalone_query
        )

        if rerouted == "faq":

            response = faq_chain(
                standalone_query
            )

            return (
                response,
                "faq",
                standalone_query,
                None,
            )


    # ==============================================
    # SMALL TALK
    # ==============================================

    if route == "smalltalk":

        response = (
            smalltalk_chain(
                query
            )
        )

        return (
            response,
            "smalltalk",
            query,
            None,
        )


    # ==============================================
    # FALLBACK
    # ==============================================

    return (
        (
            "I'm not sure how to handle that request. "
            "I can help with products, orders, returns, "
            "payments, shipping, promotions, or other "
            "e-commerce related questions."
        ),
        None,
        query,
        None,
    )


# --------------------------------------------------
# Header
# --------------------------------------------------

st.title(
    "🛍️ E-commerce Chatbot"
)

st.caption(
    "Find products, compare prices and ratings, "
    "or ask about returns, refunds, shipping, "
    "payments, and orders."
)


# --------------------------------------------------
# UI chat history
# --------------------------------------------------

if "messages" not in st.session_state:

    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 **Hello! I'm your shopping assistant.**\n\n"
                "I can help you find products, compare prices, "
                "discounts and ratings, or answer questions about "
                "returns, refunds, shipping, payments, and orders.\n\n"
                "**How can I help you today?**"
            ),
        }
    ]


# --------------------------------------------------
# Structured product memory
# --------------------------------------------------

if "product_state" not in st.session_state:

    st.session_state.product_state = (
        EMPTY_PRODUCT_STATE.copy()
    )


# --------------------------------------------------
# Business conversation memory
# --------------------------------------------------

if "last_business_route" not in st.session_state:

    st.session_state.last_business_route = None


if "last_faq_query" not in st.session_state:

    st.session_state.last_faq_query = None


# --------------------------------------------------
# Render previous conversation
# --------------------------------------------------

for message in (
    st.session_state.messages
):

    display_message(
        role=message["role"],
        content=message["content"],
    )


# --------------------------------------------------
# Input
# --------------------------------------------------

query = st.chat_input(
    "Ask me about products, prices, orders, returns..."
)


# --------------------------------------------------
# Process query
# --------------------------------------------------

if query:

    # Save user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": query,
        }
    )

    display_message(
        role="user",
        content=query,
    )


    # Generate response
    with st.spinner(
        "Thinking..."
    ):

        (
            response,
            route,
            standalone_query,
            new_product_state,
        ) = ask(query)


    # Display response
    display_message(
        role="assistant",
        content=response,
    )


    # Save response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response,
        }
    )


    # --------------------------------------------------
    # Update PRODUCT memory
    # --------------------------------------------------

    if route == "product":

        st.session_state.product_state = (
            new_product_state
        )

        st.session_state.last_business_route = (
            "product"
        )


    # --------------------------------------------------
    # Update FAQ memory
    # --------------------------------------------------

    elif route == "faq":

        st.session_state.last_faq_query = (
            standalone_query
        )

        st.session_state.last_business_route = (
            "faq"
        )


    # --------------------------------------------------
    # Smalltalk does NOT overwrite business context
    # --------------------------------------------------