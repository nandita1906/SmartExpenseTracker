from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TransactionCreate(BaseModel):
    amount_paise: int = Field(gt=0)
    type: Literal["income", "expense"]
    date: Date
    note: str = ""
    payment_method: str = "other"
    category_id: int | None = None


class TransactionUpdate(BaseModel):
    amount_paise: int | None = Field(default=None, gt=0)
    type: Literal["income", "expense"] | None = None
    date: Date | None = None
    note: str | None = None
    payment_method: str | None = None
    category_id: int | None = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class BudgetCreate(BaseModel):
    category_id: int
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount_paise: int = Field(gt=0)


class AITransactionSuggestion(BaseModel):
    amount_paise: int | None
    category: str | None
    type: Literal["income", "expense"] | None
    needs_clarification: bool


class AITransactionRequest(BaseModel):
    description: str = Field(min_length=1, max_length=300)
