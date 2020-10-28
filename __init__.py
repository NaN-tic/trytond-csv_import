# This file is part of csv_import module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import csv_import


def register():
    Pool.register(
        csv_import.CSVProfile,
        csv_import.CSVProfileBaseExternalMapping,
        csv_import.CSVArchive,
        csv_import.BaseExternalMapping,
        module='csv_import', type_='model')
