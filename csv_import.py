# This file is part of csv_import module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import os
import re
import unicodedata
import string
import csv
from io import StringIO
from datetime import datetime
from trytond.config import config
from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError


__all__ = ['BaseExternalMapping',
    'CSVProfile', 'CSVProfileBaseExternalMapping', 'CSVArchive']


def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = re.sub('[^\w\s-]', '', value.decode('utf-8')).strip().lower()
    return re.sub('[-\s]+', '-', value)


class BaseExternalMapping(metaclass=PoolMeta):
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
        cls._order = [
            ('date_archive', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._transitions |= set((
                ('draft', 'done'),
                ('draft', 'canceled'),
                ('canceled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state') != 'canceled',
                    'depends': ['state'],
                    },
                'import_csv': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    def get_data(self, name):
        path = os.path.join(config.get('database', 'path'),
            Transaction().database.name, 'csv_import')
        archive = '%s/%s' % (path, self.archive_name.replace(' ', '_'))
        try:
            with open(archive, 'rb') as f:
                return fields.Binary.cast(f.read())
        except IOError:
            pass

    @classmethod
    def set_data(cls, archives, name, value):
        path = os.path.join(config.get('database', 'path'),
            Transaction().database.name, 'csv_import')
        if not os.path.exists(path):
            os.makedirs(path, mode=0o777)
        for archive in archives:
            archive = '%s/%s' % (path, archive.archive_name.replace(' ', '_'))
            try:
                with open(archive, 'wb') as f:
                    f.write(value)
            except IOError:
                raise UserError(gettext('csv_import.msg_error'))

    @fields.depends('profile', '_parent_profile.rec_name')
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
    def _import_data_sale(cls, record, values, parent_values=None):
        '''
        Sale and Sale Line data
        '''
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        Party = pool.get('party.party')

        record_name = record.__name__

        if record_name == 'sale.sale':
            party = values.get('party')

            if party:
                party = Party(party)

                if not record.id:
                    record = Sale.get_sale_data(values.get('party'))

                    if hasattr(record, 'shop') and not getattr(record, 'shop'):
                        shop, = pool.get('sale.shop').search([], limit=1)
                        record.shop = shop

                if values.get('invoice_address') \
                        and values.get('invoice_address') in party.addresses:
                    record.invoice_address = values.get('invoice_address')

                if values.get('shipment_address') \
                        and values.get('shipment_address') in party.addresses:
                    record.shipment_address = values.get('shipment_address')

                if values.get('customer_reference'):
                    record.customer_reference = values.get('customer_reference')

                if values.get('lines'):
                    record.lines = values.get('lines')

                return record

        if record_name == 'sale.line':
            if values.get('product') and values.get('quantity'):
                sale = Sale.get_sale_data(parent_values.get('party'))
                line = SaleLine.get_sale_line_data(
                            sale,
                            values.get('product'),
                            values.get('quantity')
                            )
                line.on_change_product()

                return line

        return record

    @classmethod
    def _import_data_purchase(cls, record, values, parent_values=None):
        '''
        Purchase and Purchase Line data
        '''
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        Party = pool.get('party.party')

        record_name = record.__name__

        if record_name == 'purchase.purchase':
            party = values.get('party')

            if party:
                party = Party(party)

                if not record.id:
                    default_values = record.default_get(record._fields.keys(),
                        with_rec_name=False)
                    for key, value in default_values.items():
                        setattr(record, key, value)
                    record.party = party
                record.on_change_party()

                if values.get('invoice_address') \
                        and values.get('invoice_address') in party.addresses:
                    record.invoice_address = values.get('invoice_address')

                if values.get('lines'):
                    record.lines = values.get('lines')

                return record

        if record_name == 'purchase.line':
            if values.get('product') and values.get('quantity'):
                purchase = Purchase()
                default_values = Purchase.default_get(Purchase._fields.keys(),
                        with_rec_name=False)
                for key, value in default_values.items():
                    setattr(purchase, key, value)
                purchase.party = parent_values.get('party')
                purchase.on_change_party()

                record.purchase = purchase
                record.product = values.get('product')
                record.quantity = values.get('quantity')
                record.on_change_product()

                return record

        return record

    @classmethod
    def _import_data(cls, record, values, parent_values=None):
        '''Load _import_data_modelname or seattr from dict'''
        method_data = '_import_data_%s' % record.__name__.split('.')[0]

        if hasattr(cls, method_data):
            import_data = getattr(cls, method_data)
            record = import_data(record, values, parent_values)
        for k, v in values.items():
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

        try:
            data = StringIO(archive.data.decode('utf8'))
        except UnicodeDecodeError as error:
            cls.write([archive], {'logs': 'Error - %s' % (
                gettext('csv_import.msg_read_error',
                    filename=archive.archive_name.replace(' ', '_'),
                    error=error)
                )})
            return None, None
        try:
            reader = csv.reader(data, delimiter=str(separator),
                quotechar=str(quote))
        except TypeError as error:
            cls.write([archive], {'logs': 'Error - %s' % (
                gettext('csv_import.msg_read_error',
                    filename=archive.archive_name.replace(' ', '_'),
                    error=error)
                )})
            return None, None

        if header:
            # TODO. Know why some header columns get ""
            headers = ["".join(list(filter(lambda x: x in string.printable,
                x.replace('"', '')))) for x in next(reader)]
        return reader, headers

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

            if not profile.create_record and not profile.update_record or not archive.data:
                continue

            reader, headers = cls._read_csv_file(archive)
            if not reader:
                continue

            base_model = profile.model.model

            child_mappings = []
            for mapping in profile.mappings:
                if not mapping.model.model == base_model:
                    child_mappings.append(mapping)
                else:
                    base_mapping = mapping
            if not base_mapping:
                logs.append(gettext('csv_import.msg_not_mapping',
                    profile=profile.rec_name))
                continue

            new_records = []
            new_lines = []
            rows = list(reader)
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
                    if not list(base_values.values())[0] == '':
                        new_lines = []

                #get values child models
                child_values = None
                child_rel_field = None
                for child in child_mappings:
                    if not child.csv_rel_field:
                        logs.append(gettext('csv_import.msg_missing_rel_field',
                            mapping=child.rec_name))
                        continue
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

                # next row is empty first value, is a new line. Continue
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
                    logs.append(gettext('csv_import.msg_not_create_update',
                        line=i + 1))
                    continue

                #get default values from base model
                record = cls._import_data(record, base_values)

                #save - not testing
                if not profile.testing:
                    record.save()  # save or update
                    logs.append(gettext('csv_import.msg_record_saved',
                        record=record.id))
                    new_records.append(record.id)

            if profile.testing:
                logs.append(gettext('csv_import.msg_success_simulation'))

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
