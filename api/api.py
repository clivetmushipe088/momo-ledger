"""MoMo SMS REST API using Python's built-in http.server.

Run it with:
    python api/api.py

Then open http://localhost:8080/transactions with the username and
password below. The transactions are read from the XML file when the
server starts and kept in memory, so any changes are lost when it stops.
"""

import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsa.parse_sms import index_by_id, load_transactions

USERNAME = "admin"
PASSWORD = "momo2024"

TYPES = ["incoming_money", "payment", "transfer", "airtime"]
STATUSES = ["completed", "pending", "failed", "reversed"]

# transactions are kept in a dictionary {id: transaction} so that looking
# one up by id is fast (see dsa/dsa_comparison.py)
transactions = index_by_id(load_transactions())
next_id = max(transactions) + 1


def check(data, is_new):
    """Check a request body and return an error message, or None if it is fine."""
    if not isinstance(data, dict):
        return "The body must be a JSON object."
    if is_new:
        for field in ["transaction_type", "amount"]:
            if field not in data:
                return f"'{field}' is required."
    if "transaction_type" in data and data["transaction_type"] not in TYPES:
        return "'transaction_type' must be one of: " + ", ".join(TYPES)
    if "amount" in data and (not isinstance(data["amount"], int) or data["amount"] <= 0):
        return "'amount' must be a whole number greater than 0."
    if "status" in data and data["status"] not in STATUSES:
        return "'status' must be one of: " + ", ".join(STATUSES)
    return None


class MoMoHandler(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_message(self, status, message):
        self.send_json(status, {"error": message})

    def is_logged_in(self):
        """Check the Basic Auth header. Sends 401 and returns False if it is wrong."""
        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                details = base64.b64decode(header[6:]).decode()
                username, _, password = details.partition(":")
                if username == USERNAME and password == PASSWORD:
                    return True
            except Exception:
                pass

        body = json.dumps({"error": "Valid credentials are required."}).encode()
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="MoMo SMS API"')
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def get_id(self):
        """Return the id from the path, or None for /transactions itself."""
        parts = self.path.strip("/").split("/")
        if parts[0] != "transactions" or len(parts) > 2:
            return "bad path"
        return parts[1] if len(parts) == 2 else None

    def find(self, txn_id):
        """Find a transaction, or send 404 and return None."""
        if not txn_id.isdigit() or int(txn_id) not in transactions:
            self.send_error_message(404, f"No transaction with id {txn_id}.")
            return None
        return transactions[int(txn_id)]

    def read_body(self):
        """Read and parse the JSON body. Returns (data, error message)."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None, "A JSON body is required."
        try:
            return json.loads(self.rfile.read(length).decode()), None
        except ValueError:
            return None, "The body is not valid JSON."

    def do_GET(self):
        if not self.is_logged_in():
            return
        txn_id = self.get_id()
        if txn_id == "bad path":
            return self.send_error_message(404, f"Unknown path: {self.path}")

        if txn_id is None:
            records = sorted(transactions.values(), key=lambda t: t["id"])
            self.send_json(200, {"count": len(records), "transactions": records})
        else:
            found = self.find(txn_id)
            if found:
                self.send_json(200, found)

    def do_POST(self):
        global next_id
        if not self.is_logged_in():
            return
        if self.get_id() is not None:
            return self.send_error_message(404, f"Cannot POST to {self.path}")

        data, error = self.read_body()
        if error:
            return self.send_error_message(400, error)
        error = check(data, is_new=True)
        if error:
            return self.send_error_message(400, error)

        transaction = {
            "id": next_id,
            "transaction_type": data["transaction_type"],
            "amount": data["amount"],
            "sender": data.get("sender", ""),
            "receiver": data.get("receiver", ""),
            "date": data.get("date", ""),
            "currency": data.get("currency", "RWF"),
            "status": data.get("status", "completed"),
            "body": data.get("body", ""),
        }
        transactions[next_id] = transaction
        next_id = next_id + 1
        self.send_json(201, transaction)

    def do_PUT(self):
        if not self.is_logged_in():
            return
        txn_id = self.get_id()
        if txn_id is None or txn_id == "bad path":
            return self.send_error_message(404, f"Cannot PUT to {self.path}")

        transaction = self.find(txn_id)
        if not transaction:
            return
        data, error = self.read_body()
        if error:
            return self.send_error_message(400, error)
        error = check(data, is_new=False)
        if error:
            return self.send_error_message(400, error)

        for field in ["transaction_type", "amount", "sender", "receiver", "date",
                      "currency", "status", "body"]:
            if field in data:
                transaction[field] = data[field]
        self.send_json(200, transaction)

    def do_DELETE(self):
        if not self.is_logged_in():
            return
        txn_id = self.get_id()
        if txn_id is None or txn_id == "bad path":
            return self.send_error_message(404, f"Cannot DELETE {self.path}")

        transaction = self.find(txn_id)
        if not transaction:
            return
        del transactions[transaction["id"]]
        self.send_json(200, {"deleted": transaction["id"], "remaining": len(transactions)})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"MoMo SMS API on http://localhost:{port} ({len(transactions)} transactions loaded)", flush=True)
    print(f"Username: {USERNAME}   Password: {PASSWORD}", flush=True)
    HTTPServer(("", port), MoMoHandler).serve_forever()
