-- MoMo Ledger database (SQLite).
-- db.init_db() runs this file every time the app starts, so everything
-- uses IF NOT EXISTS and running it twice is harmless.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,             -- bcrypt hash, never the password itself
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One row per logged-in browser. The token is also kept in the browser's cookie.
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id               INTEGER PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sms_ref          TEXT,                   -- TxnId from the SMS, NULL for manual entries
    transaction_type TEXT NOT NULL
                     CHECK (transaction_type IN ('incoming_money', 'payment', 'transfer', 'airtime')),
    amount           INTEGER NOT NULL CHECK (amount > 0),   -- whole RWF, no cents
    party            TEXT NOT NULL DEFAULT '',              -- the other person or merchant
    date             TEXT NOT NULL CHECK (date LIKE '____-__-__ __:__:__'),
    status           TEXT NOT NULL DEFAULT 'completed'
                     CHECK (status IN ('completed', 'pending', 'failed', 'reversed')),
    raw_sms          TEXT,                   -- original message, so it can be parsed again
    UNIQUE (user_id, sms_ref)                -- the same SMS can't be imported twice
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions (user_id, date);

-- MoMo messages that no parsing rule understood, kept so a rule can be fixed later.
CREATE TABLE IF NOT EXISTS unmatched_sms (
    id      INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body    TEXT NOT NULL,
    date    TEXT NOT NULL DEFAULT '',
    UNIQUE (user_id, body, date)
);

-- Money in vs money out per month. Only incoming_money adds to the wallet.
CREATE VIEW IF NOT EXISTS v_monthly_flow AS
SELECT user_id,
       substr(date, 1, 7) AS month,
       SUM(CASE WHEN transaction_type = 'incoming_money' THEN amount ELSE 0 END) AS money_in,
       SUM(CASE WHEN transaction_type <> 'incoming_money' THEN amount ELSE 0 END) AS money_out
FROM transactions
WHERE status = 'completed'
GROUP BY user_id, month;

-- Total spent at each merchant.
CREATE VIEW IF NOT EXISTS v_merchant_spend AS
SELECT user_id,
       party AS merchant,
       COUNT(*) AS payments,
       SUM(amount) AS total
FROM transactions
WHERE transaction_type = 'payment' AND status = 'completed'
GROUP BY user_id, party;
