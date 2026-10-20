
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.schemas import AITransactionSuggestion

load_dotenv()

PROMPT_FILE = Path(__file__).with_name("ai_prompt.txt")

# Categories are detected locally. Original words are never sent to Gemini.
CATEGORY_KEYWORDS = {
    "food": ("food", "lunch", "dinner", "breakfast", "swiggy", "zomato"),
    "Travel": ("travel", "uber", "ola", "fuel", "petrol"),
    "Shopping": ("shopping", "bought", "purchase"),
    "Rent": ("rent",),
    "Bills": ("bill", "bills", "electricity"),
    "Medical": ("medicine", "medical", "pharmacy"),
    "Education": ("education", "fees", "tuition"),
    "Entertainment": ("entertainment", "movie", "cinema"),
}

INCOME_WORDS = {"received", "earned", "salary", "income"}
EXPENSE_WORDS = {"paid", "pay", "spent", "bought", "purchase", "expense"}


def sanitize_description(description: str) -> str:
    """Return only permitted structured transaction information."""
    text = description.lower()

    # Extract dates before amounts so date digits are not mistaken for money.
    date_pattern = (
        r"\b\d{4}-\d{1,2}-\d{1,2}\b"
        r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    )
    dates = re.findall(date_pattern, text)
    text_without_dates = re.sub(date_pattern, " ", text)

    # Extract numeric amounts; never send the original description.
    amounts = re.findall(
        r"(?<!\w)\d[\d,]*(?:\.\d{1,2})?(?!\w)",
        text_without_dates,
    )

    words = set(re.findall(r"[a-z]+", text))

    categories = [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if words.intersection(keywords)
    ]

    if words.intersection(INCOME_WORDS):
        transaction_type = "income"
    elif words.intersection(EXPENSE_WORDS):
        transaction_type = "expense"
    else:
        transaction_type = None

    safe_data = {
        "amounts": amounts,
        "categories": categories,
        "dates": dates,
        "type": transaction_type,
    }

    return json.dumps(safe_data)


def suggest_transaction(description: str):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("Gemini API key is not configured")

    if not description or not description.strip():
        raise ValueError("Transaction description cannot be empty")

    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    safe_data = sanitize_description(description)

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=15000),
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=f"{prompt}\n\nSafe transaction data: {safe_data}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AITransactionSuggestion,
            ),
        )
    except Exception as exc:
        # Return a clear service error without exposing credentials or input.
        raise RuntimeError(
            "AI service is temporarily unavailable. Please try again later."
        ) from exc

    if not response.text:
        raise ValueError("AI returned an empty response")

    try:
        suggestion = AITransactionSuggestion.model_validate_json(
            response.text
        )
    except Exception as exc:
        raise ValueError("AI returned invalid transaction data") from exc

    if (
        suggestion.amount_paise is not None
        and suggestion.amount_paise <= 0
    ):
        raise ValueError("AI returned an invalid amount")

    # Incomplete information must be clarified before the user saves it.
    if (
        suggestion.amount_paise is None
        or not suggestion.category
        or not suggestion.type
    ):
        suggestion.needs_clarification = True

    return suggestion
