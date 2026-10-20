# Smart Expense Tracker API

A backend REST API built using Python, FastAPI, SQLAlchemy, and SQLite to manage personal income, expenses, categories, and monthly budgets.

## Features

- User registration and login
- Password hashing and JWT authentication
- Create, view, update, and delete transactions
- Transaction search, filtering, sorting, and pagination
- User-specific expense categories
- Monthly category budgets
- Budget alerts at 80% and 100% usage
- Monthly income, expense, and savings reports
- Top 5 expenses
- Input validation and database error handling

## Tech Stack

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- JWT authentication
- Argon2 password hashing

## Setup Instructions

1. Clone this repository.
2. Open the project folder in the terminal.
3. Create and activate a virtual environment.
4. Install the dependencies:

   `pip install -r requirements.txt`

5. Set the JWT secret key in PowerShell:

   `$env:JWT_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"`

6. Start the API:

   `python -m uvicorn app.main:app --reload`

7. Open the interactive API documentation:

   `http://127.0.0.1:8000/docs`

## Database

The application uses SQLite and creates its database tables when the application starts. The database file is named `expense_tracker.db`.

## Security

- Passwords are hashed before storage.
- Protected endpoints require a JWT access token.
- Users can access only their own transactions, categories, and budgets.
- Input validation helps reject invalid requests.

## Project Status

Core authentication, transaction management, category management, budgeting, and monthly reporting features have been implemented and tested.

