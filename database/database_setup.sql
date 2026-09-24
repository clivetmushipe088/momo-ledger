

DROP DATABASE IF EXISTS momo_ledger;
CREATE DATABASE momo_ledger
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE momo_ledger;


-- 1. users: people who own a MoMo wallet and log in to the ledger
CREATE TABLE users (
    user_id       INT UNSIGNED  NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    username      VARCHAR(30)   NOT NULL COMMENT 'Login name: 3-30 letters, numbers or _',
    full_name     VARCHAR(100)  NOT NULL COMMENT 'Name shown on the dashboard',
    phone_number  VARCHAR(10)   NOT NULL COMMENT 'The MTN number the SMS backups come from (07XXXXXXXX)',
    password_hash CHAR(60)      NOT NULL COMMENT 'bcrypt hash; the password itself is never stored',
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'When the account was created',
    CONSTRAINT pk_users PRIMARY KEY (user_id),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_phone UNIQUE (phone_number),
    CONSTRAINT chk_users_username CHECK (REGEXP_LIKE(username, '^[A-Za-z0-9_]{3,30}$')),
    CONSTRAINT chk_users_phone CHECK (REGEXP_LIKE(phone_number, '^07[2389][0-9]{7}$')),
    CONSTRAINT chk_users_hash CHECK (password_hash LIKE '$2_$__$%' AND CHAR_LENGTH(password_hash) = 60)
) ENGINE = InnoDB COMMENT = 'Wallet owners who use the ledger';


-- 2. transaction_categories: lookup table for the kind of transaction
CREATE TABLE transaction_categories (
    category_id   TINYINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    category_code VARCHAR(30)      NOT NULL COMMENT 'Stable code used by the parser and the API, e.g. payment',
    category_name VARCHAR(60)      NOT NULL COMMENT 'Human-readable name',
    direction     ENUM('in', 'out') NOT NULL COMMENT 'in = money enters the wallet, out = money leaves it',
    description   VARCHAR(255)     NULL COMMENT 'What kind of SMS falls in this category',
    CONSTRAINT pk_transaction_categories PRIMARY KEY (category_id),
    CONSTRAINT uq_categories_code UNIQUE (category_code),
    CONSTRAINT chk_categories_code CHECK (REGEXP_LIKE(category_code, '^[a-z_]+$'))
) ENGINE = InnoDB COMMENT = 'Kinds of MoMo transaction';


-- 3. parties: the other side of a transaction (people, merchants,
--    agents, banks, MTN services)
CREATE TABLE parties (
    party_id      INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    party_name    VARCHAR(100) NOT NULL COMMENT 'Name as it appears in the SMS',
    party_type    ENUM('person', 'merchant', 'agent', 'bank', 'service') NOT NULL COMMENT 'What kind of party this is',
    phone_number  VARCHAR(10)  NULL COMMENT 'Phone number, for people and agents',
    merchant_code VARCHAR(60)  NULL COMMENT 'MoMoPay code or service code, for merchants, banks and services',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'When this party was first seen',
    CONSTRAINT pk_parties PRIMARY KEY (party_id),
    CONSTRAINT uq_parties_phone UNIQUE (phone_number),
    CONSTRAINT uq_parties_code UNIQUE (merchant_code),
    CONSTRAINT chk_parties_identified CHECK (phone_number IS NOT NULL OR merchant_code IS NOT NULL),
    CONSTRAINT chk_parties_phone CHECK (phone_number IS NULL OR REGEXP_LIKE(phone_number, '^07[2389][0-9]{7}$'))
) ENGINE = InnoDB COMMENT = 'Counterparties seen in transactions';

CREATE INDEX idx_parties_name ON parties (party_name);


-- 4. transactions: one row per MoMo transaction
CREATE TABLE transactions (
    transaction_id   BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    user_id          INT UNSIGNED     NOT NULL COMMENT 'FK to users: whose wallet this is',
    category_id      TINYINT UNSIGNED NOT NULL COMMENT 'FK to transaction_categories',
    sms_ref          VARCHAR(30)      NULL COMMENT 'TxnId from the SMS; NULL for entries typed in by hand',
    amount           DECIMAL(12, 2)   NOT NULL COMMENT 'Amount moved, in the currency below',
    fee              DECIMAL(10, 2)   NOT NULL DEFAULT 0.00 COMMENT 'Fee charged by MTN, 0 if none',
    balance_after    DECIMAL(12, 2)   NULL COMMENT 'Wallet balance after the transaction, only when the SMS states it',
    currency         CHAR(3)          NOT NULL DEFAULT 'RWF' COMMENT 'ISO 4217 currency code',
    transaction_date DATETIME         NOT NULL COMMENT 'When the transaction happened (from the SMS)',
    status           ENUM('completed', 'pending', 'failed', 'reversed') NOT NULL DEFAULT 'completed' COMMENT 'Outcome of the transaction',
    raw_sms          TEXT             NULL COMMENT 'Original SMS text, so it can be parsed again',
    created_at       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'When the row was inserted',
    updated_at       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'When the row was last changed',
    CONSTRAINT pk_transactions PRIMARY KEY (transaction_id),
    CONSTRAINT fk_transactions_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_transactions_category FOREIGN KEY (category_id)
        REFERENCES transaction_categories (category_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    -- Most screens list one user's transactions newest first. Declared here
    -- so the user_id foreign key uses it.
    INDEX idx_transactions_user_date (user_id, transaction_date),
    -- The same SMS can't be imported twice for the same user. sms_ref comes
    -- first on purpose: with (user_id, sms_ref), MySQL 9.7 skipped the
    -- user_id foreign key check for rows whose sms_ref is NULL.
    CONSTRAINT uq_transactions_sms UNIQUE (sms_ref, user_id),
    CONSTRAINT chk_transactions_amount CHECK (amount > 0),
    CONSTRAINT chk_transactions_fee CHECK (fee >= 0),
    CONSTRAINT chk_transactions_balance CHECK (balance_after IS NULL OR balance_after >= 0),
    CONSTRAINT chk_transactions_currency CHECK (REGEXP_LIKE(currency, '^[A-Z]{3}$', 'c'))
) ENGINE = InnoDB COMMENT = 'MoMo transactions read from SMS or entered by hand';

-- Filters on the dashboard
CREATE INDEX idx_transactions_category ON transactions (category_id);
CREATE INDEX idx_transactions_status ON transactions (status);


-- 5. transaction_parties: junction table resolving the M:N between
--    transactions and parties. A transaction can involve several
--    parties (e.g. a receiver and the agent who handled it) and a
--    party appears in many transactions.
CREATE TABLE transaction_parties (
    transaction_id BIGINT UNSIGNED NOT NULL COMMENT 'FK to transactions',
    party_id       INT UNSIGNED    NOT NULL COMMENT 'FK to parties',
    party_role     ENUM('sender', 'receiver', 'agent') NOT NULL COMMENT 'The part this party played in the transaction',
    CONSTRAINT pk_transaction_parties PRIMARY KEY (transaction_id, party_id, party_role),
    CONSTRAINT fk_tp_transaction FOREIGN KEY (transaction_id)
        REFERENCES transactions (transaction_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_tp_party FOREIGN KEY (party_id)
        REFERENCES parties (party_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB COMMENT = 'Which parties took part in which transaction, and how';

-- The PK starts with transaction_id; this index serves "all transactions for a party"
CREATE INDEX idx_tp_party ON transaction_parties (party_id);


-- 6. system_logs: what the system did (imports, logins, errors)
CREATE TABLE system_logs (
    log_id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    user_id        INT UNSIGNED    NULL COMMENT 'FK to users; NULL for events with no known user',
    transaction_id BIGINT UNSIGNED NULL COMMENT 'FK to transactions, when the event is about one',
    log_level      ENUM('DEBUG', 'INFO', 'WARNING', 'ERROR') NOT NULL DEFAULT 'INFO' COMMENT 'Severity',
    event_type     VARCHAR(40)     NOT NULL COMMENT 'Short code, e.g. sms_import, login_failed',
    message        VARCHAR(500)    NOT NULL COMMENT 'What happened, in plain words',
    created_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT 'When it happened, to the millisecond',
    CONSTRAINT pk_system_logs PRIMARY KEY (log_id),
    -- logs outlive the rows they mention, so deleting a user or transaction keeps the log
    CONSTRAINT fk_logs_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_logs_transaction FOREIGN KEY (transaction_id)
        REFERENCES transactions (transaction_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_logs_event CHECK (REGEXP_LIKE(event_type, '^[a-z_]+$'))
) ENGINE = InnoDB COMMENT = 'Audit and processing log';

CREATE INDEX idx_logs_created ON system_logs (created_at);
CREATE INDEX idx_logs_level_created ON system_logs (log_level, created_at);


-- 7. sessions: one row per logged-in browser
CREATE TABLE sessions (
    token      CHAR(43)     NOT NULL COMMENT 'Random URL-safe token, also stored in an HttpOnly cookie',
    user_id    INT UNSIGNED NOT NULL COMMENT 'FK to users',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'When the user logged in',
    expires_at DATETIME     NOT NULL COMMENT 'After this time the token is refused',
    CONSTRAINT pk_sessions PRIMARY KEY (token),
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_sessions_expiry CHECK (expires_at > created_at)
) ENGINE = InnoDB COMMENT = 'Login sessions';

CREATE INDEX idx_sessions_user ON sessions (user_id);


-- 8. unmatched_sms: MoMo messages no parsing rule understood.
--    Kept so a rule can be fixed later instead of losing the money.
CREATE TABLE unmatched_sms (
    unmatched_id INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    user_id      INT UNSIGNED NOT NULL COMMENT 'FK to users: whose backup it came from',
    body         TEXT         NOT NULL COMMENT 'Full SMS text',
    body_hash    CHAR(64)     NOT NULL COMMENT 'SHA-256 of body, so duplicates can be blocked with a UNIQUE key',
    received_at  DATETIME     NULL COMMENT 'When the phone received the SMS, if the backup says',
    CONSTRAINT pk_unmatched_sms PRIMARY KEY (unmatched_id),
    CONSTRAINT fk_unmatched_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT uq_unmatched UNIQUE (user_id, body_hash)
) ENGINE = InnoDB COMMENT = 'MoMo SMS the parser could not read';


-- Views used by the dashboard charts

-- Money in vs money out per user per month (completed transactions only)
CREATE VIEW v_monthly_flow AS
SELECT t.user_id,
       DATE_FORMAT(t.transaction_date, '%Y-%m') AS month,
       SUM(CASE WHEN c.direction = 'in'  THEN t.amount ELSE 0 END)         AS money_in,
       SUM(CASE WHEN c.direction = 'out' THEN t.amount + t.fee ELSE 0 END) AS money_out
FROM transactions t
JOIN transaction_categories c ON c.category_id = t.category_id
WHERE t.status = 'completed'
GROUP BY t.user_id, month;

-- Total spent at each merchant
CREATE VIEW v_merchant_spend AS
SELECT t.user_id,
       p.party_name    AS merchant,
       COUNT(*)        AS payments,
       SUM(t.amount)   AS total
FROM transactions t
JOIN transaction_categories c ON c.category_id = t.category_id
JOIN transaction_parties tp   ON tp.transaction_id = t.transaction_id AND tp.party_role = 'receiver'
JOIN parties p                ON p.party_id = tp.party_id
WHERE c.category_code = 'payment' AND t.status = 'completed'
GROUP BY t.user_id, p.party_name;


-- Sample data
-- Transactions 1-8 come from data/modified_sms_v2.xml.
-- Password hashes are real bcrypt hashes of throwaway demo passwords.

INSERT INTO users (user_id, username, full_name, phone_number, password_hash, created_at) VALUES
(1, 'aline_u',  'Aline Uwase',        '0789876543', '$2b$12$8qYAZhhBIR5T7URcvdaguuqAEwAnALOBg1QXGJI5cA2I28NH7DGTa', '2024-01-02 18:40:00'),
(2, 'jean_k',   'Jean Kamanzi',       '0788123456', '$2b$12$ZvN6IKDXcmgFOGUgRasJaO47sjJWKK47KHhiNYc.8y7bjWrZVjYh6', '2024-01-15 09:12:00'),
(3, 'grace_m',  'Grace Mukamana',     '0785550101', '$2b$12$4x50IKv.kAroT4mDbdAZp.lHxSDmThnBLF9n0T3SW0f6HWqkE7L0e', '2024-02-01 12:05:00'),
(4, 'eric_n',   'Eric Niyonzima',     '0782220202', '$2b$12$5LKvAF78IeS30EQznsYHZOZGvwR7.uotov5e1YxjkH1ZKBmL1uvC2', '2024-02-10 07:55:00'),
(5, 'diane_i',  'Diane Ingabire',     '0783330303', '$2b$12$CPFqRUnH2OkgbTB21BTaUuxaVt38KhyHCuGke5HSjNvwaFMzUlFkG', '2024-02-20 20:30:00');

INSERT INTO transaction_categories (category_id, category_code, category_name, direction, description) VALUES
(1, 'incoming_money', 'Incoming money',       'in',  'Money received from another MoMo number'),
(2, 'payment',        'Payment to merchant',  'out', 'MoMoPay payment to a merchant code'),
(3, 'transfer',       'Transfer to number',   'out', 'Money sent to another MoMo number'),
(4, 'airtime',        'Airtime purchase',     'out', 'Airtime or bundles bought from MTN'),
(5, 'bank_deposit',   'Bank deposit',         'in',  'Money pushed into the wallet from a bank account'),
(6, 'withdrawal',     'Cash withdrawal',      'out', 'Cash taken out at a MoMo agent');

INSERT INTO parties (party_id, party_name, party_type, phone_number, merchant_code) VALUES
(1,  'Alice',               'person',   '0781234567', NULL),
(2,  'Bob',                 'person',   '0782345678', NULL),
(3,  'Carol',               'person',   '0783456789', NULL),
(4,  'David',               'person',   '0784567890', NULL),
(5,  'Eve',                 'person',   '0785678901', NULL),
(6,  'Frank',               'person',   '0786789012', NULL),
(7,  'Grace',               'person',   '0787890123', NULL),
(8,  'Kigali Mart',         'merchant', NULL,         'MTN:MoMoPay:Kigali_Mart'),
(9,  'Pharmacy Plus',       'merchant', NULL,         'MTN:MoMoPay:Pharmacy_Plus'),
(10, 'Supermarket A',       'merchant', NULL,         'MTN:MoMoPay:Supermarket_A'),
(11, 'MTN Airtime',         'service',  NULL,         'MTN:Airtime'),
(12, 'Kimironko Agent 045', 'agent',    '0788112233', 'AGT-045'),
(13, 'Bank of Kigali',      'bank',     NULL,         'BANK:BK');

INSERT INTO transactions
    (transaction_id, user_id, category_id, sms_ref, amount, fee, balance_after, transaction_date, status, raw_sms) VALUES
(1,  1, 1, 'TXN001',  5000.00,  0.00, 15000.00, '2024-01-03 08:12:00', 'completed',
     'You have received 5000 RWF from Alice (0781234567). Your new balance is 15000 RWF. TxnId: TXN001'),
(2,  1, 2, 'TXN002',  2000.00,  0.00, NULL,     '2024-01-04 10:30:00', 'completed',
     'Your payment of 2000 RWF to Kigali Mart was successful. TxnId: TXN002'),
(3,  1, 3, 'TXN003', 10000.00, 100.00, NULL,    '2024-01-05 14:22:00', 'completed',
     'You have transferred 10000 RWF to Bob (0782345678). TxnId: TXN003'),
(4,  1, 1, 'TXN004', 15000.00,  0.00, NULL,     '2024-01-06 09:05:00', 'completed',
     'You have received 15000 RWF from Carol (0783456789). TxnId: TXN004'),
(5,  1, 4, 'TXN005',   500.00,  0.00, NULL,     '2024-01-07 11:00:00', 'completed',
     'You have bought airtime worth 500 RWF. TxnId: TXN005'),
(6,  1, 2, 'TXN006',  3500.00,  0.00, NULL,     '2024-01-08 16:45:00', 'completed',
     'Your payment of 3500 RWF to Pharmacy Plus was successful. TxnId: TXN006'),
(7,  1, 1, 'TXN007', 20000.00,  0.00, NULL,     '2024-01-09 08:30:00', 'completed',
     'You have received 20000 RWF from David (0784567890). TxnId: TXN007'),
(8,  1, 3, 'TXN008',  7500.00, 100.00, NULL,    '2024-01-10 13:15:00', 'completed',
     'You have transferred 7500 RWF to Eve (0785678901). TxnId: TXN008'),
(9,  2, 6, NULL,     30000.00, 700.00, NULL,    '2024-02-02 10:00:00', 'completed', NULL),
(10, 2, 3, 'TXN2001', 4000.00,  0.00, NULL,     '2024-02-03 15:20:00', 'failed',
     'Your transfer of 4000 RWF to Grace (0787890123) has failed. TxnId: TXN2001'),
(11, 3, 5, 'TXN3001', 50000.00, 0.00, 62000.00, '2024-02-05 09:00:00', 'completed',
     'You have received 50000 RWF from Bank of Kigali. Your new balance is 62000 RWF. TxnId: TXN3001'),
(12, 3, 2, NULL,      1500.00,  0.00, NULL,     '2024-02-06 18:10:00', 'pending', NULL),
(13, 4, 3, 'TXN4001', 12000.00, 250.00, NULL,   '2024-02-12 11:40:00', 'completed',
     'You have transferred 12000 RWF to Frank (0786789012) via agent Kimironko Agent 045. TxnId: TXN4001'),
(14, 5, 4, 'TXN5001', 1000.00,  0.00, NULL,     '2024-02-21 07:15:00', 'completed',
     'You have bought airtime worth 1000 RWF. TxnId: TXN5001');

INSERT INTO transaction_parties (transaction_id, party_id, party_role) VALUES
(1,  1,  'sender'),
(2,  8,  'receiver'),
(3,  2,  'receiver'),
(4,  3,  'sender'),
(5,  11, 'receiver'),
(6,  9,  'receiver'),
(7,  4,  'sender'),
(8,  5,  'receiver'),
(9,  12, 'agent'),
(10, 7,  'receiver'),
(11, 13, 'sender'),
(12, 10, 'receiver'),
(13, 6,  'receiver'),
(13, 12, 'agent'),        -- one transaction, two parties
(14, 11, 'receiver');

INSERT INTO system_logs (user_id, transaction_id, log_level, event_type, message, created_at) VALUES
(1,    NULL, 'INFO',    'user_registered', 'New account aline_u created',                                   '2024-01-02 18:40:00.120'),
(1,    NULL, 'INFO',    'sms_import',      'Imported sms_backup.xml: 8 new transactions, 0 duplicates, 2 unmatched', '2024-01-11 19:02:13.504'),
(1,    NULL, 'WARNING', 'sms_unmatched',   'MoMo message did not match any parsing rule; saved to unmatched_sms', '2024-01-11 19:02:13.611'),
(2,    10,   'ERROR',   'transaction_failed', 'Transfer TXN2001 to 0787890123 reported as failed by MTN',   '2024-02-03 15:20:05.002'),
(3,    12,   'INFO',    'transaction_created', 'Manual payment entry added from the dashboard',            '2024-02-06 18:11:40.870'),
(NULL, NULL, 'WARNING', 'login_failed',    'Failed login for unknown username "admin" from 197.243.10.5',  '2024-02-07 02:14:55.310'),
(4,    13,   'INFO',    'sms_import',      'Imported 1 new transaction with agent Kimironko Agent 045',     '2024-02-12 12:00:02.441'),
(1,    3,   'INFO',    'transaction_updated', 'Fee on TXN003 corrected from 0 to 100 RWF',               '2024-02-15 08:30:10.000');

INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES
('jNuT13-HnthKP1nnrT1asONpvkcTu8VZvlVL1jpdPbM', 1, '2024-02-20 08:00:00', '2024-02-21 08:00:00'),
('dD6rkcZSgNCpoIJGk_7q0ONh3lBXu9BXlBi2gW-docM', 2, '2024-02-20 09:30:00', '2024-02-21 09:30:00'),
('J5_BFqvwiGKDUxGff_Ra-dV2EjXwYVgeX0-CHWTOJHs', 3, '2024-02-21 12:10:00', '2024-02-22 12:10:00'),
('G8EHZALeQ2MORck5QwNZaeIcITu-H_GrM97eyCBRN-0', 4, '2024-02-21 14:45:00', '2024-02-22 14:45:00'),
('CfaY6_L-0ziGesX4_0Hh5fi4yH4OS5s1vkqIgjzSwsc', 5, '2024-02-22 07:20:00', '2024-02-23 07:20:00');

INSERT INTO unmatched_sms (user_id, body, body_hash, received_at) VALUES
(1, 'Y''ello! Your MoMo PIN was changed successfully.',
    SHA2('Y''ello! Your MoMo PIN was changed successfully.', 256), '2024-01-09 21:00:00'),
(1, 'You have a pending payment request of 3000 RWF from Kigali Mart. Dial *182*7# to approve.',
    SHA2('You have a pending payment request of 3000 RWF from Kigali Mart. Dial *182*7# to approve.', 256), '2024-01-10 12:30:00'),
(2, 'Your MoMo loan of 20000 RWF has been approved. Repay by 2024-03-01.',
    SHA2('Your MoMo loan of 20000 RWF has been approved. Repay by 2024-03-01.', 256), '2024-02-01 08:00:00'),
(3, 'Bundle purchase: 1GB for 1000 RWF. Valid until 2024-02-12.',
    SHA2('Bundle purchase: 1GB for 1000 RWF. Valid until 2024-02-12.', 256), '2024-02-05 10:15:00'),
(5, 'Cash-in of 5000 RWF by agent 0788112233 is being processed.',
    SHA2('Cash-in of 5000 RWF by agent 0788112233 is being processed.', 256), '2024-02-21 07:00:00');
