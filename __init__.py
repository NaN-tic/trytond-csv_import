# This file is part of csv_import module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from .csv_import import *


def register():
    Pool.register(
        CSVProfile,
        CSVArchive,
        CSVImport,
        BaseExternalMapping,
        module='csv_import', type_='model')
