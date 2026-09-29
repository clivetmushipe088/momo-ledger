"""Read the MoMo SMS backup (XML) and turn it into a list of dictionaries.

Used by the API (api/api.py) and by the search comparison
(dsa/dsa_comparison.py), so both work with the same records.
"""

import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(os.path.dirname(HERE), "data", "modified_sms_v2.xml")


def load_transactions(path=DATA_FILE):
    """Return one dictionary per <sms> element in the file."""
    root = ET.parse(path).getroot()
    records = []

    for number, sms in enumerate(root.iter("sms"), start=1):
        records.append({
            "id": int(sms.get("id", number)),
            "transaction_type": sms.get("transaction_type", ""),
            "amount": int(sms.get("amount", 0)),
            "sender": sms.get("sender", ""),
            "receiver": sms.get("receiver", ""),
            "date": sms.get("date", ""),
            "currency": sms.get("currency", "RWF"),
            "status": sms.get("status", "completed"),
            "body": sms.get("body", ""),
        })
    return records


def index_by_id(records):
    """Same records, but in a dictionary {id: record}."""
    return {record["id"]: record for record in records}


if __name__ == "__main__":
    import json

    transactions = load_transactions()
    print(f"{len(transactions)} transactions parsed\n")
    print(json.dumps(transactions[:2], indent=2))
