# This file is part of csv_import module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.backend.sqlite.database import Database as SQLiteDatabase


class CSVImportTestCase(unittest.TestCase):
    'Test CSV Import module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('csv_import')

    def test0005views(self):
        'Test views'
        test_view('csv_import')

    def test0006depends(self):
        'Test depends'
        test_depends()


def doctest_dropdb(test):
    database = SQLiteDatabase().connect()
    cursor = database.cursor(autocommit=True)
    try:
        database.drop(cursor, ':memory:')
        cursor.commit()
    finally:
        cursor.close()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CSVImportTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_csv_import.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='UTF-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
