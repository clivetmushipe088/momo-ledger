"""Tests for the REST API in api/api.py.

The server is started on a free port in the background, and the tests send
it real HTTP requests, the same way curl does.
"""

import base64
import json
import threading
from http.client import HTTPConnection
from http.server import HTTPServer

import pytest

from api import api

GOOD = base64.b64encode(b"admin:momo2024").decode()
BAD = base64.b64encode(b"admin:wrongpassword").decode()


@pytest.fixture(scope="module")
def address():
    server = HTTPServer(("127.0.0.1", 0), api.MoMoHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address
    server.shutdown()


def call(address, method, path, body=None, auth=GOOD):
    """Send one request and return (status code, response body)."""
    connection = HTTPConnection(address[0], address[1], timeout=5)
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = "Basic " + auth
    connection.request(method, path, body=json.dumps(body) if body else None, headers=headers)
    response = connection.getresponse()
    text = response.read().decode()
    connection.close()
    return response.status, json.loads(text) if text else None


def test_no_password_gives_401(address):
    status, data = call(address, "GET", "/transactions", auth=None)
    assert status == 401
    assert "credentials" in data["error"]


def test_wrong_password_gives_401(address):
    status, _ = call(address, "GET", "/transactions", auth=BAD)
    assert status == 401


def test_list_all_transactions(address):
    status, data = call(address, "GET", "/transactions")
    assert status == 200
    assert data["count"] == len(data["transactions"])
    assert data["count"] >= 25
    first = data["transactions"][0]
    for field in ["id", "transaction_type", "amount", "sender", "receiver", "date", "status"]:
        assert field in first


def test_get_one_transaction(address):
    status, data = call(address, "GET", "/transactions/5")
    assert status == 200
    assert data["id"] == 5


def test_missing_transaction_gives_404(address):
    status, data = call(address, "GET", "/transactions/99999")
    assert status == 404
    assert "No transaction" in data["error"]


def test_create_change_and_delete(address):
    new = {"transaction_type": "transfer", "amount": 5000, "sender": "0789876543",
           "receiver": "0781111111", "date": "2024-02-01 10:00:00"}
    status, created = call(address, "POST", "/transactions", new)
    assert status == 201
    assert created["amount"] == 5000
    txn_id = created["id"]

    status, changed = call(address, "PUT", f"/transactions/{txn_id}", {"status": "reversed", "amount": 5500})
    assert status == 200
    assert changed["status"] == "reversed"
    assert changed["amount"] == 5500

    status, deleted = call(address, "DELETE", f"/transactions/{txn_id}")
    assert status == 200
    assert deleted["deleted"] == txn_id

    status, _ = call(address, "GET", f"/transactions/{txn_id}")
    assert status == 404


def test_negative_amount_is_refused(address):
    status, data = call(address, "POST", "/transactions", {"transaction_type": "transfer", "amount": -5})
    assert status == 400
    assert "amount" in data["error"]


def test_unknown_type_is_refused(address):
    status, data = call(address, "POST", "/transactions", {"transaction_type": "nonsense", "amount": 10})
    assert status == 400
    assert "transaction_type" in data["error"]


def test_missing_field_is_refused(address):
    status, data = call(address, "POST", "/transactions", {"amount": 10})
    assert status == 400
    assert "required" in data["error"]


def test_unknown_path_gives_404(address):
    status, _ = call(address, "GET", "/nope")
    assert status == 404
