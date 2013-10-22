===================
CSV Import Scenario
===================

Imports::

    >>> import datetime
    >>> import os
    >>> import shutil
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()
    >>> from trytond.config import CONFIG
    >>> CONFIG['data_path'] = '/tmp/trytond'

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install modules::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...         ('name', 'in', ('party', 'csv_import')),
    ...         ])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Init models::

    >>> Model = Model.get('ir.model')
    >>> Field = Model.get('ir.model.field')
    >>> Group = Model.get('res.group')
    >>> BaseExternalMapping = Model.get('base.external.mapping')
    >>> BaseExternalMappingLine = Model.get('base.external.mapping.line')

Create profile::

    >>> CSVProfile = Model.get('csv.profile')
    >>> profile = CSVProfile()
    >>> profile.name = 'Parties'
    >>> profile.model = Model.find([('model', '=', 'party.party')])[0]
    >>> profile.group =  Group.find([('name', '=', 'Administration')])[0]
    >>> profile.create_record = True
    >>> profile.csv_header = True
    >>> profile.csv_archive_separator = ','
    >>> profile.csv_quote = '"'
    >>> profile.save()

Create party mapping::

    >>> model_party = Model.find([('model', '=', 'party.party')])[0]
    >>> mapping = BaseExternalMapping()
    >>> mapping.name = 'party.csv'
    >>> mapping.model = model_party
    >>> mapping.state = 'done'
    >>> mapping.profile = profile
    >>> mapping_line = BaseExternalMappingLine()
    >>> mapping.mapping_lines.append(mapping_line)
    >>> mapping_line.sequence = 0
    >>> mapping_line.field = Field.find([
    ...     ('name', '=', 'name'),
    ...     ('model', '=', model_party.id),
    ...     ])[0]
    >>> mapping_line.external_field = 'name'
    >>> mapping_line.mapping_type = 'in_out'
    >>> mapping_line.external_type = 'str'
    >>> mapping_line = BaseExternalMappingLine()
    >>> mapping.mapping_lines.append(mapping_line)
    >>> mapping_line.sequence = 0
    >>> mapping_line.field = Field.find([
    ...     ('name', '=', 'addresses'),
    ...     ('model', '=', model_party.id),
    ...     ])[0]
    >>> mapping_line.external_field = 'name'
    >>> mapping_line.mapping_type = 'in_out'
    >>> mapping_line.external_type = 'str'
    >>> mapping_line.in_function = 'result = []'
    >>> mapping.save()

Create address mapping::

    >>> model_address = Model.find([('model', '=', 'party.address')])[0]
    >>> mapping2 = BaseExternalMapping()
    >>> mapping2.name = 'address.csv'
    >>> mapping2.model = model_address
    >>> mapping2.state = 'done'
    >>> mapping2.profile = profile
    >>> mapping_line = BaseExternalMappingLine()
    >>> mapping2.mapping_lines.append(mapping_line)
    >>> mapping_line.sequence = 1
    >>> mapping_line.field = Field.find([
    ...     ('name', '=', 'street'),
    ...     ('model', '=', model_address.id),
    ...     ])[0]
    >>> mapping_line.external_field = 'stree'
    >>> mapping_line.mapping_type = 'in_out'
    >>> mapping_line.external_type = 'str'
    >>> mapping_line = BaseExternalMappingLine()
    >>> mapping2.mapping_lines.append(mapping_line)
    >>> mapping_line.sequence = 2
    >>> mapping_line.field = Field.find([
    ...     ('name', '=', 'city'),
    ...     ('model', '=', model_address.id),
    ...     ])[0]
    >>> mapping_line.external_field = 'city'
    >>> mapping_line.mapping_type = 'in_out'
    >>> mapping_line.external_type = 'str'
    >>> mapping2.parent = mapping
    >>> mapping2.rel_field = Field.find([
    ...     ('name', '=', 'party'),
    ...     ('model', '=', model_address.id),
    ...     ])[0]
    >>> mapping2.save()

Create CSV archive::

    >>> srcfile = '%s/tests/%s' % (os.getcwd(), 'import_party.csv')
    >>> dstfile = '%s/:memory:/csv_import/%s' % (CONFIG.get('data_path'), 'import_party.csv')
    >>> shutil.copy(srcfile, dstfile)
    >>> CSVArchive = Model.get('csv.archive')
    >>> archive = CSVArchive()
    >>> archive.profile = profile
    >>> archive.archive_name = 'import_party.csv'
    >>> archive.save()
    >>> csv_import = CSVArchive.import_csv([archive.id], config.context)

Get CSV import::

    >>> CSVImport = Model.get('csv.import')
    >>> csv_import = CSVImport.find([])
    >>> len(csv_import)
    6

Get Party::

    >>> Party = Model.get('party.party')
    >>> party, = Party.find([('name', '=', 'Zikzakmedia')])
    >>> len(party.addresses)
    1

Create update profile::

    >>> CSVProfile = Model.get('csv.profile')
    >>> profile = CSVProfile()
    >>> profile.name = 'Update Parties'
    >>> profile.model = Model.find([('model', '=', 'party.party')])[0]
    >>> profile.group =  Group.find([('name', '=', 'Administration')])[0]
    >>> profile.create_record = False
    >>> profile.update_record = True
    >>> profile.code_internal = Field.find([
    ...     ('name', '=', 'name'),
    ...     ('model', '=', model_party.id),
    ...     ])[0]
    >>> profile.code_external = 0
    >>> profile.csv_header = True
    >>> profile.csv_archive_separator = ','
    >>> profile.csv_quote = '"'
    >>> profile.save()

Create update mapping::

    >>> model_party = Model.find([('model', '=', 'party.party')])[0]
    >>> mapping = BaseExternalMapping()
    >>> mapping.name = 'update-party.csv'
    >>> mapping.model = model_party
    >>> mapping.state = 'done'
    >>> mapping.profile = profile
    >>> mapping_line = BaseExternalMappingLine()
    >>> mapping.mapping_lines.append(mapping_line)
    >>> mapping_line.sequence = 0
    >>> mapping_line.field = Field.find([
    ...     ('name', '=', 'name'),
    ...     ('model', '=', model_party.id),
    ...     ])[0]
    >>> mapping_line.external_field = 'name'
    >>> mapping_line.mapping_type = 'in_out'
    >>> mapping_line.external_type = 'str'
    >>> mapping_line = BaseExternalMappingLine()
    >>> mapping.mapping_lines.append(mapping_line)
    >>> mapping_line.sequence = 1
    >>> mapping_line.field = Field.find([
    ...     ('name', '=', 'vat_number'),
    ...     ('model', '=', model_party.id),
    ...     ])[0]
    >>> mapping_line.external_field = 'vat_number'
    >>> mapping_line.mapping_type = 'in_out'
    >>> mapping_line.external_type = 'str'
    >>> mapping.save()

Create CSV update archive::

    >>> srcfile = '%s/tests/%s' % (os.getcwd(), 'update_party.csv')
    >>> dstfile = '%s/:memory:/csv_import/%s' % (CONFIG.get('data_path'), 'update_party.csv')
    >>> shutil.copy(srcfile, dstfile)
    >>> CSVArchive = Model.get('csv.archive')
    >>> archive = CSVArchive()
    >>> archive.profile = profile
    >>> archive.archive_name = 'update_party.csv'
    >>> archive.save()
    >>> csv_update = CSVArchive.import_csv([archive.id], config.context)

Get Party by vat::

    >>> Party = Model.get('party.party')
    >>> parties = Party.find([('vat_number', '=', '123456789A')])
    >>> len(parties)
    1