from pathlib import Path

from app.parsing import classify, parse_backup, parse_date

DATA = Path(__file__).resolve().parent.parent / "data"


# ---------- one test per message format ----------

def test_incoming_money():
    result = classify("You have received 5000 RWF from Alice (0781234567). TxnId: TXN001")
    assert result == {"transaction_type": "incoming_money", "amount": 5000,
                      "party": "Alice", "sms_ref": "TXN001"}


def test_payment():
    result = classify("Your payment of 2000 RWF to Kigali Mart was successful. TxnId: TXN002")
    assert result["transaction_type"] == "payment"
    assert result["party"] == "Kigali Mart"


def test_transfer():
    result = classify("You have transferred 10000 RWF to Bob (0782345678). TxnId: TXN003")
    assert result["transaction_type"] == "transfer"
    assert result["amount"] == 10000
    assert result["party"] == "Bob"


def test_airtime():
    result = classify("You have bought airtime worth 500 RWF. TxnId: TXN005")
    assert result["transaction_type"] == "airtime"
    assert result["party"] == ""


# ---------- edge cases ----------

def test_amount_with_commas():
    assert classify("You have received 1,500 RWF from Nadia (0781112233).")["amount"] == 1500


def test_missing_transaction_id():
    assert classify("You have bought airtime worth 500 RWF.")["sms_ref"] is None


def test_unknown_format_returns_none():
    assert classify("You have withdrawn 20,000 RWF via agent Jean.") is None


def test_date_in_milliseconds_is_kigali_time():
    assert parse_date("1706770800000") == "2024-02-01 09:00:00"


def test_date_as_text():
    assert parse_date("2024-01-03 08:12:00") == "2024-01-03 08:12:00"


def test_backup_sorts_messages_into_three_groups():
    xml = """<smses>
      <sms date="1706770800000" body="You have received 1,500 RWF from Nadia (0781112233). TxnId: TXN101" />
      <sms date="1706770800000" body="You have withdrawn 20,000 RWF via agent Jean. TxnId: TXN106" />
      <sms date="not a date" body="You have bought airtime worth 500 RWF. TxnId: TXN107" />
      <sms date="1706770800000" body="Your verification code is 482913" />
    </smses>"""
    records, unmatched, ignored = parse_backup(xml)
    assert [r["sms_ref"] for r in records] == ["TXN101"]
    assert len(unmatched) == 2  # unknown format + unreadable date
    assert ignored == 1         # no "RWF", so not a MoMo message
    assert records[0]["raw_sms"].startswith("You have received")


# ---------- the real data files ----------

def test_whole_dataset_parses():
    records, unmatched, ignored = parse_backup((DATA / "modified_sms_v2.xml").read_bytes())
    assert len(records) == 25
    assert unmatched == []
    assert ignored == 0


def test_sample_backup():
    records, unmatched, ignored = parse_backup((DATA / "sample_backup.xml").read_bytes())
    assert len(records) == 7
    assert len(unmatched) == 1
    assert ignored == 2
