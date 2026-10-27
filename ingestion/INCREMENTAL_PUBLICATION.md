# Incremental RAW publication

The loader preserves its staging workflow and defaults to dry run. Airflow calls it
without arguments and therefore never enables publication automatically.

From the Project 07 directory, with the existing Airflow container running:

```powershell
docker exec subsurface-airflow python -u /opt/subsurface_project/ingestion/load_snowflake.py --dry-run
```

The running container uses its existing environment. Do not create or copy
credentials into source files.

Dry run uploads CSVs and rebuilds session-scoped temporary STG tables, validates
counts/NULLs and both sides' business keys, then reports planned inserts and
updates. It does not change RAW. Staging must be built on the same connection.

Real publication requires the explicit `--publish` flag and separate user
authorization. It validates all business keys before the first MERGE, executes
four MERGEs within BEGIN TRANSACTION, and commits only after all succeed. DDL and
AUTOCOMMIT changes are excluded from that transaction because Snowflake can
implicitly commit them. Actual MERGE result counts are logged after commit;
PREVIEW lines are estimates, not confirmed writes. On MERGE/commit failure the
loader attempts rollback and propagates the original error. A lost commit reply
can leave an unknown server outcome; inspect/reconcile before an idempotent rerun.

Use a dedicated idle connection and serialize publication with every other RAW
writer. Snowflake key checks are preflight checks, not enforced unique constraints
or protection against concurrent writes. No deletion of absent source rows occurs.
All non-key fields use IS DISTINCT FROM. Only WELLS.LOCATION comparison collapses
whitespace and trims it; inserted/updated values come from staging unchanged.

Offline tests:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_publish_to_raw.py -v
```

These tests execute preview SQL and generated comparison/assignment expressions
using SQLite, with a Snowflake MERGE/result adapter and injected transaction errors.
They do not verify Snowflake server syntax, network failures, or concurrency.
Snowflake transaction reference: https://docs.snowflake.com/en/sql-reference/transactions
