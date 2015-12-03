# This file is part of csv_import module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from StringIO import StringIO
from csv import reader
from datetime import datetime
from trytond.config import config
from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
import os
import re
import unicodedata
import string


__all__ = ['BaseExternalMapping',
    'CSVProfile', 'CSVProfileBaseExternalMapping', 'CSVArchive']
__metaclass__ = PoolMeta
_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')


def slugify(value):
    if not isinstance(value, unicode):
        value = unicode(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(_slugify_strip_re.sub('', value).strip().lower())
    return _slugify_hyphenate_re.sub('-', value)


class BaseExternalMapping:
    __name__ = 'base.external.mapping'
    csv_mapping = fields.Many2One('base.external.mapping', 'CSV Mapping')
    csv_rel_field = fields.Many2One('ir.model.field', 'CSV Field related')


class CSVProfile(ModelSQL, ModelView):
    'CSV Profile'
    __name__ = 'csv.profile'
    name = fields.Char('Name', required=True)
    archives = fields.One2Many('csv.archive', 'profile',
        'Archives')
    model = fields.Many2One('ir.model', 'Model', required=True)
    mappings = fields.Many2Many('csv.profile-base.external.mapping',
        'profile', 'mapping', 'Mappings', required=True)
    code_internal = fields.Many2One('ir.model.field', 'Tryton Code Field',
        domain=[('model', '=', Eval('model'))],
        states={
            'invisible': ~Eval('update_record', True),
            'required': Eval('update_record', True),
        }, depends=['model', 'update_record'],
        help='Code field in Tryton.')
    code_external = fields.Integer("CSV Code Field",
        states={
            'invisible': ~Eval('update_record', True),
            'required': Eval('update_record', True),
        }, depends=['model', 'update_record'],
        help='Code field in CSV column.')
    create_record = fields.Boolean('Create', help='Create record from CSV')
    update_record = fields.Boolean('Update', help='Update record from CSV')
    testing = fields.Boolean('Testing', help='Not create or update records')
    active = fields.Boolean('Active')
    csv_header = fields.Boolean('Header',
        help='Header (field names) on archives')
    csv_archive_separator = fields.Selection([
            (',', 'Comma'),
            (';', 'Semicolon'),
            ('tab', 'Tabulator'),
            ('|', '|'),
            ], 'CSV Separator', help="Archive CSV Separator",
        required=True)
    csv_quote = fields.Char('Quote', required=True,
        help='Character to use as quote')
    note = fields.Text('Notes')

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_create_record():
        return True

    @staticmethod
    def default_update_record():
        return False

    @staticmethod
    def default_csv_header():
        return True

    @staticmethod
    def default_csv_archive_separator():
        return ","

    @staticmethod
    def default_csv_quote():
        return '"'

    @staticmethod
    def default_code_external():
        return 0


class CSVProfileBaseExternalMapping(ModelSQL):
    'CSV Profile - Base External Mapping'
    __name__ = 'csv.profile-base.external.mapping'
    _table = 'csv_profile_mapping_rel'
    profile = fields.Many2One('csv.profile', 'Profile',
            ondelete='CASCADE', select=True, required=True)
    mapping = fields.Many2One('base.external.mapping', 'Mapping',
        ondelete='RESTRICT', required=True)


class CSVArchive(Workflow, ModelSQL, ModelView):
    'CSV Archive'
    __name__ = 'csv.archive'
    _rec_name = 'archive_name'
    profile = fields.Many2One('csv.profile', 'CSV Profile', ondelete='CASCADE',
        required=True)
    date_archive = fields.DateTime('Date', required=True)
    data = fields.Function(fields.Binary('Archive', filename='archive_name',
        required=True), 'get_data', setter='set_data')
    archive_name = fields.Char('Archive Name')
    logs = fields.Text("Logs", readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('done', 'Done'),
            ('canceled', 'Canceled'),
            ], 'State', required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(CSVArchive, cls).__setup__()
        cls._order.insert(0, ('date_archive', 'DESC'))
        cls._order.insert(1, ('id', 'DESC'))
        cls._transitions |= set((
                ('draft', 'done'),
                ('draft', 'canceled'),
                ('canceled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'draft',
                    },
                'draft': {
                    'invisible': Eval('state') != 'canceled',
                    'icon': If(Eval('state') == 'canceled', 'tryton-clear',
                        'tryton-go-previous'),
                    },
                'import_csv': {
                    'invisible': Eval('state') != 'draft',
                    },
                })
        cls._error_messages.update({
                'error': 'CSV Import Error!',
                'reading_error': 'Error reading file %s.',
                'read_error': 'Error reading file: %s.\nError %s.',
                'success_simulation': 'Simulation successfully.',
                'record_saved': 'Record ID %s saved successfully!',
                'record_error': 'Error saving records.',
                'not_create_update': 'Not create or update line %s',
                })

    def get_data(self, name):
        cursor = Transaction().cursor
        path = os.path.join(config.get('database', 'path'),
            cursor.database_name, 'csv_import')
        archive = '%s/%s' % (path, self.archive_name.replace(' ', '_'))
        try:
            with open(archive, 'r') as f:
                return fields.Binary.cast(f.read())
        except IOError:
            self.raise_user_error('error',
                error_description='reading_error',
                error_description_args=(self.archive_name.replace(' ', '_'),),
                raise_exception=True)

    @classmethod
    def set_data(cls, archives, name, value):
        cursor = Transaction().cursor
        path = os.path.join(config.get('database', 'path'),
            cursor.database_name, 'csv_import')
        if not os.path.exists(path):
            os.makedirs(path, mode=0777)
        for archive in archives:
            archive = '%s/%s' % (path, archive.archive_name.replace(' ', '_'))
            try:
                with open(archive, 'w') as f:
                    f.write(value)
            except IOError, e:
                cls.raise_user_error('error',
                    error_description='save_error',
                    error_description_args=(e,),
                    raise_exception=True)

    @fields.depends('profile')
    def on_change_profile(self):
        if self.profile:
            today = Pool().get('ir.date').today()
            files = len(self.search([
                        ('archive_name', 'like', '%s_%s_%s.csv' %
                            (today, '%', slugify(self.profile.rec_name))),
                    ]))
            self.archive_name = '%s_%s_%s.csv' % \
                    (today, files, slugify(self.profile.rec_name))
        else:
            self.archive_name = None

    @staticmethod
    def default_date_archive():
        return datetime.now()

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_profile():
        CSVProfile = Pool().get('csv.profile')
        csv_profiles = CSVProfile.search([])
        if len(csv_profiles) == 1:
            return csv_profiles[0].id

    @classmethod
    def _import_data(cls, record, values, parent_values=None):
        '''Load _import_data_modelname or seattr from dict'''
        method_data = '_import_data_%s' % record.__name__.split('.')[0]

        if hasattr(cls, method_data):
            import_data = getattr(cls, method_data)
            return import_data(record, values, parent_values)
        else:
            for k, v in values.iteritems():
                setattr(record, k, v)
            return record

    @classmethod
    def post_import(cls, profile, records):
        """ This method is made to be overridden and execute something with
            imported records after import them. At the end of the inherited
            @param profile: profile object
            @param records: List of id records.
        """
        pass

    @classmethod
    def _read_csv_file(cls, archive):
        '''Read CSV data from archive'''
        headers = None
        profile = archive.profile

        separator = profile.csv_archive_separator
        if separator == "tab":
            separator = '\t'
        quote = profile.csv_quote
        header = profile.csv_header

        data = StringIO(archive.data)
        try:
            rows = reader(data, delimiter=str(separator),
                quotechar=str(quote))

        except TypeError, e:
            cls.write([archive], {'logs': 'Error - %s' % (
                cls.raise_user_error('error',
                    error_description='read_error',
                    error_description_args=(archive.archive_name, e),
                    raise_exception=False),
                )})
            return

        if header:  # TODO. Know why some header columns get ""
            headers = [filter(lambda x: x in string.printable, x
                    ).replace('"', '')
                for x in next(rows)]
        return rows, headers

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def import_csv(cls, archives):
        '''
        Process archives to import data from CSV files
        base: base model, e.g: party
        childs: new lines related a base, e.g: addresses
        '''
        pool = Pool()
        ExternalMapping = pool.get('base.external.mapping')

        logs = []
        for archive in archives:
            profile = archive.profile

            if not profile.create_record and not profile.update_record:
                continue

            data, headers = cls._read_csv_file(archive)

            base_model = profile.model.model

            child_mappings = []
            for mapping in profile.mappings:
                if not mapping.model.model == base_model:
                    child_mappings.append(mapping)
                else:
                    base_mapping = mapping

            new_records = []
            new_lines = []
            rows = list(data)
            Base = pool.get(base_model)
            for i in range(len(rows)):
                row = rows[i]
                if not row:
                    continue

                #join header and row to convert a list to dict {header: value}
                vals = dict(zip(headers, row))

                #get values base model
                if not new_lines:
                    base_values = ExternalMapping.map_external_to_tryton(
                            base_mapping.name, vals)
                    if not base_values.values()[0] == '':
                        new_lines = []

                #get values child models
                child_values = None
                child_rel_field = None
                for child in child_mappings:
                    child_rel_field = child.csv_rel_field.name
                    child_values = ExternalMapping.map_external_to_tryton(
                            child.name, vals)
                    Child = pool.get(child.model.model)
                    child = Child()
                    # get default values in child model
                    child_values = cls._import_data(child, child_values,
                        base_values)
                    new_lines.append(child_values)

                if child_rel_field:
                    base_values[child_rel_field] = new_lines

                #next row is empty first value, is a new line. Continue
                if i < len(rows) - 1:
                    if rows[i + 1]:
                        if rows[i + 1][0] == '':
                            continue
                        else:
                            new_lines = []

                #create object or get object exist
                record = None
                records = None
                if profile.update_record:
                    val = row[profile.code_external]
                    records = Base.search([
                            (profile.code_internal.name, '=', val)
                            ])
                    if records:
                        record = Base(records[0])
                if profile.create_record and not records:
                    record = Base()

                if not record:
                    logs.append(cls.raise_user_error('not_create_update',
                        error_args=(i + 1,), raise_exception=False))
                    continue

                #get default values from base model
                record = cls._import_data(record, base_values)

                #save - not testing
                if not profile.testing:
                    record.save()  # save or update
                    logs.append(cls.raise_user_error('record_saved',
                        error_args=(record.id,), raise_exception=False))
                    new_records.append(record.id)

            if profile.testing:
                logs.append(cls.raise_user_error('success_simulation',
                    raise_exception=False))

            cls.post_import(profile, new_records)
            cls.write([archive], {'logs': '\n'.join(logs)})

    @classmethod
    def copy(cls, archives, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['logs'] = None
        return super(CSVArchive, cls).copy(archives, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, archives):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('canceled')
    def cancel(cls, archives):
        pass
