# Smart Expense Tracker API

A REST API built with Python, FastAPI, SQLAlchemy, and SQLite to manage personal income, expenses, categories, monthly budgets, and spending reports. It also provides an AI-powered transaction categorization feature.

## Features

### Authentication and Security
- User registration and login
- Argon2 password hashing
- JWT-based authentication
- User-specific access to transactions, categories, and budgets

### Transaction Management
- Create, view, update, and delete transactions
- Search transactions by note
- Filter by date range, category, type, and amount
- Sort results and paginate transaction lists
- Validate positive amounts and prevent future-dated transactions

### Categories and Budgets
- Default categories for newly registered users
- Create custom categories
- Set monthly budgets for categories
- Budget usage warnings at 80% and 100%
- Prevent deletion of categories used by transactions or budgets

### Reports
- Monthly income, expenses, and savings
- Spending breakdown by category
- Top five expenses
- Summary for a custom date range

### AI Transaction Categorization
- Suggests transaction amounts, categories, and types from short descriptions
- Uses a separate prompt file: `app/ai_prompt.txt`
- Validates structured JSON responses
- Caches AI suggestions to reduce repeated requests
- Returns suggestions for user confirmation; transactions are not saved automatically
- Handles AI service errors with meaningful responses

## Tech Stack

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- JWT (`python-jose`)
- Argon2 (`pwdlib`)
- Google Gemini API (`google-genai`)

## Project Structure

```text
SmartExpenseTracker/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── auth.py
│   ├── ai_service.py
│   └── ai_prompt.txt
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── check_db.py
```

## Setup Instructions

### 1. Clone the repository

```powershell
git clone https://github.com/nandita1906/SmartExpenseTracker.git
cd SmartExpenseTracker
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set your own values:

```dotenv
JWT_SECRET_KEY=replace_with_a_random_secret
GEMINI_API_KEY=your_gemini_api_key_here
```

Use a strong, private JWT secret and your own Gemini API key. Never commit `.env` or publish API keys.

The Gemini API key is needed for AI categorization. Keep your credentials private.

### 5. Run the application

```powershell
python -m uvicorn app.main:app --reload
```

### 6. Open API documentation

- Swagger UI: http://127.0.0.1:8000/docs
- Root endpoint: http://127.0.0.1:8000/

Use Swagger UI to register, log in, authorize protected requests, and test endpoints.

## API Endpoints

Authentication:
- `POST /register` — register a user
- `POST /login` — log in and receive a JWT
- `GET /me` — view the authenticated user

Transactions:
- `POST /transactions` — create a transaction
- `GET /transactions` — list, search, filter, sort, and paginate transactions
- `PATCH /transactions/{transaction_id}` — update a transaction
- `DELETE /transactions/{transaction_id}` — delete a transaction

Categories:
- `POST /categories` — create a category
- `GET /categories` — list categories
- `DELETE /categories/{category_id}` — delete an unused category

Budgets:
- `POST /budgets` — create or configure a monthly category budget
- `GET /budgets` — list budgets
- `GET /budgets/{budget_id}/status` — check budget usage and warning status

Reports:
- `GET /reports/monthly` — monthly financial report
- `GET /reports/summary?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — report for a custom date range

AI:
- `POST /ai/categorize` — generate an AI transaction suggestion

Protected endpoints require a bearer token. Log in using `/login`, copy `access_token`, and click **Authorize** in Swagger UI.

## Money Representation

Money is stored as an integer number of paise rather than a floating-point number.

For example:
- ₹200 = `20000` paise
- ₹1,000 = `100000` paise
- `515000` paise = ₹5,150

This avoids floating-point rounding errors in monetary calculations.

## AI Feature: Design and Examples

The AI categorization endpoint receives a short transaction description and returns a structured suggestion. The prompt is maintained separately in `app/ai_prompt.txt`, while `app/ai_service.py` handles the AI request, validation, and response processing.

The service caches suggestions by user and input hash. A repeated request can return a cached result. AI suggestions do not automatically create transactions; the user must confirm them separately.

### Example 1: Clear transaction

Input:

```json
{
  "description": "Paid 200 rupees for lunch"
}
```

Example output:

```json
{
  "message": "Please confirm this suggestion before saving",
  "suggestion": {
    "amount_paise": 20000,
    "category": "Food",
    "type": "expense",
    "needs_clarification": false
  },
  "cache": "miss",
  "saved": false
}
```

### Example 2: Ambiguous transaction

Input:

```json
{
  "description": "paid ravi 2000"
}
```

Example suggestion:

```json
{
  "amount_paise": 200000,
  "category": null,
  "type": "expense",
  "needs_clarification": true
}
```

The missing or ambiguous details require clarification before the user creates a transaction. AI output can vary; the example illustrates the intended clarification behavior.

### Example 3: Repeated transaction request

Input:

```json
{
  "description": "Paid 200 rupees for lunch"
}
```

Example output metadata from a repeated request:

```json
{
  "cache": "hit",
  "saved": false
}
```

The cached suggestion is reused, and the transaction remains unsaved until the user confirms it.

The AI integration uses the Gemini API. API credentials are loaded from environment variables, and the prompt is kept separate from application code. The service validates structured output and handles service failures rather than treating every model response as valid.

## Database

The application uses SQLite and creates tables when the application starts. The database file is named `expense_tracker.db`.

SQLAlchemy models define users, categories, transactions, budgets, and cached AI suggestions. The application uses database constraints and relationships to support data integrity.

**Note:** `create_all()` creates missing tables but does not automatically migrate existing table schemas. A migration tool should be introduced if the schema changes after deployment.

## Validation and Error Handling

- Positive transaction amounts are required.
- Future transaction dates are rejected.
- Invalid request fields are validated by Pydantic.
- Protected resources are scoped to the authenticated user.
- Categories in use by transactions or budgets cannot be deleted.
- Errors are returned as JSON responses with suitable HTTP status codes.

Examples tested:
- `200 OK` — successful category, transaction, report, and AI requests
- `400 Bad Request` — transaction date in the future
- `422 Unprocessable Entity` — amount is zero

## Environment Variables

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | Signs authentication tokens |
| `GEMINI_API_KEY` | Authenticates requests to the Gemini API |

Use `.env.example` as a template. Do not commit `.env`, database files, virtual environments, or secret credentials.

## Running Tests

The API can be tested interactively through Swagger UI at `http://127.0.0.1:8000/docs`. Test authentication, transaction validation, categories, budgets, reports, and AI categorization using the documented endpoints.

## Project Status

The main API features have been implemented. Manual testing has verified login, AI categorization and caching, category and transaction listing, custom-range reporting, zero-amount validation, and rejection of future transaction dates.

## Future Improvements

- Automated unit and integration tests
- Database migrations with Alembic
- CSV export
- Recurring transactions
- Docker support
- Expanded API documentation and deployment configuration
