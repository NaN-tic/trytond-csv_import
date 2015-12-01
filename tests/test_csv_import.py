# This file is part of the csv_import module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class CsvImportTestCase(ModuleTestCase):
    'Test Csv Import module'
    module = 'csv_import'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CsvImportTestCase))
    return suite