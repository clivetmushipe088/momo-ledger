from fastapi.testclient import TestClient

from app import db
from app.main import app
from conftest import log_in, upload

NEW_TXN = {"transaction_type": "transfer", "amount": 5000, "party": "Bob",
           "date": "2024-02-01 10:00:00"}


# ---------- logging in ----------

def test_api_needs_login(client):
    assert client.get("/transactions").status_code == 401
    assert client.post("/transactions", json=NEW_TXN).status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_register_login_logout(client):
    account = {"username": "alice", "password": "password123"}
    assert client.post("/auth/register", json=account).status_code == 201
    assert client.post("/auth/register", json=account).status_code == 400  # name taken

    wrong = {"username": "alice", "password": "wrongpassword"}
    assert client.post("/auth/login", json=wrong).status_code == 401

    assert client.post("/auth/login", json=account).status_code == 200
    assert client.get("/auth/me").json() == {"username": "alice"}

    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401


def test_short_password_is_rejected(client):
    response = client.post("/auth/register", json={"username": "alice", "password": "short"})
    assert response.status_code == 422


def test_password_is_not_stored_as_plain_text(user):
    assert db.find_user("alice")["password_hash"] != "password123"


def test_old_logins_stop_working(user):
    with db.connect() as conn:
        conn.execute("UPDATE sessions SET created_at = datetime('now', '-2 days')")
    assert user.get("/auth/me").status_code == 401


# ---------- uploading a backup ----------

def test_upload_skips_duplicates(user):
    assert upload(user, "modified_sms_v2.xml").json() == {
        "imported": 25, "duplicates": 0, "unmatched": 0, "ignored": 0}
    assert upload(user, "modified_sms_v2.xml").json()["duplicates"] == 25

    # sample_backup.xml repeats TXN002, has 1 unknown MoMo message and 2 chats
    assert upload(user, "sample_backup.xml").json() == {
        "imported": 6, "duplicates": 1, "unmatched": 1, "ignored": 2}
    assert len(user.get("/unmatched").json()) == 1
    assert user.get("/transactions").json()["count"] == 31


def test_upload_rejects_a_file_that_is_not_xml(user):
    response = user.post("/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400


# ---------- listing ----------

def test_filter_and_pages(user):
    upload(user, "modified_sms_v2.xml")

    page = user.get("/transactions?type=payment&limit=3&page=2").json()
    assert page["count"] == 8
    assert page["pages"] == 3
    assert len(page["transactions"]) == 3
    assert all(t["transaction_type"] == "payment" for t in page["transactions"])

    amounts = [t["amount"] for t in
               user.get("/transactions?min_amount=10000&max_amount=25000").json()["transactions"]]
    assert amounts and all(10000 <= a <= 25000 for a in amounts)

    assert user.get("/transactions?type=gift").status_code == 422


# ---------- create, read, update, delete ----------

def test_bad_transactions_are_rejected(user):
    assert user.post("/transactions", json={**NEW_TXN, "amount": -500}).status_code == 422
    assert user.post("/transactions", json={**NEW_TXN, "date": "not a date"}).status_code == 422
    assert user.post("/transactions", json={**NEW_TXN, "transaction_type": "gift"}).status_code == 422
    assert user.post("/transactions", json={**NEW_TXN, "status": "reviewed"}).status_code == 422


def test_create_read_update_delete(user):
    created = user.post("/transactions", json=NEW_TXN)
    assert created.status_code == 201
    txn = created.json()
    assert txn["amount"] == 5000
    assert txn["date"] == "2024-02-01 10:00:00"

    assert user.get(f"/transactions/{txn['id']}").json() == txn

    updated = user.put(f"/transactions/{txn['id']}", json={"amount": 5500, "status": "reversed"}).json()
    assert updated["amount"] == 5500
    assert updated["status"] == "reversed"
    assert updated["party"] == "Bob"  # fields not sent stay the same

    assert user.put(f"/transactions/{txn['id']}", json={"amount": 0}).status_code == 422

    assert user.delete(f"/transactions/{txn['id']}").status_code == 200
    assert user.get(f"/transactions/{txn['id']}").status_code == 404
    assert user.delete(f"/transactions/{txn['id']}").status_code == 404
    assert user.put("/transactions/999", json={"amount": 10}).status_code == 404


def test_reports(user):
    assert user.get("/reports/monthly-flow").json() == []  # nothing uploaded yet
    upload(user, "modified_sms_v2.xml")

    months = user.get("/reports/monthly-flow").json()
    assert months == [{"month": "2024-01", "money_in": 158000, "money_out": 89200}]

    merchants = user.get("/reports/merchants").json()
    assert len(merchants) == 8
    assert merchants[0] == {"merchant": "School Fees", "payments": 1, "total": 9000}


def test_users_only_see_their_own_data(user):
    upload(user, "modified_sms_v2.xml")
    alice_txn = user.get("/transactions?limit=1").json()["transactions"][0]

    bob = TestClient(app)  # a second browser with its own cookies, same database
    log_in(bob, "bob")
    assert bob.get("/transactions").json()["count"] == 0
    assert bob.get(f"/transactions/{alice_txn['id']}").status_code == 404
    assert bob.delete(f"/transactions/{alice_txn['id']}").status_code == 404
    assert user.get(f"/transactions/{alice_txn['id']}").status_code == 200
