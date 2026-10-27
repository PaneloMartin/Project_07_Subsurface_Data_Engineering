"""Offline checks for the opt-in Snowflake integration harness."""
import importlib.util
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch

from test_publish_to_raw import loader, LocalConnection, LocalCursor

spec = importlib.util.spec_from_file_location(
    'integration_harness', Path(__file__).with_name('snowflake_merge_integration.py'))
harness = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'ingestion.load_snowflake': loader}):
    spec.loader.exec_module(harness)


class HarnessCursor(LocalCursor):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def execute(self, sql, params=None):
        if sql.startswith('SHOW '):
            if sql.startswith('SHOW SCHEMAS'):
                names, rows = ['name'], [('TESTING',)]
            else:
                names = ['name', 'kind', 'comment', 'database_name', 'schema_name']
                existing = {row[0] for row in self.connection.db.execute(
                    "SELECT name FROM sqlite_temp_master UNION SELECT name FROM sqlite_master")}
                rows = [(name, 'TEMPORARY', marker, 'SUBSURFACE_DB', 'TESTING')
                        for name, marker in getattr(self.connection, 'markers', {}).items()
                        if name in existing]
            self.description = [(name,) for name in names]
            self.metadata_rows = rows
            return self
        self.metadata_rows = None
        if sql.startswith('CREATE TEMPORARY TABLE '):
            sql, marker = sql.split(' COMMENT = ')
            if not hasattr(self.connection, 'markers'):
                self.connection.markers = {}
            self.connection.markers[sql.split()[3].split('.')[-1]] = marker.strip("'")
        if sql.startswith('CREATE SCHEMA '):
            self.connection.statements.append(sql)
            return self
        self.assert_isolated(sql)
        sql = sql.replace(harness.NAMESPACE + '.', '').replace('%s', '?')
        if sql.startswith(('MERGE', 'BEGIN')) or sql.startswith('SELECT COUNT(*)'):
            return super().execute(sql)
        self.connection.statements.append(sql)
        self.inner = self.connection.db.execute(sql, params or ())
        return self

    def assert_isolated(self, sql):
        if 'SUBSURFACE_DB.RAW' in sql:
            raise AssertionError('Unexpected productive identifier')

    def executemany(self, sql, params):
        self.assert_isolated(sql)
        sql = sql.replace(harness.NAMESPACE + '.', '').replace('%s', '?')
        self.connection.db.executemany(sql, params)

    def fetchall(self):
        if self.metadata_rows is not None:
            return self.metadata_rows
        return self.inner.fetchall()


class HarnessConnection(LocalConnection):
    def cursor(self):
        return HarnessCursor(self)


class IntegrationHarnessTests(unittest.TestCase):
    def test_full_harness_offline(self):
        c = HarnessConnection()
        with patch.object(loader.snowflake.connector, 'Error', sqlite3.Error, create=True):
            harness.run(c)
        self.assertEqual(sum(s.startswith('DROP TABLE') for s in c.statements), 8)

    def test_opt_in_required_before_connect(self):
        with patch.object(loader, 'connect_to_snowflake') as connect:
            harness.main([])
            connect.assert_not_called()

    def test_unique_isolated_names(self):
        a, b = harness.table_names()
        c, d = harness.table_names()
        self.assertEqual(len(set(a.values()) | set(b.values()) | set(c.values()) | set(d.values())), 16)
        self.assertTrue(all(n.startswith('SUBSURFACE_DB.TESTING.IT_MERGE_')
                            for mapping in (a, b, c, d) for n in mapping.values()))

    def test_invalid_mapping_rejected_before_cursor(self):
        from unittest.mock import Mock
        for mapping in ({}, {t: 'X;DROP TABLE Y' for t in loader.FILES},
                        {t: 'SAME' for t in loader.FILES}):
            c = Mock()
            with self.assertRaises(ValueError):
                loader.publish_to_raw(c, False, target_tables=mapping)
            c.cursor.assert_not_called()


if __name__ == '__main__':
    unittest.main()

