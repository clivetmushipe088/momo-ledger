# MoMo SMS Ledger

**Team 2 | ALU | Database Design and Implementation**

| Name | Role |
|------|------|
| Clive Mushipe | Full solo |

## Project Overview

A web app and REST API that turns MTN Mobile Money SMS messages into a ledger you can search, edit and chart. You upload an XML backup of your phone's text messages; the app finds the MoMo messages, reads the type, amount and other party from the message text, and saves them in a database.

* **API:** built with FastAPI. Pydantic validates every request, and the interactive docs are at `/docs`.
* **Accounts:** everyone registers and only sees their own transactions. Passwords are stored as bcrypt hashes, and the login is kept in an HttpOnly cookie.
* **No double counting:** each SMS transaction id (`TxnId`) can be stored only once per user, so uploading the same backup twice adds nothing.
* **Dashboard:** upload a backup, see two charts, and filter, page, add, edit or delete transactions.
* **Tests:** pytest, run by GitHub Actions on every push.

## Repository Structure

```
momo/
├── app/
│   ├── main.py                 # FastAPI app: all routes, serves the dashboard
│   ├── models.py               # request validation (Pydantic)
│   ├── parsing.py              # turns SMS backup XML into transaction records
│   ├── db.py                   # SQL queries (sqlite3)
│   ├── auth.py                 # password hashing, login sessions
│   ├── reports.py              # numbers for the charts
│   └── schema.sql              # the app's SQLite tables and views
├── web/                        # dashboard: index.html, app.js, styles.css
├── data/
│   ├── modified_sms_v2.xml     # MoMo SMS dataset (25 messages)
│   └── sample_backup.xml       # made up phone backup with chats, a duplicate and an unknown format
├── docs/
│   └── api_docs.md             # full API documentation
├── tests/                      # test_parsing.py, test_api.py
├── .github/workflows/tests.yml # runs the tests on every push
└── README.md
```

## Prerequisites

* Python 3.10 or higher
* curl or Postman for testing

## Setup & Running

### 1. Clone the repository

```bash
git clone <repository-url>
cd momo
```

### 2. Install the dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start the server

```bash
uvicorn app.main:app --reload
```

The server starts at <http://localhost:8000>. Open it in a browser for the dashboard, or go to <http://localhost:8000/docs> for the interactive API docs.

The app's database is a single file, `momo.db`, created on first start. Delete it to start again from nothing.

### 4. Run the tests

```bash
pytest
```

## Credentials

There is no built in account. Create your own, either on the login page with **SignUp** or with the API:

| Field | Rule |
|-------|------|
| Username | 3 to 30 letters, numbers or `_` |
| Password | at least 8 characters |

After logging in, the session cookie lasts one day.

## Quick API Test

The login cookie is saved in `cookies.txt` and sent with every request after that.

```bash
# Create an account and log in
curl -H "Content-Type: application/json" -d '{"username":"clive","password":"password123"}' \
  http://localhost:8000/auth/register
curl -c cookies.txt -H "Content-Type: application/json" -d '{"username":"clive","password":"password123"}' \
  http://localhost:8000/auth/login

# Import the dataset
curl -b cookies.txt -F file=@data/modified_sms_v2.xml http://localhost:8000/upload

# List all transactions
curl -b cookies.txt http://localhost:8000/transactions

# Get one transaction
curl -b cookies.txt http://localhost:8000/transactions/1

# Create a transaction
curl -b cookies.txt -X POST http://localhost:8000/transactions \
  -H "Content-Type: application/json" \
  -d '{"transaction_type":"transfer","amount":5000,"party":"Bob","date":"2024-02-01 10:00:00"}'

# Update a transaction
curl -b cookies.txt -X PUT http://localhost:8000/transactions/1 \
  -H "Content-Type: application/json" \
  -d '{"status":"reversed","amount":5500}'

# Delete a transaction
curl -b cookies.txt -X DELETE http://localhost:8000/transactions/1

# Test unauthorized access (should return 401)
curl http://localhost:8000/transactions
```

## API Documentation

See [`docs/api_docs.md`](docs/api_docs.md) for the full endpoint reference, including request and response examples, error codes, how the SMS parsing works, and a security discussion.

## Scrum Board

<!-- TODO: add the Scrum board link -->
[Scrum board](<link>)
