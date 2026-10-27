"""Opt-in Snowflake integration harness; no CSV/RAW reads or writes."""
import argparse
import re
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion import load_snowflake as loader

NAMESPACE = 'SUBSURFACE_DB.TESTING'
NUMERIC = {'LATITUDE', 'LONGITUDE', 'ELEVATION', 'DEPTH_START', 'DEPTH_STOP',
           'FILE_SIZE_BYTES', 'CURVE_POSITION', 'DEPTH', 'VALUE'}
CHANGE_COLUMN = {'WELLS': 'API', 'LOG_FILES': 'CATALOG_URL',
                 'CURVES': 'DESCRIPTION', 'MEASUREMENTS': 'VALUE'}


def table_names():
    prefix = 'IT_MERGE_' + uuid4().hex.upper()
    targets = {t: f'{NAMESPACE}.{prefix}_{t}' for t in loader.FILES}
    staging = {t: f'{NAMESPACE}.{prefix}_STG_{t}' for t in loader.FILES}
    return targets, staging


def fixtures(table):
    columns = loader.TABLE_COLUMNS[table]
    baseline, staged, expected = [], [], []
    for index in range(1, 7):
        old = {c: (index if c in NUMERIC else f'{c}_{index}') for c in columns}
        if table == 'WELLS':
            old['LOCATION'] = ' A  B '
        new = dict(old)
        change = CHANGE_COLUMN[table]
        if index == 2:
            new[change] = 99 if change in NUMERIC else 'changed'
        elif index == 3:
            new[change] = None
        elif index == 4:
            old[change] = None
        elif index == 5 and table == 'WELLS':
            new['LOCATION'] = '\tA B\n'
        if index < 6:
            baseline.append(old)
        staged.append(new)
        expected.append(old if index == 5 else new)
    return baseline, staged, expected


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def snapshot(connection, names):
    result = {}
    with connection.cursor() as cursor:
        for table, name in names.items():
            cursor.execute(f"SELECT {', '.join(loader.TABLE_COLUMNS[table])} FROM {name} "
                           f"ORDER BY {', '.join(loader.BUSINESS_KEYS[table])}")
            result[table] = cursor.fetchall()
    return result


class FailFourthMerge:
    """Delegate all work, but cause a real server SQL error before MERGE four."""
    def __init__(self, connection):
        self.connection = connection
        self.merges = 0
        self.injected = False
        self.rollbacks = 0

    def cursor(self):
        return FailingCursor(self, self.connection.cursor())

    def commit(self):
        return self.connection.commit()

    def rollback(self):
        self.rollbacks += 1
        return self.connection.rollback()


class FailingCursor:
    def __init__(self, owner, cursor):
        self.owner, self.inner = owner, cursor

    def execute(self, sql):
        if sql.startswith('MERGE INTO '):
            self.owner.merges += 1
            if self.owner.merges == 4:
                self.owner.injected = True
                self.inner.execute("SELECT TO_NUMBER('INTENTIONAL_MERGE_TEST_FAILURE')")
                raise AssertionError('Expected Snowflake conversion error')
        return self.inner.execute(sql)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def _show(cursor, sql):
    cursor.execute(sql)
    names = [column[0].lower() for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _objects(connection):
    with connection.cursor() as cursor:
        schemas = _show(cursor, "SHOW SCHEMAS IN DATABASE SUBSURFACE_DB")
        if not any(row['name'] == 'TESTING' for row in schemas):
            return set()
        return {row['name'] for row in _show(cursor, f"SHOW OBJECTS IN SCHEMA {NAMESPACE}")}


def _cleanup(connection, attempted, marker):
    """Never drop by name alone. Failed CREATE replies are treated as uncertain.

    If the connection is lost during CREATE, the table may exist server-side even
    though execute raised. Its name was logged before sending CREATE. We verify
    the atomic CREATE comment and TEMPORARY kind before DROP, or report it pending.
    No reconnection is used: temporary tables belong to the original session and
    disappear when that server session ends (not necessarily at network loss).
    """
    pending = []
    errors = []
    try:
        connection.rollback()
    except Exception as error:
        errors.append(f"rollback: {type(error).__name__}")
    for name in reversed(attempted):
        try:
            with connection.cursor() as cursor:
                rows = _show(cursor, f"SHOW TABLES IN SCHEMA {NAMESPACE}")
                matches = [row for row in rows if row['name'] == name.rsplit('.', 1)[1]]
                if not matches:
                    # Could be an uncertain creation or an invisible object: do not DROP.
                    pending.append(name)
                    continue
                require(len(matches) == 1 and matches[0].get('kind') == 'TEMPORARY'
                        and matches[0].get('comment') == marker
                        and matches[0].get('database_name') == 'SUBSURFACE_DB'
                        and matches[0].get('schema_name') == 'TESTING',
                        f"Ownership not verified: {name}")
                cursor.execute(f'DROP TABLE {name}')
        except Exception as error:
            pending.append(name)
            errors.append(f"{name}: {type(error).__name__}")
    if pending or errors:
        print(f"CLEANUP WARNING {marker}: pending/unverified={pending}; errors={errors}",
              flush=True)
    return pending, errors


def run(connection):
    targets, staging = table_names()
    loader._publication_tables(targets, staging)
    planned = list(targets.values()) + list(staging.values())
    require(len(planned) == 8 and len(set(planned)) == 8, 'Expected eight distinct tables')
    for name in planned:
        require(re.fullmatch(r'SUBSURFACE_DB\.TESTING\.IT_MERGE_[A-F0-9]{32}_(?:STG_)?(?:WELLS|LOG_FILES|CURVES|MEASUREMENTS)', name),
                f'Unsafe test destination: {name}')
    run_id = targets['WELLS'].split('.')[-1].removeprefix('IT_MERGE_').removesuffix('_WELLS')
    require(all(name.startswith(f'{NAMESPACE}.IT_MERGE_{run_id}_') for name in planned),
            'Mixed execution identifiers')
    marker = f'PROJECT07_INTEGRATION_{run_id}'
    print(f'RUN_ID={run_id}', flush=True)
    for name in planned:
        print(f'PLANNED_TABLE={name}', flush=True)
    # Fail closed on metadata/permission errors, before any object creation.
    existing = _objects(connection)
    require(not existing.intersection(name.rsplit('.', 1)[1] for name in planned),
            'Test name collision: aborting without changing existing objects')
    attempted = []
    primary_error = False
    try:
        with connection.cursor() as cursor:
            # All DDL precedes publication. Only this fixed testing namespace is used.
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {NAMESPACE}')
            for table in loader.FILES:
                definitions = ', '.join(
                    f'{c} {"NUMBER(20, 4)" if c in NUMERIC else "VARCHAR"}'
                    for c in loader.TABLE_COLUMNS[table])
                for name in (targets[table], staging[table]):
                    # Recheck immediately before CREATE; no OR REPLACE / IF NOT EXISTS.
                    require(name.rsplit('.', 1)[1] not in _objects(connection),
                            f'Test name collision: {name}')
                    attempted.append(name)
                    cursor.execute(f"CREATE TEMPORARY TABLE {name} ({definitions}) COMMENT = '{marker}'")
                baseline, staged, _ = fixtures(table)
                for name, rows in ((targets[table], baseline), (staging[table], staged)):
                    columns = loader.TABLE_COLUMNS[table]
                    cursor.executemany(
                        f"INSERT INTO {name} ({', '.join(columns)}) VALUES "
                        f"({', '.join('%s' for _ in columns)})",
                        [tuple(row[c] for c in columns) for row in rows])
        connection.commit()
        kwargs = dict(target_tables=targets, staging_tables=staging)
        before = snapshot(connection, targets)
        expected_counts = {t: {'inserted': 1, 'updated': 3} for t in loader.FILES}
        require(loader.publish_to_raw(connection, **kwargs) == expected_counts, 'Preview counts')
        require(snapshot(connection, targets) == before, 'Dry run changed test targets')
        require(loader.publish_to_raw(connection, False, **kwargs) == expected_counts, 'MERGE counts')
        expected_rows = {}
        for table in loader.FILES:
            _, _, expected = fixtures(table)
            expected.sort(key=lambda row: tuple(row[k] for k in loader.BUSINESS_KEYS[table]))
            expected_rows[table] = [tuple(row[c] for c in loader.TABLE_COLUMNS[table]) for row in expected]
        after = snapshot(connection, targets)
        require(after == expected_rows, 'Stored values/NULLs/unchanged rows/LOCATION mismatch')
        zero = {t: {'inserted': 0, 'updated': 0} for t in loader.FILES}
        require(loader.publish_to_raw(connection, False, **kwargs) == zero, 'Second MERGE not idempotent')
        require(snapshot(connection, targets) == after, 'Second MERGE changed values')
        with connection.cursor() as cursor:
            for table, name in staging.items():
                column = CHANGE_COLUMN[table]
                cursor.execute(f'UPDATE {name} SET {column} = %s',
                               (777 if column in NUMERIC else 'rollback_candidate',))
        connection.commit()
        failing = FailFourthMerge(connection)
        try:
            loader.publish_to_raw(failing, False, **kwargs)
        except loader.snowflake.connector.Error:
            require(failing.injected and failing.merges == 4, 'Unexpected server error')
        else:
            raise AssertionError('Injected error did not propagate')
        require(failing.rollbacks == 1, 'Rollback was not called exactly once')
        require(snapshot(connection, targets) == after, 'Rollback left partial changes')
        print('PASS: inserts=1, updates=3 per table; values, NULLs, LOCATION, idempotence, rollback')
    except BaseException:
        primary_error = True
        raise
    finally:
        pending, errors = _cleanup(connection, attempted, marker)
        if (pending or errors) and not primary_error:
            raise RuntimeError('Integration cleanup incomplete; see RUN_ID and pending objects above')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-snowflake', action='store_true',
                        help='Explicitly allow creation and writes to isolated TESTING objects')
    args = parser.parse_args(argv)
    if not args.run_snowflake:
        print('Not executed. Use --run-snowflake only after authorization; creates TESTING objects.')
        return
    connection = loader.connect_to_snowflake()
    try:
        run(connection)
    finally:
        connection.close()


if __name__ == '__main__':
    main()
