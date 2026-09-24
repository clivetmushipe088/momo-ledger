"""
parsing.py - turns an SMS backup (XML) into MoMo transaction records.

Only the text and date of each message are used, the same as a real phone
backup. Every MoMo message ends up either as a record or in the unmatched
list, so nothing is thrown away without us knowing.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
KIGALI = timezone(timedelta(hours=2))  # Rwanda is UTC+2 all year, no daylight saving

# One rule per message format. Add a new rule when a new format shows up.
AMOUNT = r"(?P<amount>\d[\d,]*) RWF"
RULES = [
    ("incoming_money", re.compile(rf"received {AMOUNT} from (?P<party>[^(]+)")),
    ("payment",        re.compile(rf"payment of {AMOUNT} to (?P<party>.+?) (?:has been|was)")),
    ("transfer",       re.compile(rf"transferred {AMOUNT} to (?P<party>[^(]+)")),
    ("airtime",        re.compile(rf"airtime worth {AMOUNT}")),
]
TXN_ID = re.compile(r"(?:TxId|TxnId|Transaction Id):\s*(?P<ref>\w+)")


def classify(body: str) -> dict | None:
    """Read the type, amount, other party and transaction id from one SMS.

    Returns None when no rule matches.
    """
    for txn_type, pattern in RULES:
        match = pattern.search(body)
        if match:
            ref = TXN_ID.search(body)
            return {
                "transaction_type": txn_type,
                "amount": int(match["amount"].replace(",", "")),
                "party": (match.groupdict().get("party") or "").strip(),
                "sms_ref": ref["ref"] if ref else None,
            }
    return None


def parse_date(value: str) -> str:
    """Phone backups store dates as milliseconds since 1970. Our sample file uses text."""
    value = value.strip()
    if value.isdigit():
        moment = datetime.fromtimestamp(int(value) / 1000, tz=KIGALI)
    else:
        moment = datetime.strptime(value, DATE_FORMAT)
    return moment.strftime(DATE_FORMAT)


def parse_backup(xml_content) -> tuple[list[dict], list[dict], int]:
    """Split a backup into (records, unmatched MoMo messages, number of ignored messages).

    Raises xml.etree.ElementTree.ParseError if the file isn't valid XML.
    """
    root = ET.fromstring(xml_content)
    records, unmatched, ignored = [], [], 0

    for sms in root.iter("sms"):
        body = sms.get("body", "")
        if "RWF" not in body:  # not a MoMo message (chats, OTP codes, ...)
            ignored += 1
            continue

        fields = classify(body)
        try:
            date = parse_date(sms.get("date", ""))
        except ValueError:
            date = None

        if fields is None or date is None or fields["amount"] <= 0:
            unmatched.append({"body": body, "date": date or ""})
        else:
            records.append({**fields, "date": date, "raw_sms": body})

    return records, unmatched, ignored
