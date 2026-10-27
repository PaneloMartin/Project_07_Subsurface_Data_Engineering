
import argparse
import re
import os
from pathlib import Path

import snowflake.connector


PROJECT_DIR = Path("/opt/subsurface_project")
DATA_DIR = PROJECT_DIR / "data" / "processed"

DATABASE = "SUBSURFACE_DB"
SCHEMA = "RAW"

STAGE = f"{DATABASE}.{SCHEMA}.LAS_STAGE"
FILE_FORMAT = f"{DATABASE}.{SCHEMA}.LAS_CSV_FORMAT"

FILES = {
    "WELLS": "wells.csv",
    "LOG_FILES": "log_files.csv",
    "CURVES": "curves.csv",
    "MEASUREMENTS": "measurements.csv",
}


def connect_to_snowflake():
    """Connect using environment variables, without hardcoded credentials."""
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        role=os.environ["SNOWFLAKE_ROLE"],
        login_timeout=30,
    )


def validate_local_files():
    """Check that all four processed CSV files exist and are nonempty."""
    print("Checking processed CSV files...", flush=True)

    for table, filename in FILES.items():
        path = DATA_DIR / filename

        if not path.is_file():
            raise FileNotFoundError(f"Missing file: {path}")

        if path.stat().st_size == 0:
            raise ValueError(f"Empty file: {path}")

        print(f"OK: {table} -> {filename}", flush=True)


def inspect_snowflake(connection):
    """Read existing table counts without changing data."""
    cursor = connection.cursor()

    try:
        for table in FILES:
            cursor.execute(
                f"SELECT COUNT(*) FROM {DATABASE}.{SCHEMA}.{table}"
            )
            count = cursor.fetchone()[0]
            print(f"{table}: {count:,} existing rows", flush=True)

        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT_IF(VALUE IS NULL) AS null_values
            FROM {DATABASE}.{SCHEMA}.MEASUREMENTS
            """
        )

        total, nulls = cursor.fetchone()
        print(
            f"MEASUREMENTS validation: "
            f"{total:,} rows, {nulls:,} NULL values",
            flush=True,
        )

    finally:
        cursor.close()


def upload_csv_files(connection):
    """
    Upload processed CSV files to the existing Snowflake stage.
    Does not modify destination tables.
    """
    cursor = connection.cursor()

    try:
        for table, filename in FILES.items():
            local_path = DATA_DIR / filename

            print(f"Uploading {filename} to Snowflake stage...", flush=True)

            put_sql = (
                f"PUT 'file://{local_path.as_posix()}' "
                f"@{STAGE}/{table.lower()}/ "
                f"AUTO_COMPRESS=TRUE "
                f"OVERWRITE=TRUE"
            )

            cursor.execute(put_sql)

            for result in cursor.fetchall():
                print(result, flush=True)

        print("All CSV files uploaded successfully.", flush=True)

    finally:
        cursor.close()


def load_into_staging(connection):
    """
    Load CSV files into temporary Snowflake tables.

    Original RAW tables remain untouched.
    Temporary tables are scoped to this connection.
    """
    cursor = connection.cursor()

    try:
        for table in FILES:
            temp_table = f"STG_{table}"
            source_table = f"{DATABASE}.{SCHEMA}.{table}"

            print(f"Preparing temporary table {temp_table}...", flush=True)

            cursor.execute(
                f"CREATE OR REPLACE TEMPORARY TABLE {temp_table} "
                f"LIKE {source_table}"
            )

            copy_sql = f"""
                COPY INTO {temp_table}
                FROM @{STAGE}/{table.lower()}/
                FILE_FORMAT = (FORMAT_NAME = '{FILE_FORMAT}')
                ON_ERROR = ABORT_STATEMENT
            """

            cursor.execute(copy_sql)

            results = cursor.fetchall()
            for result in results:
                print(result, flush=True)

            cursor.execute(f"SELECT COUNT(*) FROM {temp_table}")
            row_count = cursor.fetchone()[0]

            print(
                f"{temp_table}: {row_count:,} staged rows",
                flush=True,
            )

        print("All temporary tables loaded successfully.", flush=True)

    finally:
        cursor.close()


def validate_staging(connection):
    """
    Validate staged row counts against local CSV files
    and verify measurement NULL values.
    """
    import csv

    cursor = connection.cursor()

    try:
        for table, filename in FILES.items():
            csv_path = DATA_DIR / filename

            with csv_path.open(
                "r", encoding="utf-8-sig", newline=""
            ) as file:
                reader = csv.DictReader(file)
                expected_count = sum(1 for _ in reader)

            cursor.execute(f"SELECT COUNT(*) FROM STG_{table}")
            actual_count = cursor.fetchone()[0]

            print(
                f"{table}: CSV={expected_count:,} | "
                f"STAGING={actual_count:,}",
                flush=True,
            )

            if actual_count != expected_count:
                raise ValueError(
                    f"Row count mismatch in {table}: "
                    f"expected {expected_count}, got {actual_count}"
                )

        # Calculate expected NULL values directly from the CSV
        with (DATA_DIR / "measurements.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            expected_nulls = sum(
                1
                for row in csv.DictReader(file)
                if row["value"] == ""
            )

        # Compare with Snowflake staging table
        cursor.execute(
            "SELECT COUNT_IF(VALUE IS NULL) FROM STG_MEASUREMENTS"
        )
        actual_nulls = cursor.fetchone()[0]

        print(
            f"MEASUREMENTS NULL values: "
            f"CSV={expected_nulls:,} | "
            f"STAGING={actual_nulls:,}",
            flush=True,
        )

        if actual_nulls != expected_nulls:
            raise ValueError(
                f"Measurement NULL mismatch: "
                f"expected {expected_nulls}, got {actual_nulls}"
            )

        print(
            "All staging validations passed successfully.",
            flush=True,
        )

    finally:
        cursor.close()


def compare_staging_to_raw(connection):
    """
    Compare staged data with existing RAW tables.

    Uses EXCEPT in both directions to detect differences.
    No existing RAW data is modified.
    """
    cursor = connection.cursor()

    try:
        all_match = True

        for table in FILES:
            staging_table = f"STG_{table}"
            raw_table = f"{DATABASE}.{SCHEMA}.{table}"

            print(f"Comparing {table}...", flush=True)

            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT * FROM {staging_table}
                    EXCEPT
                    SELECT * FROM {raw_table}
                )
                """
            )
            missing_in_raw = cursor.fetchone()[0]

            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT * FROM {raw_table}
                    EXCEPT
                    SELECT * FROM {staging_table}
                )
                """
            )
            extra_in_raw = cursor.fetchone()[0]

            cursor.execute(
                f"SELECT COUNT(*) FROM {staging_table}"
            )
            staging_count = cursor.fetchone()[0]

            cursor.execute(
                f"SELECT COUNT(*) FROM {raw_table}"
            )
            raw_count = cursor.fetchone()[0]

            matches = (
                missing_in_raw == 0
                and extra_in_raw == 0
                and staging_count == raw_count
            )

            print(
                f"{table}: "
                f"missing_in_raw={missing_in_raw}, "
                f"extra_in_raw={extra_in_raw}, "
                f"counts_match={staging_count == raw_count}",
                flush=True,
            )

            if not matches:
                all_match = False

        if all_match:
            print(
                "All RAW tables match staging. "
                "No publication required.",
                flush=True,
            )
        else:
            print(
                "Differences detected. "
                "Publication is required, but no changes were made.",
                flush=True,
            )

        return all_match

    finally:
        cursor.close()



def diagnose_wells(connection):
    """
    Identify which WELLS columns differ between staging and RAW.
    Also compare LOCATION after whitespace normalization.
    """
    columns = [
        "API",
        "LEASE",
        "OPERATOR",
        "LATITUDE",
        "LONGITUDE",
        "LOCATION",
        "ELEVATION",
        "ELEVATION_REFERENCE",
    ]

    cursor = connection.cursor()

    try:
        print("\nWELLS COLUMN DIAGNOSTIC", flush=True)

        # Compare each column individually
        for column in columns:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM STG_WELLS s
                JOIN {DATABASE}.{SCHEMA}.WELLS r
                  ON s.KGS_ID = r.KGS_ID
                WHERE NOT EQUAL_NULL(s.{column}, r.{column})
                """
            )

            differences = cursor.fetchone()[0]

            print(
                f"{column}: {differences} differing rows",
                flush=True,
            )

        # Compare LOCATION after normalizing whitespace
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM STG_WELLS s
            JOIN {DATABASE}.{SCHEMA}.WELLS r
              ON s.KGS_ID = r.KGS_ID
            WHERE NOT EQUAL_NULL(
                REGEXP_REPLACE(
                    TRIM(s.LOCATION),
                    '[[:space:]]+',
                    ' '
                ),
                REGEXP_REPLACE(
                    TRIM(r.LOCATION),
                    '[[:space:]]+',
                    ' '
                )
            )
            """
        )

        normalized_differences = cursor.fetchone()[0]

        print(
            f"LOCATION differences after normalization: "
            f"{normalized_differences}",
            flush=True,
        )

    finally:
        cursor.close()


def validate_staging_keys(connection):
    """
    Validate business key uniqueness and non-null values
    in Snowflake staging tables.
    """
    keys = {
        "WELLS": ["KGS_ID"],
        "LOG_FILES": ["FILE_ID"],
        "CURVES": ["FILE_ID", "CURVE_POSITION"],
        "MEASUREMENTS": ["FILE_ID", "DEPTH", "MNEMONIC"],
    }

    cursor = connection.cursor()

    try:
        print("\nSTAGING BUSINESS KEY VALIDATION", flush=True)

        for table, columns in keys.items():
            column_list = ", ".join(columns)
            null_condition = " OR ".join(
                f"{column} IS NULL" for column in columns
            )

            cursor.execute(
                f"""
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(DISTINCT {column_list}) AS unique_keys,
                    COUNT_IF({null_condition}) AS null_keys
                FROM STG_{table}
                """
            )

            total, unique, nulls = cursor.fetchone()
            nulls = nulls or 0

            duplicates = total - unique - nulls

            print(
                f"{table}: total={total:,}, "
                f"unique={unique:,}, "
                f"null_keys={nulls:,}, "
                f"duplicates={duplicates:,}",
                flush=True,
            )

            if nulls > 0 or duplicates > 0:
                raise ValueError(
                    f"Invalid business keys in STG_{table}"
                )

        print(
            "All staging business keys validated successfully.",
            flush=True,
        )

    finally:
        cursor.close()


def preview_merge(connection):
    """
    Preview incremental inserts without modifying RAW tables.
    """
    keys = {
        "WELLS": ["KGS_ID"],
        "LOG_FILES": ["FILE_ID"],
        "CURVES": ["FILE_ID", "CURVE_POSITION"],
        "MEASUREMENTS": ["FILE_ID", "DEPTH", "MNEMONIC"],
    }

    cursor = connection.cursor()

    try:
        print("\nINCREMENTAL LOAD PREVIEW", flush=True)

        total_new = 0

        for table, columns in keys.items():
            join_condition = " AND ".join(
                f"s.{column} = r.{column}"
                for column in columns
            )

            first_key = columns[0]

            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM STG_{table} s
                LEFT JOIN {DATABASE}.{SCHEMA}.{table} r
                  ON {join_condition}
                WHERE r.{first_key} IS NULL
                """
            )

            new_rows = cursor.fetchone()[0]
            total_new += new_rows

            print(
                f"{table}: {new_rows:,} new rows to insert",
                flush=True,
            )

        print(
            f"TOTAL NEW ROWS: {total_new:,}",
            flush=True,
        )

        print("Preview completed. No RAW data modified.")

    finally:
        cursor.close()



# Column/key allowlists; optional table mappings are validated separately.
BUSINESS_KEYS = {
    "WELLS": ("KGS_ID",),
    "LOG_FILES": ("FILE_ID",),
    "CURVES": ("FILE_ID", "CURVE_POSITION"),
    "MEASUREMENTS": ("FILE_ID", "DEPTH", "MNEMONIC"),
}
TABLE_COLUMNS = {
    "WELLS": ("KGS_ID", "API", "LEASE", "OPERATOR", "LATITUDE", "LONGITUDE",
              "LOCATION", "ELEVATION", "ELEVATION_REFERENCE"),
    "LOG_FILES": ("FILE_ID", "KGS_ID", "CATALOG_URL", "DOWNLOAD_URL",
                  "DEPTH_START", "DEPTH_STOP", "FILE_SIZE_BYTES"),
    "CURVES": ("FILE_ID", "CURVE_POSITION", "MNEMONIC", "ORIGINAL_UNIT",
               "DESCRIPTION", "QUALITY_STATUS"),
    "MEASUREMENTS": ("FILE_ID", "DEPTH", "MNEMONIC", "VALUE"),
}


def _merge_conditions(table):
    keys = BUSINESS_KEYS[table]
    join = " AND ".join(f"r.{c} = s.{c}" for c in keys)
    comparisons = []
    for column in TABLE_COLUMNS[table]:
        if column in keys:
            continue
        left, right = f"r.{column}", f"s.{column}"
        if table == "WELLS" and column == "LOCATION":
            left = f"TRIM(REGEXP_REPLACE({left}, '[[:space:]]+', ' '))"
            right = f"TRIM(REGEXP_REPLACE({right}, '[[:space:]]+', ' '))"
        comparisons.append(f"{left} IS DISTINCT FROM {right}")
    return join, " OR ".join(comparisons)


def _publication_tables(target_tables=None, staging_tables=None):
    targets = dict(target_tables) if target_tables is not None else {
        table: f"{DATABASE}.{SCHEMA}.{table}" for table in FILES}
    staging = dict(staging_tables) if staging_tables is not None else {
        table: f"STG_{table}" for table in FILES}
    for mapping in (targets, staging):
        if set(mapping) != set(FILES):
            raise ValueError("Publication mappings must contain exactly the four tables")
        if any(not re.fullmatch(r"[A-Z_][A-Z0-9_]*(?:\.[A-Z_][A-Z0-9_]*){0,2}", name)
               for name in mapping.values()):
            raise ValueError("Invalid publication table identifier")
    if len(set(targets.values()) | set(staging.values())) != 8:
        raise ValueError("Publication source and target tables must be distinct")
    return targets, staging


def _validate_publication_keys(cursor, targets=None, staging=None):
    if targets is None or staging is None:
        targets, staging = _publication_tables()
    for table, keys in BUSINESS_KEYS.items():
        for source in (staging[table], targets[table]):
            nulls = " OR ".join(f"{key} IS NULL" for key in keys)
            cursor.execute(f"SELECT COUNT(*) FROM {source} WHERE {nulls}")
            if cursor.fetchone()[0]:
                raise ValueError(f"NULL business keys in {source}")
            cursor.execute(
                f"SELECT COUNT(*) FROM (SELECT {', '.join(keys)} FROM {source} "
                f"GROUP BY {', '.join(keys)} HAVING COUNT(*) > 1) invalid_keys"
            )
            if cursor.fetchone()[0]:
                raise ValueError(f"Duplicate business keys in {source}")


def publish_to_raw(connection, dry_run=True, *, target_tables=None, staging_tables=None):
    """Preview by default; atomically merge four tables only when explicitly enabled.

    Optional table mappings support isolated integration tests without changing defaults.
    Requires a dedicated, idle connection and staging prepared in this same session.
    No DDL or AUTOCOMMIT changes may occur between BEGIN and COMMIT: Snowflake
    implicitly commits on DDL. Callers must serialize publishers/other RAW writers;
    key preflight checks do not lock out concurrent writers in Snowflake.
    A failed commit is reported as failure even if its server outcome is unknown;
    rollback is attempted and an idempotent rerun can reconcile that outcome.
    """
    targets, staging = _publication_tables(target_tables, staging_tables)
    cursor = connection.cursor()
    report = {}
    transaction_started = False
    try:
        if not dry_run:
            # Arm cleanup before sending BEGIN: a lost response can mean the
            # server opened the transaction even though execute() raised.
            transaction_started = True
            cursor.execute("BEGIN TRANSACTION")
        _validate_publication_keys(cursor, targets, staging)
        for table in FILES:
            join, changed = _merge_conditions(table)
            raw = targets[table]
            cursor.execute(
                f"SELECT COUNT(*) FROM {staging[table]} s LEFT JOIN {raw} r ON {join} "
                f"WHERE r.{BUSINESS_KEYS[table][0]} IS NULL"
            )
            inserts = cursor.fetchone()[0]
            cursor.execute(
                f"SELECT COUNT(*) FROM {staging[table]} s JOIN {raw} r ON {join} "
                f"WHERE {changed}"
            )
            updates = cursor.fetchone()[0]
            report[table] = {"inserted": inserts, "updated": updates}
            print(f"PREVIEW {table}: inserts={inserts:,}, updates={updates:,}", flush=True)
        if dry_run:
            return report
        for table in FILES:
            join, changed = _merge_conditions(table)
            columns = TABLE_COLUMNS[table]
            assignments = ", ".join(
                f"{c} = s.{c}" for c in columns if c not in BUSINESS_KEYS[table]
            )
            cursor.execute(
                f"MERGE INTO {targets[table]} r USING {staging[table]} s ON {join} "
                f"WHEN MATCHED AND ({changed}) THEN UPDATE SET {assignments} "
                f"WHEN NOT MATCHED THEN INSERT ({', '.join(columns)}) "
                f"VALUES ({', '.join('s.' + c for c in columns)})"
            )
            # Snowflake MERGE returns named counts, not a reliable aggregate rowcount.
            names = [c[0].lower() for c in cursor.description]
            counts = dict(zip(names, cursor.fetchone()))
            report[table] = {
                "inserted": int(counts["number of rows inserted"]),
                "updated": int(counts["number of rows updated"]),
            }
        connection.commit()
        transaction_started = False
        for table, counts in report.items():
            print(f"COMMITTED {table}: inserts={counts['inserted']:,}, "
                  f"updates={counts['updated']:,}", flush=True)
        return report
    except BaseException:
        if transaction_started:
            try:
                connection.rollback()
            except Exception as rollback_error:
                print(f"Rollback failed: {type(rollback_error).__name__}; "
                      "publication outcome requires reconciliation", flush=True)
        raise
    finally:
        cursor.close()



def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage CSVs and preview incremental RAW publication")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publish", action="store_true", help="Explicitly commit four RAW MERGEs")
    mode.add_argument("--dry-run", action="store_true", help="Preview only (default)")
    args = parser.parse_args(argv)
    print("Starting Snowflake staging pipeline")

    validate_local_files()

    connection = connect_to_snowflake()

    try:
        inspect_snowflake(connection)

        upload_csv_files(connection)
        load_into_staging(connection)
        validate_staging(connection)
        validate_staging_keys(connection)
        compare_staging_to_raw(connection)
        diagnose_wells(connection)
        preview_merge(connection)
        publish_to_raw(connection, dry_run=not args.publish)
        print("Snowflake staging pipeline completed successfully.")
        print("RAW publication committed." if args.publish else "Existing RAW tables were not modified.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
