
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.schemas import AITransactionSuggestion

load_dotenv()

PROMPT_FILE = Path(__file__).with_name("ai_prompt.txt")

def sanitize_description(description: str) -> str:
    allowed_words = {
        "paid", "pay", "spent", "bought", "purchase",
        "received", "earned", "salary", "income",
        "expense", "lunch", "dinner", "breakfast",
        "food", "grocery", "groceries", "rent",
        "travel", "fuel", "petrol", "shopping",
        "bill", "bills", "medicine", "medical",
        "education", "fees", "entertainment",
        "transfer", "refund", "rupee", "rupees",
        "rs", "inr", "for", "on", "from"
    }

    tokens = re.findall(
        r"\d+(?:[.,]\d+)?|[a-z]+|₹",
        description.lower()
    )

    safe_tokens = [
        token for token in tokens
        if token.isdigit()
        or re.fullmatch(r"\d+(?:[.,]\d+)", token)
        or token == "₹"
        or token in allowed_words
    ]

    return " ".join(safe_tokens)


def suggest_transaction(description: str):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("Gemini API key is not configured")

    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    safe_description = sanitize_description(description)

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30000),
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"{prompt}\n\nTransaction: {safe_description}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AITransactionSuggestion,
        ),
    )

    if not response.text:
        raise ValueError("AI returned an empty response")

    suggestion = AITransactionSuggestion.model_validate_json(
        response.text
    )

    if (
        suggestion.amount_paise is not None
        and suggestion.amount_paise <= 0
    ):
        raise ValueError("AI returned an invalid amount")

    return suggestion