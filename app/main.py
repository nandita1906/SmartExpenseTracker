import re
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database import Base, engine, get_db
from app import models, schemas
from app.auth import hash_password, verify_password, create_token, get_current_user
from datetime import date

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Smart Expense Tracker API")


@app.get("/")
def home():
    return {"message": "Smart Expense Tracker API is running!"}


@app.post("/register")
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    email = data.email.lower()

    if db.query(models.User).filter_by(email=email).first():
        raise HTTPException(400, "Email already registered")

    user = models.User(
        email=email,
        hashed_password=hash_password(data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "Registration successful", "user_id": user.id}


@app.post("/login", response_model=schemas.Token)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    email = data.email.lower()
    user = db.query(models.User).filter_by(email=email).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")

    return {
        "access_token": create_token(user.id),
        "token_type": "bearer"
    }

@app.get("/me")
def get_profile(user=Depends(get_current_user)):
    return {"id": user.id, "email": user.email}

@app.post("/transactions")
def create_transaction(
    data: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if data.category_id is not None:
        category = db.query(models.Category).filter_by(
            id=data.category_id, user_id=user.id
        ).first()
        if not category:
            raise HTTPException(404, "Category not found")

    transaction = models.Transaction(
        **data.model_dump(),
        user_id=user.id
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return {"message": "Transaction created", "id": transaction.id}


@app.get("/transactions")
def get_transactions(
    type: str | None = None,
    search: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    sort_by: str = "date",
    order: str = "desc",
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    query = db.query(models.Transaction).filter_by(
        user_id=user.id
    )

    if type:
        if type not in ["income", "expense"]:
            raise HTTPException(400, "Invalid transaction type")
        query = query.filter(models.Transaction.type == type)

    
    if search:
        query = query.filter(
            models.Transaction.note.ilike(f"%{search}%")
        )

    if start_date:
        try:
            start = date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(400, "Invalid start_date. Use YYYY-MM-DD")
        query = query.filter(models.Transaction.date >= start)

    if end_date:
        try:
            end = date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(400, "Invalid end_date. Use YYYY-MM-DD")
        query = query.filter(models.Transaction.date <= end)

    if sort_by not in ["date", "amount_paise"]:
        raise HTTPException(400, "Invalid sort field")

    if order not in ["asc", "desc"]:
        raise HTTPException(400, "Order must be asc or desc")

    column = getattr(models.Transaction, sort_by)
    query = query.order_by(
        column.asc() if order == "asc" else column.desc()
    )

    if skip < 0 or limit < 1 or limit > 100:
        raise HTTPException(400, "Invalid pagination values")

    return query.offset(skip).limit(limit).all()



@app.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    transaction = db.query(models.Transaction).filter_by(
        id=transaction_id, user_id=user.id
    ).first()

    if not transaction:
        raise HTTPException(404, "Transaction not found")

    db.delete(transaction)
    db.commit()

    return {"message": "Transaction deleted"}



@app.patch("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: int,
    data: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
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



@app.post("/categories")
def create_category(
    data: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    name = data.name.strip()

    if not name:
        raise HTTPException(400, "Category name cannot be empty")

    existing = db.query(models.Category).filter(
        models.Category.user_id == user.id,
        func.lower(models.Category.name) == name.lower()
    ).first()

    if existing:
        raise HTTPException(409, "Category already exists")

    category = models.Category(
        name=name,
        user_id=user.id
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return {"message": "Category created", "id": category.id}



@app.get("/categories")
def get_categories(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return db.query(models.Category).filter_by(
        user_id=user.id
    ).all()


@app.post("/budgets")
def create_budget(
    data: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    category = db.query(models.Category).filter_by(
        id=data.category_id, user_id=user.id
    ).first()

    if not category:
        raise HTTPException(404, "Category not found")

    budget = models.Budget(
        **data.model_dump(),
        user_id=user.id
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
    user=Depends(get_current_user)
):
    return db.query(models.Budget).filter_by(
        user_id=user.id
    ).all()


@app.get("/budgets/{budget_id}/status")
def get_budget_status(
    budget_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    budget = db.query(models.Budget).filter_by(
        id=budget_id,
        user_id=user.id
    ).first()

    if not budget:
        raise HTTPException(404, "Budget not found")

    from sqlalchemy import func

    spent = db.query(
        func.coalesce(func.sum(models.Transaction.amount_paise), 0)
    ).filter(
        models.Transaction.user_id == user.id,
        models.Transaction.category_id == budget.category_id,
        models.Transaction.type == "expense",
        models.Transaction.date.like(f"{budget.month}-%")
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
        "warning": warning
    }


@app.get("/reports/monthly")
def monthly_report(
    month: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(400, "Month must be YYYY-MM")

    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == user.id,
        func.strftime("%Y-%m", models.Transaction.date) == month
    ).all()

    income = sum(
        t.amount_paise for t in transactions if t.type == "income"
    )
    expenses = sum(
        t.amount_paise for t in transactions if t.type == "expense"
    )

    top_expenses = sorted(
        [t for t in transactions if t.type == "expense"],
        key=lambda t: t.amount_paise,
        reverse=True
    )[:5]

    return {
        "month": month,
        "total_income_paise": income,
        "total_expenses_paise": expenses,
        "savings_paise": income - expenses,
        "top_5_expenses": [
            {
                "id": t.id,
                "amount_paise": t.amount_paise,
                "note": t.note,
                "date": t.date
            }
            for t in top_expenses
        ]
    }
