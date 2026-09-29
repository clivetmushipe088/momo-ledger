# MoMo SMS Ledger

**Team 2 | ALU | Building and Securing a REST API + Database Design and Implementation**

| Name | Role |
|------|------|
| Clive Mushipe | Full solo |

## Project Overview

A web app and REST API that turns MTN Mobile Money SMS messages into a ledger you can search, edit and chart. You upload an XML backup of your phone's text messages; the app finds the MoMo messages, reads the type, amount and other party from the message text, and saves them in a database.

* **REST API:** `api/api.py`, built on Python's own `http.server`, serves the SMS records with full CRUD behind HTTP Basic Authentication.
* **Search benchmark:** `dsa/dsa_comparison.py` times linear search against dictionary lookup and explains the difference.
* **Dashboard API:** a second, larger service built with FastAPI, backed by SQLite, which serves the web dashboard.
* **Accounts:** everyone registers and only sees their own transactions. Passwords are stored as bcrypt hashes, and the login is kept in an HttpOnly cookie.
* **No double counting:** each SMS transaction id (`TxnId`) can be stored only once per user, so uploading the same backup twice adds nothing.
* **Dashboard:** upload a backup, see two charts, and filter, page, add, edit or delete transactions.
* **Database design:** a full MySQL schema with an ERD, a data dictionary, CRUD tests and JSON schemas (see [Database Design](#database-design)).
* **Tests:** pytest, run by GitHub Actions on every push.

## Repository Structure

```
momo/
├── api/
│   └── api.py                  # REST API: CRUD + Basic Auth, on http.server
├── dsa/
│   ├── parse_sms.py            # SMS backup XML -> JSON objects
│   └── dsa_comparison.py       # linear search vs dictionary lookup benchmark
├── screenshots/                # curl test evidence and the benchmark
├── app/
│   ├── main.py                 # FastAPI app: all routes, serves the dashboard
│   ├── models.py               # request validation (Pydantic)
│   ├── parsing.py              # turns SMS backup XML into transaction records
│   ├── db.py                   # SQL queries (sqlite3)
│   ├── auth.py                 # password hashing, login sessions
│   ├── reports.py              # numbers for the charts
│   └── schema.sql              # the app's SQLite tables and views
├── web/                        # dashboard: index.html, app.js, styles.css
├── database/
│   ├── database_setup.sql      # full MySQL design: tables, constraints, indexes, sample data
│   ├── crud_tests.sql          # CRUD and constraint tests
│   └── crud_test_results.txt   # output of the tests
├── examples/
│   └── json_schemas.json       # JSON Schemas, examples, SQL to JSON mapping
├── data/
│   ├── modified_sms_v2.xml     # MoMo SMS dataset (25 messages)
│   └── sample_backup.xml       # made up phone backup with chats, a duplicate and an unknown format
├── docs/
│   ├── api_docs.md             # REST API documentation: endpoints, examples, errors
│   ├── api_report.md           # report: security, endpoints, DSA results, Basic Auth
│   ├── api_report.pdf          # the same report as a PDF
│   ├── dashboard_api.md        # the FastAPI dashboard service
│   ├── team_participation.md   # who did what
│   ├── database_design.md      # ERD, design rationale, data dictionary, queries, security
│   ├── database_design.pdf     # the same document as a PDF
│   ├── erd_diagram.png         # the ERD
│   ├── erd.drawio              # ERD source, editable in Draw.io
│   ├── erd.dbml                # the same ERD for dbdiagram.io
│   └── screenshots/            # query results and CRUD test output
├── tests/                      # test_parsing.py, test_api.py, test_plain_api.py
├── .github/workflows/tests.yml # runs the tests on every push
└── README.md
```

## Prerequisites

* Python 3.10 or higher
* MySQL 8.0 or higher (only for the database design scripts; the app itself uses SQLite)
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

### 3. Start the REST API

```bash
python api/api.py
# MoMo SMS API on http://localhost:8080  (25 transactions loaded)
```

It reads `data/modified_sms_v2.xml` at startup and keeps the records in memory, so changes last until the server stops. Pass a port to use a different one: `python api/api.py 9000`.

### 4. Start the dashboard (optional)

```bash
uvicorn app.main:app --reload
```

The dashboard runs at <http://localhost:8000>, with interactive docs at <http://localhost:8000/docs>. Its database is a single file, `momo.db`, created on first start. Delete it to start again from nothing.

### 5. Run the tests

```bash
pytest
```

## Credentials

The REST API uses HTTP Basic Authentication:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `momo2024` |

They are set at the top of `api/api.py`.

The dashboard is separate and has no built in account: create your own with **SignUp**, using 3 to 30 letters, numbers or `_` and a password of at least 8 characters.

## Quick API Test

```bash
# List all transactions
curl -u admin:momo2024 http://localhost:8080/transactions

# Get one transaction
curl -u admin:momo2024 http://localhost:8080/transactions/5

# Create a transaction
curl -u admin:momo2024 -X POST http://localhost:8080/transactions \
  -H "Content-Type: application/json" \
  -d '{"transaction_type":"transfer","amount":5000,"sender":"0789876543","receiver":"0781111111","date":"2024-02-01 10:00:00"}'

# Update a transaction
curl -u admin:momo2024 -X PUT http://localhost:8080/transactions/26 \
  -H "Content-Type: application/json" \
  -d '{"status":"reversed","amount":5500}'

# Delete a transaction
curl -u admin:momo2024 -X DELETE http://localhost:8080/transactions/26

# Test unauthorized access (should return 401)
curl -i http://localhost:8080/transactions
curl -i -u admin:wrongpassword http://localhost:8080/transactions
```

Test evidence is in [`screenshots/`](screenshots/), and the dashboard's own API is covered in [`docs/dashboard_api.md`](docs/dashboard_api.md).

## DSA Benchmark

```bash
python dsa/dsa_comparison.py            # 100,000 repetitions per case
python dsa/dsa_comparison.py 20000      # fewer, for a quicker run
```

Finds a transaction by id with a linear search through the list and with a dictionary lookup, over the 25 records and then over copies grown to 25,000. The dictionary is about 9× faster at 25 records and over 5,000× faster at 25,000, because a linear search is O(n) while a hash lookup is O(1). Full numbers and the reflection are in [`docs/api_report.md`](docs/api_report.md).

## Database Design

```bash
mysql -u root -p < database/database_setup.sql                          # create and fill momo_ledger
mysql -u root -p --table --force momo_ledger < database/crud_tests.sql  # run the CRUD and constraint tests
```

The MySQL design has 8 tables: `users`, `transactions`, `transaction_categories`, `parties`, the junction table `transaction_parties` (transactions ↔ parties is many to many), `system_logs`, `sessions` and `unmatched_sms`. It has foreign keys, CHECK constraints, indexes, a comment on every column, and at least 5 sample rows per table. The test script changes the data, and the setup script puts it back.

The ERD, design rationale, data dictionary, sample queries and security rules are in [`docs/database_design.md`](docs/database_design.md). The JSON model is in [`examples/json_schemas.json`](examples/json_schemas.json). The ERD itself is [`docs/erd_diagram.png`](docs/erd_diagram.png), drawn from [`docs/erd.drawio`](docs/erd.drawio). The design document is also available as a PDF: [`docs/database_design.pdf`](docs/database_design.pdf).

## API Documentation

| Document | What's in it |
|---|---|
| [`docs/api_docs.md`](docs/api_docs.md) | The REST API: authentication, every endpoint with request and response examples, error codes, and why Basic Auth is weak |
| [`docs/api_report.md`](docs/api_report.md) ([PDF](docs/api_report.pdf)) | Report: API security, the endpoints, the DSA results, and the reflection on Basic Auth |
| [`docs/dashboard_api.md`](docs/dashboard_api.md) | The FastAPI dashboard service, its routes and how the SMS parsing works |

## Scrum Board

[MoMo SMS Ledger board](https://github.com/users/clivetmushipe088/projects/2)
