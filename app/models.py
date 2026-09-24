from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, PositiveInt

TransactionType = Literal["incoming_money", "payment", "transfer", "airtime"]
Status = Literal["completed", "pending", "failed", "reversed"]


class TransactionIn(BaseModel):
    """A transaction added by hand."""
    transaction_type: TransactionType
    amount: PositiveInt  # whole RWF
    party: str = Field(default="", max_length=100)
    date: datetime
    status: Status = "completed"


class TransactionUpdate(BaseModel):
    """Every field is optional: only the ones sent are changed."""
    transaction_type: TransactionType | None = None
    amount: PositiveInt | None = None
    party: str | None = Field(default=None, max_length=100)
    date: datetime | None = None
    status: Status | None = None


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=72)
