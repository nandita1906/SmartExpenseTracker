# Smart Expense Tracker API

A RESTful backend API built with **Python, FastAPI, SQLAlchemy, and SQLite** to manage personal income, expenses, categories, monthly budgets, and financial reports. The API also includes an AI-powered transaction categorization feature using Google Gemini.

**GitHub Repository:** https://github.com/nandita1906/SmartExpenseTracker

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Environment Variables](#environment-variables)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Authentication](#authentication)
- [Money Representation](#money-representation)
- [AI Transaction Categorization](#ai-transaction-categorization)
- [Database Design](#database-design)
- [Validation and Error Handling](#validation-and-error-handling)
- [Running Tests](#running-tests)
- [Design Decisions](#design-decisions)
- [Limitations and Future Improvements](#limitations-and-future-improvements)

## Features

### 1. Authentication and Security

- User registration and login.
- Password hashing using Argon2.
- JWT-based authentication for protected endpoints.
- User-specific access to transactions, categories, and budgets.
- Environment variables for sensitive credentials.

### 2. Transaction Management

- Create, view, update, and delete transactions.
- Support for income and expense transactions.
- Store transaction amount, type, category, date, note, and payment method.
- Search transactions by note.
- Filter transactions by date range, category, type, and amount.
- Sort and paginate transaction listings.
- Validate positive transaction amounts and reject future transaction dates.

### 3. Categories and Monthly Budgets

- Default categories for newly registered users.
- Custom category creation.
- Monthly budgets for individual categories.
- Budget usage status and warnings at 80% and 100%.
- Prevent deletion of categories that are in use by transactions or budgets.

### 4. Financial Reports

- Monthly income, expenses, and savings summary.
- Spending breakdown by category.
- Top five expenses.
- Summary for a custom date range.

### 5. AI-Powered Transaction Categorization

- Generate transaction suggestions from short text descriptions.
- Return structured data for amount, category, transaction type, and clarification status.
- Keep the AI prompt in a separate file.
- Validate model output before using it.
- Cache repeated AI suggestions.
- Require user confirmation before saving an AI-suggested transaction.
- Handle AI service errors without relying on unvalidated model output.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming language |
| FastAPI | REST API framework |
| SQLAlchemy | Database ORM |
| SQLite | Relational database |
| Pydantic | Request and response validation |
| python-jose | JWT authentication |
| pwdlib with Argon2 | Password hashing |
| Google Gemini API | AI transaction categorization |
| pytest | Automated testing |

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
├── tests/
│   └── test_api.py
├── .env.example
├── .gitignore
├── check_db.py
├── requirements.txt
├── sample_requests.http
└── README.md
```

### Main Files

- `main.py`: API routes and request handling.
- `models.py`: SQLAlchemy database models.
- `schemas.py`: Pydantic request and response schemas.
- `database.py`: Database configuration and session management.
- `auth.py`: Authentication and password/token handling.
- `ai_service.py`: AI request processing, validation, and caching.
- `ai_prompt.txt`: Instructions supplied to the AI model.
- `tests/test_api.py`: Automated API tests.
- `sample_requests.http`: Sample API requests.
- `.env.example`: Template for required environment variables.

## Setup and Installation

### Prerequisites

Install the following before running the application:

- Python 3.10 or a compatible version supported by the dependencies.
- Git.
- A Google Gemini API key for AI categorization.

### Step 1: Clone the repository

```bash
git clone https://github.com/nandita1906/SmartExpenseTracker.git
cd SmartExpenseTracker
```

### Step 2: Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**

```bash
python -m venv .venv
source .venv/bin/activate
```

### Step 3: Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 4: Configure environment variables

Create a local `.env` file from `.env.example`.

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder values with your own credentials.

## Environment Variables

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | Secret used to sign JWT authentication tokens |
| `GEMINI_API_KEY` | API key used to access Google Gemini |
| `GEMINI_MODEL` | Optional model configuration, if supported by the application |

Example configuration:

```env
JWT_SECRET_KEY=replace_with_a_strong_random_secret
GEMINI_API_KEY=your_gemini_api_key_here
```

If the application uses a configurable Gemini model, set `GEMINI_MODEL` to a model supported by your API account.

**Security notes:**

- Never commit `.env` to GitHub.
- Never publish real API keys or JWT secrets.
- Use a strong, private JWT secret.
- `.env.example` should contain placeholders only.

## Running the Application

Start the development server from the project root:

```bash
python -m uvicorn app.main:app --reload
```

Once the server starts, open:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc
- **Root endpoint:** http://127.0.0.1:8000/

Swagger UI can be used to register a user, log in, authorize protected requests, and test the API interactively.

## API Endpoints

The following endpoints are documented by the project.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/register` | Register a new user |
| POST | `/login` | Log in and receive a JWT |
| GET | `/me` | Get the authenticated user's information |

### Transactions

| Method | Endpoint | Description |
|---|---|---|
| POST | `/transactions` | Create a transaction |
| GET | `/transactions` | List transactions with supported search, filters, sorting, and pagination |
| PATCH | `/transactions/{transaction_id}` | Update a transaction |
| DELETE | `/transactions/{transaction_id}` | Delete a transaction |

### Categories

| Method | Endpoint | Description |
|---|---|---|
| POST | `/categories` | Create a custom category |
| GET | `/categories` | List categories |
| DELETE | `/categories/{category_id}` | Delete a category when permitted |

### Budgets

| Method | Endpoint | Description |
|---|---|---|
| POST | `/budgets` | Create or configure a monthly category budget |
| GET | `/budgets` | List budgets |
| GET | `/budgets/{budget_id}/status` | Check budget usage and warning status |

### Reports

| Method | Endpoint | Description |
|---|---|---|
| GET | `/reports/monthly` | Retrieve a monthly financial summary |
| GET | `/reports/summary?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | Retrieve a custom date-range summary |

### AI Categorization

| Method | Endpoint | Description |
|---|---|---|
| POST | `/ai/categorize` | Generate a transaction suggestion |

Protected endpoints require a valid bearer token. Use Swagger's **Authorize** option after logging in.

For request body formats and available query parameters, refer to the application's OpenAPI documentation at `/docs` and the examples in `sample_requests.http`.

## Authentication

The API uses JWT-based authentication.

The general flow is:

1. Register a user using `/register`.
2. Log in using `/login`.
3. Copy the returned access token.
4. Click **Authorize** in Swagger UI and provide the bearer token.
5. Call protected endpoints using that token.

Passwords are hashed before being stored. Protected resources must be scoped to the authenticated user to prevent access to another user's private data.

## Money Representation

Money is represented as an integer number of paise rather than a floating-point value.

Examples:

| Amount | Stored value |
|---|---:|
| ₹1 | `100` paise |
| ₹200 | `20000` paise |
| ₹1,000 | `100000` paise |
| ₹5,150 | `515000` paise |

This representation avoids common floating-point rounding problems in financial calculations.

Amounts returned by the API may be represented in paise; clients should convert them into rupees for display when needed.

## AI Transaction Categorization

### Overview

The `/ai/categorize` endpoint accepts a short transaction description and generates a structured transaction suggestion.

The implementation separates AI instructions from application logic:

- `app/ai_prompt.txt` contains the prompt.
- `app/ai_service.py` handles AI processing, response validation, and caching.
- Pydantic schemas validate structured suggestion data.
- The endpoint returns a suggestion for user confirmation rather than automatically creating a transaction.

### Prompt Design

The prompt is designed to:

1. Extract only information needed for transaction categorization.
2. Return structured JSON instead of unrestricted explanatory text.
3. Avoid inventing missing amounts, categories, or transaction details.
4. Flag ambiguous descriptions for clarification.
5. Distinguish income from expenses when the available information supports it.
6. Require user confirmation before a suggestion is saved.

The AI output is treated as an untrusted suggestion. It must be validated by the application before being returned or used in a transaction workflow.

### Example 1: Clear Expense

**Input description:**

```text
Paid 200 rupees for lunch
```

**Example API response:**

```json
{
  "message": "Please confirm this suggestion before saving",
  "suggestion": {
    "amount_paise": 20000,
    "category": "Food",
    "type": "expense",
    "needs_clarification": false
  },
  "cache": "hit",
  "saved": false
}
```

The suggestion identifies ₹200 as an expense in the Food category. The response indicates that the transaction has not been saved.

The `cache` field can be `miss` for a new request or `hit` when a matching cached suggestion is reused.

### Example 2: Ambiguous Description

**Input description:**

```text
paid ravi 2000
```

This description does not specify a currency or clearly explain the purpose of the payment. The system should request clarification instead of treating the amount and category as confirmed facts.

**Expected behavior:**

- Flag the description as ambiguous.
- Avoid inventing a category.
- Do not save a transaction.
- Ask the user to confirm the currency and any missing transaction details.

The exact response depends on the application's validated schema and implementation. Test this input against the running API and document the actual returned JSON before submission.

### Example 3: Repeated Request

**Input description:**

```text
Paid 200 rupees for lunch
```

When the same request is repeated for the same user, the service can reuse the cached suggestion rather than making another model request.

**Example response metadata:**

```json
{
  "cache": "hit",
  "saved": false
}
```

This is an abbreviated example of the cache-related fields; the complete response may contain the original suggestion and message as well.

### AI Reliability and Privacy

The application is designed to handle invalid model output and AI service errors through validation and error handling.

The API key is configured through environment variables. The AI service should send only the minimum permitted transaction information to the model, as required by the assignment, and must never send names, emails, or passwords.

AI suggestions do not automatically modify existing transactions or create new ones. The user remains responsible for confirming a suggestion before saving it.

**Important:** Verify the actual sanitized model payload, ambiguous-input response, timeout handling, rate-limit handling, and cache behavior against the current implementation before claiming that each behavior has been fully tested.

## Database Design

The application uses SQLite with SQLAlchemy models.

The documented data entities include:

- **Users:** account information and authentication data.
- **Categories:** default and user-created transaction categories.
- **Transactions:** income and expense records.
- **Budgets:** monthly category spending limits.
- **Cached AI suggestions:** previously generated suggestions used to reduce repeated requests.

The database file is named `expense_tracker.db` and is created by the application when it starts, subject to the configured database path.

The relational model and application logic are intended to maintain data integrity and isolate user-owned resources.

### Schema and Migrations

The application currently uses SQLAlchemy's `create_all()` approach to create missing tables. This does not automatically migrate existing table schemas when models change.

For a production deployment, a migration tool such as Alembic would be a useful improvement.

## Validation and Error Handling

The API uses Pydantic schemas and application-level checks for request validation.

Important business rules include:

- Transaction amounts must be positive.
- Future transaction dates are rejected.
- Invalid request fields should return clear validation errors.
- Protected resources must be scoped to the authenticated user.
- Categories in use by transactions or budgets cannot be deleted.
- Money must not be stored using binary floating-point values.
- AI responses must be validated before use.

The API uses HTTP status codes and JSON responses to communicate success and errors. Exact status codes depend on the endpoint and the specific failure.

## Running Tests

Install dependencies and run the automated test suite from the project root:

```bash
python -m pytest -v
```

The repository includes `tests/test_api.py`. The tests are intended to cover key API flows and validation behavior, including authentication, transaction amount validation, future-date rejection, and user-specific access.

The application can also be tested interactively through Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Before submission, run the test suite locally and update this section if the actual test coverage or results differ from the description.

## Sample API Requests

The repository includes [`sample_requests.http`](sample_requests.http), which contains sample requests for interacting with the API.

Use these requests alongside Swagger UI to test registration, authentication, transaction operations, reporting, budgets, and AI categorization.

Protected requests require a valid JWT. Request body fields and query parameters should match the application's current Pydantic schemas and route definitions.

## Design Decisions

### FastAPI

FastAPI provides request validation, structured API responses, and automatically generated OpenAPI documentation.

### SQLite and SQLAlchemy

SQLite keeps local setup simple for an assignment-sized project. SQLAlchemy provides a relational data model and a consistent interface for database operations.

### Integer-Based Money Storage

Storing money in paise avoids floating-point rounding issues in calculations.

### Separate AI Prompt

Keeping the prompt in `app/ai_prompt.txt` makes the AI behavior easier to inspect, maintain, and improve without embedding all instructions inside a route.

### User Confirmation for AI Suggestions

AI output is not treated as authoritative financial data. Requiring user confirmation reduces the risk of saving incorrect amounts or categories.

### Environment-Based Configuration

Credentials are provided through environment variables rather than hard-coded into the source code.

## Limitations and Future Improvements

The current project is an assignment-oriented API rather than a fully deployed production service.

Potential improvements include:

- Database schema migrations using Alembic.
- Additional unit and integration tests for all business rules.
- CSV export of transactions.
- Recurring transactions for rent and subscriptions.
- Docker-based development and deployment.
- More comprehensive API examples and deployment documentation.
- Additional verification of AI privacy constraints, ambiguous inputs, and failure handling.
- Production deployment configuration, logging, monitoring, and rate limiting.

## Project Status

The repository contains the core API implementation, AI categorization service, configuration template, sample requests, and an automated test suite.

Manual testing has previously been performed for login, AI categorization and caching, listing operations, custom-range reporting, zero-amount validation, and rejection of future transaction dates. Automated tests should be rerun before submission to confirm the current state.

This project was developed as a technical assignment for the Backend Developer Internship at Parvati & Sons. The implementation should be reviewed and tested against the assignment's requirements before production use.
