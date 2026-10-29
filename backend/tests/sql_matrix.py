"""The mcp-sql validator's negative matrix (05a review r1 MINOR-1, KARARLAR "05a review r1
kararları" item 5). Every row is refused before any database connection: the unit test proves
it with a connect function that is never called, the integration test with the demo
database's own session counter (pg_stat_database.sessions).
"""

REJECTED = [
    # exactly one statement
    ("SELECT 1 FROM beds; SELECT 2 FROM beds", "sql_multiple_statements"),
    ("SELECT 1 FROM beds; DELETE FROM beds", "sql_multiple_statements"),
    # comments hide nothing: a statement after a comment is still a second statement
    ("SELECT 1 FROM beds -- note\n; DELETE FROM beds", "sql_multiple_statements"),
    ("SELECT 1 FROM beds /* note */; DROP TABLE beds", "sql_multiple_statements"),
    # set operations: every branch is a SELECT
    ("SELECT id FROM beds UNION VALUES (1)", "sql_not_select"),
    ("SELECT id FROM beds UNION SELECT oid FROM pg_authid", "sql_system_catalog"),
    ("SELECT id FROM beds INTERSECT SELECT id FROM beds FOR UPDATE", "sql_not_select"),
    # functions that change state, wait, or reach outside the query (closed list)
    ("SELECT setval('beds_id_seq', 1) FROM beds", "sql_function_not_allowed"),
    ("SELECT nextval('beds_id_seq') FROM beds", "sql_function_not_allowed"),
    ("SELECT lastval() FROM beds", "sql_function_not_allowed"),
    ("SELECT currval('beds_id_seq') FROM beds", "sql_function_not_allowed"),
    ("SELECT set_config('statement_timeout', '0', false) FROM beds", "sql_function_not_allowed"),
    ("SELECT current_setting('search_path') FROM beds", "sql_function_not_allowed"),
    ("SELECT pg_sleep(10) FROM beds", "sql_function_not_allowed"),
    ("SELECT pg_read_file('/etc/passwd') FROM beds", "sql_function_not_allowed"),
    ("SELECT pg_read_binary_file('/etc/passwd') FROM beds", "sql_function_not_allowed"),
    ("SELECT lo_import('/etc/passwd') FROM beds", "sql_function_not_allowed"),
    ("SELECT dblink_exec('host=x', 'DROP TABLE beds') FROM beds", "sql_function_not_allowed"),
    ("SELECT txid_current() FROM beds", "sql_function_not_allowed"),
    ("SELECT SETVAL('beds_id_seq', 1) FROM beds", "sql_function_not_allowed"),
    # writes inside a CTE
    ("WITH gone AS (DELETE FROM beds RETURNING *) SELECT * FROM gone", "sql_not_select"),
    (
        "WITH up AS (UPDATE beds SET is_active = false RETURNING *) SELECT * FROM up",
        "sql_not_select",
    ),
    (
        "WITH ins AS (INSERT INTO beds (id) VALUES (999) RETURNING *) SELECT * FROM ins",
        "sql_not_select",
    ),
    # COPY is not a query
    ("COPY beds TO STDOUT", "sql_not_select"),
]
