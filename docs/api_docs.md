# MoMo SMS API: Documentation

A REST API over the MoMo SMS records, written with Python's built-in `http.server` and protected with HTTP Basic Authentication. When the server starts it reads `data/modified_sms_v2.xml`, keeps the 25 transactions in memory, and serves them as JSON.

Start it with:

```bash
python api/api.py
# MoMo SMS API on http://localhost:8080 (25 transactions loaded)
```

Base URL: `http://localhost:8080`

The dashboard has its own separate API, documented in [`dashboard_api.md`](dashboard_api.md).

---

## Authentication

Every endpoint needs a username and password.

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `momo2024` |

With curl, `-u admin:momo2024` sends them. Curl builds the header itself:

```
Authorization: Basic YWRtaW46bW9tbzIwMjQ=
```

That is `admin:momo2024` in base64, which anyone can decode. See "Why Basic Auth is weak" at the end.

A request with no credentials, or the wrong ones, gets `401 Unauthorized`:

```bash
curl -i http://localhost:8080/transactions
```

```
HTTP/1.0 401 Unauthorized
WWW-Authenticate: Basic realm="MoMo SMS API"
Content-Type: application/json

{"error": "Valid credentials are required."}
```

The `WWW-Authenticate` header is what makes a browser show a login box.

---

## Endpoints

| Method | Path | What it does | Success |
|--------|------|--------------|---------|
| GET | `/transactions` | List all transactions | 200 |
| GET | `/transactions/{id}` | One transaction | 200 |
| POST | `/transactions` | Add a transaction | 201 |
| PUT | `/transactions/{id}` | Change a transaction | 200 |
| DELETE | `/transactions/{id}` | Delete a transaction | 200 |

### The fields of a transaction

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Given by the server |
| `transaction_type` | string | `incoming_money`, `payment`, `transfer` or `airtime` |
| `amount` | integer | Whole RWF, greater than 0 |
| `sender` | string | Phone number of the sender |
| `receiver` | string | Phone number, or a MoMoPay code such as `MTN:MoMoPay:Kigali_Mart` |
| `date` | string | `YYYY-MM-DD HH:MM:SS` |
| `currency` | string | `RWF` |
| `status` | string | `completed`, `pending`, `failed` or `reversed` |
| `body` | string | The original SMS text |

`transaction_type` and `amount` are needed when adding one. The rest have defaults.

---

## Requests and responses

The responses below are real output from the running server.

### GET /transactions

```bash
curl -u admin:momo2024 http://localhost:8080/transactions
```

```json
{
  "count": 25,
  "transactions": [
    {
      "id": 1,
      "transaction_type": "incoming_money",
      "amount": 5000,
      "sender": "0781234567",
      "receiver": "0789876543",
      "date": "2024-01-03 08:12:00",
      "currency": "RWF",
      "status": "completed",
      "body": "You have received 5000 RWF from Alice (0781234567). Your new balance is 15000 RWF. TxnId: TXN001"
    }
  ]
}
```

### GET /transactions/{id}

```bash
curl -u admin:momo2024 http://localhost:8080/transactions/5
```

```json
{
  "id": 5,
  "transaction_type": "airtime",
  "amount": 500,
  "sender": "0789876543",
  "receiver": "MTN:Airtime",
  "date": "2024-01-07 11:00:00",
  "currency": "RWF",
  "status": "completed",
  "body": "You have bought airtime worth 500 RWF. TxnId: TXN005"
}
```

### POST /transactions

```bash
curl -u admin:momo2024 -X POST http://localhost:8080/transactions \
  -H "Content-Type: application/json" \
  -d '{"transaction_type":"transfer","amount":5000,"sender":"0789876543","receiver":"0781111111","date":"2024-02-01 10:00:00"}'
```

```json
{
  "id": 26,
  "transaction_type": "transfer",
  "amount": 5000,
  "sender": "0789876543",
  "receiver": "0781111111",
  "date": "2024-02-01 10:00:00",
  "currency": "RWF",
  "status": "completed",
  "body": ""
}
```

### PUT /transactions/{id}

Only the fields you send are changed.

```bash
curl -u admin:momo2024 -X PUT http://localhost:8080/transactions/26 \
  -H "Content-Type: application/json" \
  -d '{"status":"reversed","amount":5500}'
```

```json
{
  "id": 26,
  "transaction_type": "transfer",
  "amount": 5500,
  "sender": "0789876543",
  "receiver": "0781111111",
  "date": "2024-02-01 10:00:00",
  "currency": "RWF",
  "status": "reversed",
  "body": ""
}
```

### DELETE /transactions/{id}

```bash
curl -u admin:momo2024 -X DELETE http://localhost:8080/transactions/26
```

```json
{
  "deleted": 26,
  "remaining": 25
}
```

---

## Error codes

| Status | When it happens | Example |
|---|---|---|
| 400 | The body is missing, is not valid JSON, or a value is wrong | `{"error": "'amount' must be a whole number greater than 0."}` |
| 401 | No credentials, or the wrong ones | `{"error": "Valid credentials are required."}` |
| 404 | No transaction with that id, or a path that does not exist | `{"error": "No transaction with id 999."}` |

For example, an amount that is not allowed:

```bash
curl -u admin:momo2024 -X POST http://localhost:8080/transactions \
  -H "Content-Type: application/json" \
  -d '{"transaction_type":"transfer","amount":-5}'
```

```json
{
  "error": "'amount' must be a whole number greater than 0."
}
```

---

## Why Basic Auth is weak

1. **The password is sent with every request.** Base64 is only an encoding, not encryption: `YWRtaW46bW9tbzIwMjQ=` turns back into `admin:momo2024` with one command. Over plain HTTP, anyone on the same network can read it.
2. **It never expires.** The password keeps working until somebody changes it, and there is no way to log one client out.
3. **There is one account for everything.** Whoever logs in can read, add, change and delete. A client that only needs to read the transactions still gets the power to delete them.
4. **The password is in the code.** `api/api.py` has `admin` and `momo2024` written in it, so anyone reading the repository knows them.
5. **Nothing stops guessing.** Passwords can be tried over and over, as fast as the server will answer.

### Better options

- **JWT (JSON Web Tokens).** The client logs in once and gets back a signed token that expires after a while, and sends that token instead of the password. If the token is stolen it stops working on its own, and it can hold the user's role so the server knows what they are allowed to do.
- **OAuth 2.0.** The password never reaches this API at all. Another server handles the login and gives out tokens that only allow certain things, so one app can be allowed to read transactions but not delete them, and access can be taken back without changing the password.
- **HTTPS in all cases.** Without it, tokens are read in transit just as easily as a password, so encryption is needed before any of the above helps.

This API runs on plain HTTP and keeps everything in memory, which is fine for coursework and a demo, but not for real customer data.
