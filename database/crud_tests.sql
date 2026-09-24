USE momo_ledger;

-- 1. CREATE: record a new payment with its party and a log entry,
--    all or nothing
SELECT '1. CREATE' AS test;

START TRANSACTION;
INSERT INTO transactions (user_id, category_id, sms_ref, amount, fee, transaction_date, status, raw_sms)
VALUES (1, (SELECT category_id FROM transaction_categories WHERE category_code = 'payment'),
        'TXN009', 1200.00, 0.00, '2024-01-11 17:00:00', 'completed',
        'Your payment of 1200 RWF to Supermarket A was successful. TxnId: TXN009');
SET @new_id = LAST_INSERT_ID();
INSERT INTO transaction_parties (transaction_id, party_id, party_role)
VALUES (@new_id, (SELECT party_id FROM parties WHERE merchant_code = 'MTN:MoMoPay:Supermarket_A'), 'receiver');
INSERT INTO system_logs (user_id, transaction_id, log_level, event_type, message)
VALUES (1, @new_id, 'INFO', 'transaction_created', 'Imported TXN009 from SMS');
COMMIT;

SELECT t.transaction_id, t.sms_ref, c.category_code, t.amount, p.party_name, tp.party_role
FROM transactions t
JOIN transaction_categories c ON c.category_id = t.category_id
JOIN transaction_parties tp   ON tp.transaction_id = t.transaction_id
JOIN parties p                ON p.party_id = tp.party_id
WHERE t.transaction_id = @new_id;


-- 2. READ
SELECT '2a. READ: one user''s transactions with category and parties' AS test;
SELECT t.transaction_id,
       t.transaction_date,
       c.category_name,
       c.direction,
       t.amount,
       t.fee,
       t.status,
       GROUP_CONCAT(CONCAT(p.party_name, ' (', tp.party_role, ')') ORDER BY tp.party_role SEPARATOR ', ') AS parties
FROM transactions t
JOIN transaction_categories c    ON c.category_id = t.category_id
LEFT JOIN transaction_parties tp ON tp.transaction_id = t.transaction_id
LEFT JOIN parties p              ON p.party_id = tp.party_id
WHERE t.user_id = 1
GROUP BY t.transaction_id
ORDER BY t.transaction_date DESC;

SELECT '2b. READ: money in vs out per month (view)' AS test;
SELECT * FROM v_monthly_flow ORDER BY user_id, month;

SELECT '2c. READ: spend per merchant (view)' AS test;
SELECT * FROM v_merchant_spend ORDER BY total DESC;

SELECT '2d. READ: transactions with more than one party (uses the junction table)' AS test;
SELECT t.transaction_id, t.sms_ref, COUNT(*) AS party_count,
       GROUP_CONCAT(CONCAT(p.party_name, ' (', tp.party_role, ')') SEPARATOR ', ') AS parties
FROM transactions t
JOIN transaction_parties tp ON tp.transaction_id = t.transaction_id
JOIN parties p              ON p.party_id = tp.party_id
GROUP BY t.transaction_id, t.sms_ref
HAVING COUNT(*) > 1;

SELECT '2e. READ: top counterparties across all users' AS test;
SELECT p.party_name, p.party_type, COUNT(*) AS times_seen, SUM(t.amount) AS total_amount
FROM parties p
JOIN transaction_parties tp ON tp.party_id = p.party_id
JOIN transactions t         ON t.transaction_id = tp.transaction_id
WHERE t.status = 'completed'
GROUP BY p.party_id, p.party_name, p.party_type
ORDER BY total_amount DESC
LIMIT 5;

SELECT '2f. READ: warnings and errors in the log' AS test;
SELECT l.created_at, l.log_level, l.event_type, u.username, l.message
FROM system_logs l
LEFT JOIN users u ON u.user_id = l.user_id
WHERE l.log_level IN ('WARNING', 'ERROR')
ORDER BY l.created_at;

SELECT '2g. READ: a user''s date range is read through an index, not a full scan' AS test;
EXPLAIN SELECT transaction_id, amount FROM transactions
WHERE user_id = 1 AND transaction_date BETWEEN '2024-01-01' AND '2024-01-31';

 
-- 3. UPDATE: MTN reverses a failed transfer
SELECT '3. UPDATE' AS test;
SELECT transaction_id, sms_ref, status, updated_at FROM transactions WHERE sms_ref = 'TXN2001';

DO SLEEP(1);  -- so the new updated_at is visibly different
UPDATE transactions SET status = 'reversed' WHERE sms_ref = 'TXN2001';
INSERT INTO system_logs (user_id, transaction_id, log_level, event_type, message)
SELECT user_id, transaction_id, 'INFO', 'transaction_updated', 'Status changed from failed to reversed'
FROM transactions WHERE sms_ref = 'TXN2001';

SELECT transaction_id, sms_ref, status, updated_at FROM transactions WHERE sms_ref = 'TXN2001';


-- 4. DELETE: remove a transaction. Its junction rows go with it
--    (ON DELETE CASCADE), its log rows stay but lose the link
--    (ON DELETE SET NULL).
SELECT '4. DELETE' AS test;
SELECT (SELECT COUNT(*) FROM transaction_parties WHERE transaction_id = 13) AS party_links_before,
       (SELECT COUNT(*) FROM system_logs WHERE transaction_id = 13)        AS logs_linked_before;

DELETE FROM transactions WHERE transaction_id = 13;

SELECT (SELECT COUNT(*) FROM transactions WHERE transaction_id = 13)        AS transaction_after,
       (SELECT COUNT(*) FROM transaction_parties WHERE transaction_id = 13) AS party_links_after,
       (SELECT COUNT(*) FROM system_logs WHERE transaction_id = 13)        AS logs_linked_after,
       (SELECT COUNT(*) FROM system_logs
         WHERE transaction_id IS NULL AND message LIKE '%Kimironko%')      AS log_kept_unlinked;


-- 5. Constraints: every statement below must be REJECTED
SELECT '5a. negative amount -> CHECK chk_transactions_amount' AS test;
INSERT INTO transactions (user_id, category_id, amount, transaction_date)
VALUES (1, 2, -500.00, '2024-03-01 10:00:00');

SELECT '5b. same SMS imported twice -> UNIQUE uq_transactions_sms' AS test;
INSERT INTO transactions (user_id, category_id, sms_ref, amount, transaction_date)
VALUES (1, 1, 'TXN001', 5000.00, '2024-01-03 08:12:00');

SELECT '5c. user that does not exist -> FOREIGN KEY fk_transactions_user' AS test;
INSERT INTO transactions (user_id, category_id, amount, transaction_date)
VALUES (999, 1, 100.00, '2024-03-01 10:00:00');

SELECT '5d. delete a category still in use -> FOREIGN KEY ON DELETE RESTRICT' AS test;
DELETE FROM transaction_categories WHERE category_code = 'payment';

SELECT '5e. badly formed phone number -> CHECK chk_users_phone' AS test;
INSERT INTO users (username, full_name, phone_number, password_hash)
VALUES ('bad_phone', 'Bad Phone', '12345', '$2b$12$ZvN6IKDXcmgFOGUgRasJaO47sjJWKK47KHhiNYc.8y7bjWrZVjYh6');

SELECT '5f. plain-text password -> CHECK chk_users_hash' AS test;
INSERT INTO users (username, full_name, phone_number, password_hash)
VALUES ('plain_pw', 'Plain Password', '0781112223', 'password123');

SELECT '5g. party with no phone and no code -> CHECK chk_parties_identified' AS test;
INSERT INTO parties (party_name, party_type) VALUES ('Nobody', 'person');

SELECT '5h. session that expires before it starts -> CHECK chk_sessions_expiry' AS test;
INSERT INTO sessions (token, user_id, created_at, expires_at)
VALUES ('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 1, '2024-03-01 10:00:00', '2024-02-01 10:00:00');

SELECT 'Row counts after the tests' AS test;
SELECT (SELECT COUNT(*) FROM transactions)        AS transactions,
       (SELECT COUNT(*) FROM transaction_parties) AS transaction_parties,
       (SELECT COUNT(*) FROM users)               AS users,
       (SELECT COUNT(*) FROM parties)             AS parties,
       (SELECT COUNT(*) FROM system_logs)         AS system_logs;
