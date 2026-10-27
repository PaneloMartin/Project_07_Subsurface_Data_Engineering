# Isolated Snowflake MERGE integration test

This is an opt-in test, separate from Airflow. No original CSVs or RAW objects
are read, modified, cloned, or replaced. It calls the real publish_to_raw function
with explicit source/target mappings; SQL predicates, MERGE generation, key checks,
result counts and transaction handling are shared with production.

After explicit authorization, from Project 07 with the existing container running:

```powershell
docker exec subsurface-airflow python -u /opt/subsurface_project/tests/snowflake_merge_integration.py --run-snowflake
```

Without --run-snowflake the script exits without connecting. Credentials come
from the existing container environment. The account needs warehouse usage,
SUBSURFACE_DB usage and TESTING usage. Temporary tables do not require CREATE
TABLE on the schema. If TESTING does not exist,
CREATE SCHEMA on SUBSURFACE_DB is also needed. No additional RAW privilege is
needed by this harness. The schema name is fixed, not configurable from the CLI.

The script creates SUBSURFACE_DB.TESTING if absent and eight uniquely named
IT_MERGE_<UUID> temporary tables. It uses explicit synthetic definitions, not
CREATE LIKE RAW. The testing schema remains; tables are explicitly dropped on
exit and are session-scoped as a second cleanup mechanism. Existing TESTING
objects are never replaced. Setup and cleanup DDL occur outside MERGE transactions.

For every table the first publication must report 1 insert and 3 updates.
Six cases verify unchanged values, a real change, value-to-NULL, NULL-to-value,
a whitespace-only LOCATION difference (WELLS), and a new row. Full row comparisons
verify original LOCATION preservation and all NULLs. The second publication must
report 0 inserts and 0 updates for every table and leave the full contents intact.

For rollback, all staging rows are changed, then a connection wrapper injects a
real SQL conversion error before the fourth MERGE. The first three MERGEs execute
on Snowflake. The test requires the server error to propagate, exactly one rollback,
and every destination row to equal the snapshot before the failed publication.
No alternative MERGE logic is implemented in the harness.

Successful execution prints:
PASS: inserts=1, updates=3 per table; values, NULLs, LOCATION, idempotence, rollback

Any failed assertion or unexpected Snowflake error exits nonzero. The synthetic
column types cover the MERGE behavior; they do not validate production DDL parity,
concurrent writers, or uncertain commit outcomes caused by network interruption.

Offline regression checks (no credentials, Docker, or network needed):

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_publish_to_raw.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -p test_integration_harness.py -v
```

Offline harness tests run the complete scenario through a SQLite adapter, verify
opt-in before connection, unique TESTING names, and rejection of invalid mappings.
Remote execution is intentionally not part of unittest discovery.

Temporary table lifecycle and permissions: https://docs.snowflake.com/en/user-guide/tables-temp-transient
