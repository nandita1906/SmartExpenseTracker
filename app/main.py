import re
import hashlib
import logging
from datetime import date

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database import Base, engine, get_db
from app import models, schemas
from app.ai_service import suggest_transaction, sanitize_description
from app.auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Expense Tracker API")

DEFAULT_CATEGORIES = [
    "Food",
    "Travel",
    "Shopping",
    "Rent",
    "Bills",
    "Medical",
    "Education",
    "Entertainment",
    "Other",
]


@app.get("/")
def home():
    return {"message": "Smart Expense Tracker API is running!"}


@app.post("/register")
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    email = data.email.lower()

    if db.query(models.User).filter_by(email=email).first():
        raise HTTPException(409, "Email already registered")

    user = models.User(
        email=email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.flush()

    for name in DEFAULT_CATEGORIES:
        db.add(models.Category(name=name, user_id=user.id))

    db.commit()
    db.refresh(user)

    return {"message": "Registration successful", "user_id": user.id}


@app.post("/login", response_model=schemas.Token)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(
        email=data.email.lower()
    ).first()

    if not user or not verify_password(
        data.password, user.hashed_password
    ):
        raise HTTPException(401, "Invalid email or password")

    return {
        "access_token": create_token(user.id),
        "token_type": "bearer",
    }


@app.get("/me")
def get_profile(user=Depends(get_current_user)):
    return {"id": user.id, "email": user.email}


@app.post("/transactions")
def create_transaction(
    data: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if data.date > date.today():
        raise HTTPException(400, "Transaction date cannot be in the future")

    if data.category_id is not None:
        category = db.query(models.Category).filter_by(
            id=data.category_id, user_id=user.id
        ).first()

        if not category:
            raise HTTPException(404, "Category not found")

    transaction = models.Transaction(
        **data.model_dump(),
        user_id=user.id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return {"message": "Transaction created", "id": transaction.id}


@app.get("/transactions")
def get_transactions(
    type: str | None = None,
    search: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: int | None = None,
    min_amount_paise: int | None = None,
    max_amount_paise: int | None = None,
    sort_by: str = "date",
    order: str = "desc",
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(models.Transaction).filter_by(user_id=user.id)

    if type is not None:
        if type not in ["income", "expense"]:
            raise HTTPException(400, "Invalid transaction type")
        query = query.filter(models.Transaction.type == type)

    if search:
        query = query.filter(
            models.Transaction.note.ilike(f"%{search}%")
        )

    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "start_date cannot be after end_date")

    if start_date:
        query = query.filter(models.Transaction.date >= start_date)

    if end_date:
        query = query.filter(models.Transaction.date <= end_date)

    if category_id is not None:
        category = db.query(models.Category).filter_by(
            id=category_id, user_id=user.id
        ).first()

        if not category:
            raise HTTPException(404, "Category not found")

        query = query.filter(
            models.Transaction.category_id == category_id
        )

    if min_amount_paise is not None:
        if min_amount_paise < 0:
            raise HTTPException(400, "Minimum amount cannot be negative")
        query = query.filter(
            models.Transaction.amount_paise >= min_amount_paise
        )

    if max_amount_paise is not None:
        if max_amount_paise < 0:
            raise HTTPException(400, "Maximum amount cannot be negative")
        query = query.filter(
            models.Transaction.amount_paise <= max_amount_paise
        )

    if (
        min_amount_paise is not None
        and max_amount_paise is not None
        and min_amount_paise > max_amount_paise
    ):
        raise HTTPException(
            400, "Minimum amount cannot exceed maximum amount"
        )

    if sort_by not in ["date", "amount_paise"]:
        raise HTTPException(400, "Invalid sort field")

    if order not in ["asc", "desc"]:
        raise HTTPException(400, "Order must be asc or desc")

    if skip < 0 or limit < 1 or limit > 100:
        raise HTTPException(400, "Invalid pagination values")

    column = getattr(models.Transaction, sort_by)
    query = query.order_by(
        column.asc() if order == "asc" else column.desc()
    )

    return query.offset(skip).limit(limit).all()


@app.patch("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: int,
    data: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    transaction = db.query(models.Transaction).filter_by(
        id=transaction_id, user_id=user.id
    ).first()

    if not transaction:
        raise HTTPException(404, "Transaction not found")

    updates = data.model_dump(exclude_unset=True)

    for field in ["amount_paise", "type", "date"]:
        if field in updates and updates[field] is None:
            raise HTTPException(400, f"{field} cannot be null")

    new_date = updates.get("date", transaction.date)
    if new_date > date.today():
        raise HTTPException(400, "Transaction date cannot be in the future")

    if "category_id" in updates and updates["category_id"] is not None:
        category = db.query(models.Category).filter_by(
            id=updates["category_id"], user_id=user.id
        ).first()

        if not category:
            raise HTTPException(404, "Category not found")

    for key, value in updates.items():
        setattr(transaction, key, value)

    db.commit()
    db.refresh(transaction)

    return {"message": "Transaction updated", "id": transaction.id}


@app.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    transaction = db.query(models.Transaction).filter_by(
        id=transaction_id, user_id=user.id
    ).first()

    if not transaction:
        raise HTTPException(404, "Transaction not found")

    db.delete(transaction)
    db.commit()

    return {"message": "Transaction deleted"}


@app.post("/categories")
def create_category(
    data: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    name = data.name.strip()

    if not name:
        raise HTTPException(400, "Category name cannot be empty")

    existing = db.query(models.Category).filter(
        models.Category.user_id == user.id,
        func.lower(models.Category.name) == name.lower(),
    ).first()

    if existing:
        raise HTTPException(409, "Category already exists")

    category = models.Category(name=name, user_id=user.id)
    db.add(category)
    db.commit()
    db.refresh(category)

    return {"message": "Category created", "id": category.id}


@app.get("/categories")
def get_categories(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return db.query(models.Category).filter_by(
        user_id=user.id
    ).all()


@app.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    category = db.query(models.Category).filter_by(
        id=category_id, user_id=user.id
    ).first()

    if not category:
        raise HTTPException(404, "Category not found")

    used_by_transaction = db.query(models.Transaction).filter_by(
        user_id=user.id, category_id=category_id
    ).first()

    used_by_budget = db.query(models.Budget).filter_by(
        user_id=user.id, category_id=category_id
    ).first()

    if used_by_transaction or used_by_budget:
        raise HTTPException(
            409,
            "Cannot delete a category used by transactions or budgets",
        )

    db.delete(category)
    db.commit()

    return {"message": "Category deleted"}


@app.post("/budgets")
def create_budget(
    data: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    category = db.query(models.Category).filter_by(
        id=data.category_id, user_id=user.id
    ).first()

    if not category:
        raise HTTPException(404, "Category not found")

    budget = models.Budget(
        **data.model_dump(),
        user_id=user.id,
    )
    db.add(budget)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Budget already exists or is invalid")

    db.refresh(budget)

    return {"message": "Budget created", "id": budget.id}


@app.get("/budgets")
def get_budgets(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return db.query(models.Budget).filter_by(
        user_id=user.id
    ).all()


@app.get("/budgets/{budget_id}/status")
def get_budget_status(
    budget_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    budget = db.query(models.Budget).filter_by(
        id=budget_id, user_id=user.id
    ).first()

    if not budget:
        raise HTTPException(404, "Budget not found")

    spent = db.query(
        func.coalesce(func.sum(models.Transaction.amount_paise), 0)
    ).filter(
        models.Transaction.user_id == user.id,
        models.Transaction.category_id == budget.category_id,
        models.Transaction.type == "expense",
        func.strftime("%Y-%m", models.Transaction.date) == budget.month,
    ).scalar()

    percent = spent * 100 / budget.amount_paise

    if percent >= 100:
        warning = "Budget exceeded or fully used"
    elif percent >= 80:
        warning = "80% budget warning"
    else:
        warning = "Budget within limit"

    return {
        "month": budget.month,
        "budget_paise": budget.amount_paise,
        "spent_paise": spent,
        "percentage_used": round(percent, 2),
        "warning": warning,
    }


@app.get("/reports/monthly")
def monthly_report(
    month: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(400, "Month must be YYYY-MM")

    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == user.id,
        func.strftime("%Y-%m", models.Transaction.date) == month,
    ).all()

    income = sum(
        t.amount_paise for t in transactions if t.type == "income"
    )
    expenses = sum(
        t.amount_paise for t in transactions if t.type == "expense"
    )

    category_names = {
        c.id: c.name
        for c in db.query(models.Category).filter_by(user_id=user.id).all()
    }

    category_totals = {}
    for transaction in transactions:
        if (
            transaction.type == "expense"
            and transaction.category_id is not None
        ):
            category_totals[transaction.category_id] = (
                category_totals.get(transaction.category_id, 0)
                + transaction.amount_paise
            )

    top_expenses = sorted(
        [t for t in transactions if t.type == "expense"],
        key=lambda t: t.amount_paise,
        reverse=True,
    )[:5]

    return {
        "month": month,
        "total_income_paise": income,
        "total_expenses_paise": expenses,
        "savings_paise": income - expenses,
        "spending_by_category": [
            {
                "category_id": category_id,
                "category": category_names.get(category_id, "Unknown"),
                "amount_paise": amount,
            }
            for category_id, amount in category_totals.items()
        ],
        "top_5_expenses": [
            {
                "id": t.id,
                "amount_paise": t.amount_paise,
                "category_id": t.category_id,
                "note": t.note,
                "date": t.date,
            }
            for t in top_expenses
        ],
    }


@app.get("/reports/summary")
def report_summary(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if start_date > end_date:
        raise HTTPException(400, "start_date cannot be after end_date")

    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == user.id,
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
    ).all()

    income = sum(
        t.amount_paise for t in transactions if t.type == "income"
    )
    expenses = sum(
        t.amount_paise for t in transactions if t.type == "expense"
    )

    category_names = {
        c.id: c.name
        for c in db.query(models.Category).filter_by(user_id=user.id).all()
    }

    category_totals = {}
    for transaction in transactions:
        if (
            transaction.type == "expense"
            and transaction.category_id is not None
        ):
            category_totals[transaction.category_id] = (
                category_totals.get(transaction.category_id, 0)
                + transaction.amount_paise
            )

    top_expenses = sorted(
        [t for t in transactions if t.type == "expense"],
        key=lambda t: t.amount_paise,
        reverse=True,
    )[:5]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_income_paise": income,
        "total_expenses_paise": expenses,
        "savings_paise": income - expenses,
        "spending_by_category": [
            {
                "category_id": category_id,
                "category": category_names.get(category_id, "Unknown"),
                "amount_paise": amount,
            }
            for category_id, amount in category_totals.items()
        ],
        "top_5_expenses": [
            {
                "id": t.id,
                "amount_paise": t.amount_paise,
                "category_id": t.category_id,
                "note": t.note,
                "date": t.date,
            }
            for t in top_expenses
        ],
    }


@app.post("/ai/categorize")
def categorize_transaction(
    data: schemas.AITransactionRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    description = data.description.strip()

    if not description:
        raise HTTPException(400, "Description cannot be empty")

    safe_description = sanitize_description(description)

    if not safe_description:
        raise HTTPException(
            400,
            "Description does not contain recognizable transaction details",
        )

    input_hash = hashlib.sha256(
        safe_description.encode("utf-8")
    ).hexdigest()

    cached = db.query(models.AISuggestionCache).filter_by(
        user_id=user.id,
        input_hash=input_hash,
    ).first()

    if cached:
        suggestion = schemas.AITransactionSuggestion.model_validate(
            cached.suggestion
        )

        message = (
            "Please clarify the transaction"
            if suggestion.needs_clarification
            else "Please confirm this suggestion before saving"
        )

        result = {
            "message": message,
            "suggestion": suggestion.model_dump(),
            "cache": "hit",
        }

        if not suggestion.needs_clarification:
            result["saved"] = False

        return result

    try:
        suggestion = suggest_transaction(description)

        if (
            suggestion.amount_paise is not None
            and suggestion.amount_paise <= 0
        ):
            raise ValueError("AI returned an invalid amount")

        if suggestion.type not in (None, "income", "expense"):
            raise ValueError("AI returned an invalid transaction type")

        if not suggestion.needs_clarification and (
            suggestion.amount_paise is None
            or not suggestion.category
            or not suggestion.category.strip()
            or suggestion.type is None
        ):
            raise ValueError("AI returned incomplete transaction details")

    except Exception as exc:
        # Full diagnostic goes to the server terminal, not the API response.
        logger.exception("AI categorization failed")

        error_text = repr(exc).upper()

        if isinstance(exc, RuntimeError) and "API KEY" in str(exc).upper():
            raise HTTPException(503, "AI service is not configured") from exc

        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            raise HTTPException(
                429, "AI rate limit reached. Please try again later."
            ) from exc

        if any(term in error_text for term in (
            "504", "DEADLINE_EXCEEDED", "TIMEOUT"
        )):
            raise HTTPException(
                504, "AI request timed out. Please try again."
            ) from exc

        if any(term in error_text for term in (
            "503", "UNAVAILABLE"
        )):
            raise HTTPException(
                503, "AI service is temporarily unavailable."
            ) from exc

        raise HTTPException(
            502, "AI service returned an invalid response."
        ) from exc

    cache_entry = models.AISuggestionCache(
        user_id=user.id,
        input_hash=input_hash,
        suggestion=suggestion.model_dump(mode="json"),
        needs_clarification=suggestion.needs_clarification,
    )

    db.add(cache_entry)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("AI suggestion cache entry already exists")

    message = (
        "Please clarify the transaction"
        if suggestion.needs_clarification
        else "Please confirm this suggestion before saving"
    )

    result = {
        "message": message,
        "suggestion": suggestion.model_dump(),
        "cache": "miss",
    }

    if not suggestion.needs_clarification:
        result["saved"] = False

    return result
