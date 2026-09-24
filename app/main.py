"""
main.py - the MoMo Ledger web app.

Run it from the project folder with:

    uvicorn app.main:app --reload

then open http://localhost:8000 for the dashboard, or http://localhost:8000/docs
to try the API.
"""

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from xml.etree.ElementTree import ParseError

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, db, reports
from .models import Status, TransactionIn, TransactionType, TransactionUpdate, UserIn
from .parsing import parse_backup

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB is plenty for a year of SMS


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()  # create the tables on first run
    yield


app = FastAPI(title="MoMo Ledger", lifespan=lifespan)


@app.exception_handler(sqlite3.IntegrityError)
def database_rejected(request: Request, exc: sqlite3.IntegrityError):
    # Pydantic should catch bad data first. This is the backup: the CHECK
    # constraints in schema.sql refuse anything that slips through.
    return JSONResponse(status_code=400, content={"detail": "The database rejected this data."})


# ---------- accounts ----------

@app.post("/auth/register", status_code=201)
def register(user: UserIn):
    if not db.create_user(user.username, auth.hash_password(user.password)):
        raise HTTPException(status_code=400, detail="That username is already taken.")
    return {"message": "Account created. You can log in now."}


@app.post("/auth/login")
def login(user: UserIn, response: Response):
    row = db.find_user(user.username)
    if row is None or not auth.check_password(user.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    token = auth.start_session(row["id"])
    response.set_cookie(
        auth.COOKIE_NAME, token,
        max_age=24 * 60 * 60,
        httponly=True,   # JavaScript can't read it
        samesite="lax",  # not sent with requests started by other websites
        secure=False,    # change to True once the site runs over HTTPS
    )
    return {"username": row["username"]}


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        db.delete_session(token)
    response.delete_cookie(auth.COOKIE_NAME)
    return {"message": "Logged out."}


@app.get("/auth/me")
def me(user=Depends(auth.current_user)):
    return {"username": user["username"]}


# ---------- importing a backup ----------

@app.post("/upload")
def upload(file: UploadFile, user=Depends(auth.current_user)):
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="That file is too big (the limit is 5 MB).")
    try:
        records, unmatched, ignored = parse_backup(content)
    except ParseError:
        raise HTTPException(status_code=400, detail="That file isn't a valid XML backup.")
    result = db.save_import(user["id"], records, unmatched)
    return {**result, "unmatched": len(unmatched), "ignored": ignored}


@app.get("/unmatched")
def unmatched(user=Depends(auth.current_user)):
    return db.list_unmatched(user["id"])


# ---------- transactions ----------

@app.get("/transactions")
def list_transactions(
    txn_type: TransactionType | None = Query(None, alias="type"),
    status: Status | None = None,
    min_amount: int | None = Query(None, ge=0),
    max_amount: int | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(auth.current_user),
):
    return db.list_transactions(user["id"], txn_type, status, min_amount, max_amount, page, limit)


@app.post("/transactions", status_code=201)
def create_transaction(txn: TransactionIn, user=Depends(auth.current_user)):
    return db.create_transaction(user["id"], txn.model_dump())


@app.get("/transactions/{txn_id}")
def get_transaction(txn_id: int, user=Depends(auth.current_user)):
    txn = db.get_transaction(user["id"], txn_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return txn


@app.put("/transactions/{txn_id}")
def update_transaction(txn_id: int, changes: TransactionUpdate, user=Depends(auth.current_user)):
    txn = db.update_transaction(user["id"], txn_id, changes.model_dump(exclude_none=True))
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return txn


@app.delete("/transactions/{txn_id}")
def delete_transaction(txn_id: int, user=Depends(auth.current_user)):
    if not db.delete_transaction(user["id"], txn_id):
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return {"message": "Transaction deleted."}


# ---------- reports for the charts ----------

@app.get("/reports/monthly-flow")
def monthly_flow(user=Depends(auth.current_user)):
    return reports.monthly_flow(user["id"])


@app.get("/reports/merchants")
def merchants(user=Depends(auth.current_user)):
    return reports.top_merchants(user["id"])


# The dashboard. Mounted last so it doesn't hide the API routes above.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
