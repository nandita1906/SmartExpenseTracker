import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.schemas import AITransactionSuggestion

load_dotenv()

PROMPT_FILE = Path(__file__).with_name("ai_prompt.txt")

CATEGORY_KEYWORDS = {
    "Food": ("food", "lunch", "dinner", "breakfast", "swiggy", "zomato"),
    "Travel": ("travel", "uber", "ola", "fuel", "petrol", "taxi"),
    "Shopping": ("shopping", "bought", "purchase"),
    "Rent": ("rent",),
    "Bills": ("bill", "bills", "electricity"),
    "Medical": ("medicine", "medical", "pharmacy"),
    "Education": ("education", "fees", "tuition"),
    "Entertainment": ("entertainment", "movie", "cinema"),
}

INCOME_WORDS = {
    "received", "earned", "salary", "income", "credited"
}

EXPENSE_WORDS = {
    "paid", "pay", "spent", "bought", "purchase", "expense"
}

RUPEE_WORDS = {"rupee", "rupees", "rs", "inr"}


def sanitize_description(description: str) -> str:
    """Extract structured transaction information locally."""
    text = description.lower()

    date_pattern = (
        r"\b\d{4}-\d{1,2}-\d{1,2}\b"
        r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    )

    text_without_dates = re.sub(date_pattern, " ", text)
    words = set(re.findall(r"[a-z]+", text_without_dates))

    amounts = re.findall(
        r"(?<!\w)\d[\d,]*(?:\.\d{1,2})?(?!\w)",
        text_without_dates,
    )

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

    # Send only structured fields, never the original description.
    safe_data = {
        "amounts": amounts,
        "categories": categories,
        "dates": re.findall(date_pattern, text),
        "type": transaction_type,
        "currency": (
            "INR"
            if "₹" in description
            or words.intersection(RUPEE_WORDS)
            or re.search(r"\binr\b", text)
            else None
        ),
    }

    return json.dumps(safe_data)


def suggest_transaction(description: str) -> AITransactionSuggestion:
    """Generate and validate a transaction suggestion."""
    if not description or not description.strip():
        raise ValueError("Transaction description cannot be empty")

    if len(description) > 500:
        raise ValueError(
            "Description must be 500 characters or fewer"
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini API key is not configured")

    if not PROMPT_FILE.is_file():
        raise RuntimeError("AI prompt file is missing")

    safe_data = json.loads(sanitize_description(description))

    # Resolve only information that is unambiguous.
    amount_paise = None
    amount_is_clear = False

    if len(safe_data["amounts"]) == 1:
        if safe_data["currency"] == "INR":
            try:
                amount = Decimal(
                    safe_data["amounts"][0].replace(",", "")
                )
                paise = amount * 100

                if (
                    amount > 0
                    and paise == paise.to_integral_value()
                ):
                    amount_paise = int(paise)
                    amount_is_clear = True

            except InvalidOperation:
                pass

    category = (
        safe_data["categories"][0]
        if len(safe_data["categories"]) == 1
        else None
    )

    transaction_type = safe_data["type"]

    # If all required details are clear locally, return them directly.
    # This avoids unnecessary AI calls for straightforward descriptions.
    if (
        amount_is_clear
        and category is not None
        and transaction_type is not None
    ):
        return AITransactionSuggestion(
            amount_paise=amount_paise,
            category=category,
            type=transaction_type,
            needs_clarification=False,
        )

    prompt = PROMPT_FILE.read_text(encoding="utf-8")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60000),
    )

    try:
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=(
                f"{prompt}\n\n"
                f"Structured transaction data: "
                f"{json.dumps(safe_data)}"
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AITransactionSuggestion,
            ),
        )

    except Exception as exc:
        error_text = str(exc).upper()

        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            raise RuntimeError(
                "AI rate limit reached. Please try again later."
            ) from exc

        if "504" in error_text or "DEADLINE_EXCEEDED" in error_text:
            raise RuntimeError(
                "Gemini request timed out. Please try again later."
            ) from exc

        if "404" in error_text or "NOT_FOUND" in error_text:
            raise RuntimeError(
                "Gemini model was not found. Check GEMINI_MODEL."
            ) from exc

        if "401" in error_text or "403" in error_text:
            raise RuntimeError(
                "Gemini API authentication or permission failed."
            ) from exc

        raise RuntimeError(
            "AI service is temporarily unavailable. Please try again."
        ) from exc

    if not response.text:
        raise ValueError("AI returned an empty response")

    try:
        suggestion = AITransactionSuggestion.model_validate_json(
            response.text
        )
    except Exception as exc:
        raise ValueError(
            "AI returned invalid transaction data"
        ) from exc

    # Prefer clear, locally extracted facts over incomplete AI output.
    if amount_is_clear:
        suggestion.amount_paise = amount_paise

    if category is not None:
        suggestion.category = category

    if transaction_type is not None:
        suggestion.type = transaction_type

    if (
        suggestion.amount_paise is not None
        and suggestion.amount_paise <= 0
    ):
        raise ValueError("AI returned an invalid amount")

    suggestion.needs_clarification = (
        suggestion.amount_paise is None
        or not suggestion.category
        or not suggestion.type
    )

    return suggestion