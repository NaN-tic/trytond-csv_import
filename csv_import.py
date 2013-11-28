# This file is part of csv_import module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from StringIO import StringIO
from csv import reader
from datetime import datetime
from email.mime.text import MIMEText
from trytond.config import CONFIG
from trytond.exceptions import UserError
from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.tools import get_smtp_server
from trytond.transaction import Transaction
import logging
import os
import re
import psycopg2
import unicodedata

__all__ = ['CSVProfile', 'CSVArchive', 'CSVImport', 'BaseExternalMapping']
__metaclass__ = PoolMeta
_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')


def slugify(value):
    if not isinstance(value, unicode):
        value = unicode(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(_slugify_strip_re.sub('', value).strip().lower())
    return _slugify_hyphenate_re.sub('-', value)


class CSVProfile(ModelSQL, ModelView):
    ' CSV Profile'
    __name__ = 'csv.profile'
    name = fields.Char('Name', required=True)
    archives = fields.One2Many('csv.archive', 'profile',
        'Archives')
    model = fields.Many2One('ir.model', 'Model', required=True)
    models = fields.One2Many('base.external.mapping', 'profile',
        'Model')
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
    active = fields.Boolean('Active')
    language = fields.Many2One('ir.lang', 'Language Default',
        help='Default language')
    group = fields.Many2One('res.group', 'Group', required=True,
        help='Group Users to notification')
    csv_header = fields.Boolean('Header',
        help='Header (field names) on archives')
    csv_archive_separator = fields.Selection([
            (',', 'Comma'),
            (';', 'Semicolon'),
            ('tab', 'Tabulator'),
            ('|', '|'),
            ], 'CSV Separator', help="Product archive CSV Separator",
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
    def default_code_external():
        return 0


class CSVArchive(Workflow, ModelSQL, ModelView):
    ' CSV Archive'
    __name__ = 'csv.archive'
    _rec_name = 'archive_name'
    profile = fields.Many2One('csv.profile', 'CSV Profile', ondelete='CASCADE',
        required=True, on_change=['profile'])
    date_archive = fields.DateTime('Date', required=True)
    data = fields.Function(fields.Binary('Archive', required=True),
        'get_data', setter='set_data')
    archive_name = fields.Char('Archive Name')
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
                'info': 'Information.',
                'error': 'CSV Import Error!',
                'archive_error': 'No csv archive found.\nPlease, select one.',
                'save_error': 'Error saving file! %s.',
                'format_error': 'CSV improperly formatted.',
                'reading_error': 'Error reading file %s.',
                'read_error': 'Error reading file: %s.\nError %s.',
                'reading_archive': 'Reading %s archive.',
                'mapping_error': 'Error in mapping template: %s.',
                'function_error': 'Function in CSV Profile has a mistake.\n'
                    'Please, review: %s.\n'
                    'See logs for more information.',
                'success_simulation': 'Simulation successfully.\n'
                    'Record %s not created nor updated.',
                'code_not_found': 'Code not found: Line: %s.',
                'record_saved': 'Record %s created successfully!',
                'record_error': 'Error creating %s.',
                'creation_error': 'Error creating record with values %s.'
                    '\nError raised: %s.',
                'record_already_exist': 'Record %s already exist.',
                'record_updated': 'Record %s of %s, updated with values %s!',
                'updating_error': 'Error updating %s of model %s!\n'
                    'Parent not found.',
                'cant_update': 'Unable to update %s because record %s not '
                    'found.\nIn order to allow updating, please uncheck '
                    '"Exclude update" field in the Base External Mapping '
                    'profile, or add more data in csv file to find this '
                    'record.',
                'notification': 'Import CSV notification from %s.',
                'new_record': 'There are new %s from %s. IDs: ',
                'not_default_email_configured': 'There is no default email '
                    'configured. Please, configure one.',
                'request_title': 'Import CSV file.',
                'sequence_error': 'Mapping line sequence not found',
                })

    def get_data(self, name):
        cursor = Transaction().cursor
        path = os.path.join(CONFIG.get('data_path', '/var/lib/trytond'),
            cursor.database_name, 'csv_import')
        archive = '%s/%s' % (path, self.archive_name.replace(' ', '_'))
        try:
            with open(archive, 'r') as f:
                return buffer(f.read())
        except IOError:
            self.raise_user_error('error',
                error_description='reading_error',
                error_description_args=(self.archive_name.replace(' ', '_'),),
                raise_exception=True)

    @classmethod
    def set_data(cls, archives, name, value):
        cursor = Transaction().cursor
        path = os.path.join(CONFIG.get('data_path', '/var/lib/trytond'),
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

    def on_change_profile(self):
        if not self.profile:
            return {'archive_name': None}
        today = Pool().get('ir.date').today()
        files = len(self.search([
                    ('archive_name', 'like', '%s_%s_%s.csv' %
                        (today, '%', slugify(self.profile.rec_name))),
                ]))
        return {
            'archive_name': ('%s_%s_%s.csv' %
                (today, files, slugify(self.profile.rec_name))),
            }

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
    def _add_default_values(cls, csv_model, values):
        """ This method is to be overridden and compute the default values
            of the model
        """
        pass

    @classmethod
    def _search_children(cls, csv_model, parent_record, values):
        """ This method is made to override itself and compute the children
            of the csv_model.model.model
        """
        return []

    @classmethod
    def _save_record(cls, csv_model, values, **kvargs):
        """ This method create one record recursively starting by the parent
            and following by its childs
            @param archive: Browseable instance of this model
            @param csv_model: Browseable instance of base.external.mapping
                model
            @param values: Dictionary of dictionaries with values to update.
                The outer key is used for identify the model, and
                the inner key is used for identify the field of this model.
            @param kvargs: A standard dictionary for contextual values
            @return: Return record created
        """

        if not values:
            return None
        if not kvargs:
            kvargs = {}

        pool = Pool()
        ExternalMapping = pool.get('base.external.mapping')
        model = csv_model.model.model
        ModelToImport = pool.get(model)

        now = datetime.now()
        profile = csv_model.profile
        parent = csv_model.parent
        comment = None
        record = None
        logger = logging.getLogger(__name__)

        if kvargs.get('record'):
            values[model][csv_model.rel_field.name] = kvargs['record']
        cls._add_default_values(csv_model, values)

        # Records already exist?
        records = []
        if kvargs['key_field'] in values[model]:
            records = ModelToImport.search([
                    (kvargs['key_field'], '=', kvargs['key_value']),
                    ])
        elif parent:
            records = cls._search_children(csv_model, kvargs['record'], values)

        if not records:
            try:
                record, = ModelToImport.create(
                    [values[model]])
                comment = cls.raise_user_error('record_saved',
                    error_args=(record,),
                    raise_exception=False)
                status = 'done'
            except psycopg2.ProgrammingError, e:
                Transaction().cursor.rollback()
                logger.error('Unable to create %s record: %s'
                    % (ModelToImport.__name__, e))
                cls.raise_user_error('creation_error',
                    error_args=(values[model], e))
            except UserError, e:
                logger.error('Unable to create %s record: %s'
                    % (ModelToImport.__name__, e[1][0]))
                cls.raise_user_error('creation_error',
                    error_args=(values.get(model), e))
            except Exception, e:
                logger.error('Unable to create %s record: %s'
                    % (ModelToImport.__name__, e))
        else:
            record, = records
            comment = cls.raise_user_error('record_already_exist',
                error_args=(record,),
                raise_exception=False)
            status = 'done'
        if comment:
            kvargs['log_vlist'].append({
                'create_date': now,
                'record': str(record),
                'status': status,
                'comment': comment,
                })
        children = ExternalMapping.search([
                ('profile', '=', profile.id),
                ('parent', '=', csv_model.id),
                ])
        for child in ExternalMapping.browse(children):
            cls._save_record(child, values, record=record,
                key_field=kvargs['key_field'],
                key_value=kvargs['key_value'],
                log_vlist=kvargs['log_vlist'])
        return record

    @classmethod
    def _update_record(cls, record, csv_model, values, **kvargs):
        """ This method updates one record recursively starting by the parent
            and following by its childs
            @param archive: Browseable instance of this model
            @param csv_model: Browseable instance of base.external.mapping
                model
            @param values: Dictionary of dictionaries with values to update.
                The outer key is used for identify the model, and
                the inner key is used for identify the field of this model.
            @param kvargs: A standard dictionary for contextual values
            @return: Return record updated
        """
        if not values:
            return None
        if not kvargs:
            kvargs = {}
        pool = Pool()
        now = datetime.now()
        model = csv_model.model.model
        ModelToUpdate = pool.get(model)
        ExternalMapping = pool.get('base.external.mapping')
        profile = csv_model.profile
        ModelToUpdate.write([record], values[model])
        comment = cls.raise_user_error('record_updated',
            error_args=(record.id, record.__name__, str(values[model])),
            raise_exception=False)
        status = 'done'
        kvargs['log_vlist'].append({
                'create_date': now,
                'record': str(record),
                'status': status,
                'comment': comment,
                })
        children_csv_model = ExternalMapping.search([
              ('profile', '=', profile.id),
              ('parent', '=', csv_model.id),
              ])
        # Now update its children
        for child_csv_model in ExternalMapping.browse(children_csv_model):
            child_records = cls._search_children(child_csv_model, record,
                values)
            if child_records:
                cls._update_record(child_records[0], child_csv_model, values,
                    log_vlist=kvargs['log_vlist'])
            else:
                cls.raise_user_error('cant_update',
                    error_args=(child_csv_model.model.model,
                        values[child_csv_model.model.model]))

    @classmethod
    @ModelView.button_action('csv_import.act_csv_import_with_domain')
    @Workflow.transition('done')
    def import_csv(cls, archives):
        pool = Pool()
        ExternalMapping = pool.get('base.external.mapping')
        CSVImport = pool.get('csv.import')
        User = pool.get('res.user')

        now = datetime.now()
        log_vlist = []
        context = {}

        for archive in archives:
            profile = archive.profile
            separator = profile.csv_archive_separator
            if separator == "tab":
                separator = '\t'
            quote = profile.csv_quote
            header = profile.csv_header

            external_mappings = profile.models
            field_key = profile.code_external

            ModelToImport = profile.model

            data = StringIO(archive.data)
            try:
                rows = reader(data, delimiter=str(separator),
                    quotechar=str(quote))
            except TypeError, e:
                log_vlist.append({
                    'create_date': now,
                    'status': 'error',
                    'comment': cls.raise_user_error('error',
                        error_description='read_error',
                        error_description_args=(archive.archive_name, e),
                        raise_exception=False),
                    'archive': archive
                    })
                CSVImport.create(log_vlist)
                return

            log_vlist.append({
                'create_date': now,
                'status': 'done',
                'comment': cls.raise_user_error('reading_archive',
                    error_args=(archive.archive_name),
                    raise_exception=False),
                })
            if header:
                rows.next()
            parent_models = ExternalMapping.search([('parent', '=', None)])

            send_mail = []
            csv_vals = {}
            new_records = []
            updated_records = []
            for row in rows:
                if not row:
                    continue
                for external_mapping in external_mappings:
                    if (not external_mapping.id in csv_vals
                            or external_mapping.required):
                        csv_vals[external_mapping.id] = {}
                    for l in external_mapping.mapping_lines:
                        if len(row) < l.sequence:
                            log_vlist.append({
                                'create_date': now,
                                'status': 'error',
                                'comment': cls.raise_user_error('format_error',
                                    raise_exception=False),
                                'archive': archive
                                })
                            CSVImport.create(log_vlist)
                            return
                        if row[l.sequence]:
                            csv_vals[external_mapping.id][l.external_field] = (
                                row[l.sequence])
                            if l.sequence == field_key:
                                code_external = row[l.sequence]

                if code_external:
                    try_vals = {}
                    for external_mapping in external_mappings:
                        try:
                            try_vals[external_mapping.model.model] = (
                                ExternalMapping.map_external_to_tryton(
                                    external_mapping.name,
                                    csv_vals[external_mapping.id],
                                    context))
                        except psycopg2.ProgrammingError, e:
                            cls.raise_user_error('mapping_error',
                                error_args=(e,))
                    for record in try_vals:
                        if not try_vals[record]:
                            log_vlist.append({
                                'create_date': now,
                                'status': 'error',
                                'comment': cls.raise_user_error(
                                    'function_error',
                                    error_args=(', '.join([x for x in
                                                csv_vals[external_mapping.id]]
                                            ),),
                                    raise_exception=False),
                                'archive': archive
                                })
                            CSVImport.create(log_vlist)
                            return
                        for field in try_vals[record]:
                            if try_vals[record][field] == code_external:
                                context.update({
                                        'key_field': field,
                                        'key_value': code_external,
                                        })
                                break

                    # Update records
                    if profile.update_record:
                        ModelToUpdate = pool.get(profile.model.model)
                        records = ModelToUpdate.search([
                                (profile.code_internal.name, '=', code_external)])
                        record = records[0] if records else None
                        if record:
                            updated_records.append(record)
                            for external_mapping in external_mappings:
                                try_vals[external_mapping.model.model] = (
                                    ExternalMapping.map_exclude_update(
                                        external_mapping.name,
                                        try_vals[external_mapping.model.model],))
                            for external_mapping in external_mappings:
                                if external_mapping in parent_models:
                                    cls._update_record(record,
                                            external_mapping,
                                            values=try_vals,
                                            log_vlist=log_vlist,
                                            key_field=context['key_field'],
                                            key_value=context['key_value'])
                                    send_mail.append(record)

                    # New records
                    if profile.create_record:
                        for external_mapping in external_mappings:
                            if external_mapping in parent_models:
                                new_record = cls._save_record(
                                        external_mapping,
                                        values=try_vals, record=False,
                                        log_vlist=log_vlist,
                                        key_field=context['key_field'],
                                        key_value=context['key_value'])
                                if new_record:
                                    new_records.append(new_record)
                                    send_mail.append(new_record)

                    if not profile.create_record and not profile.update_record:
                        log_vlist.append({
                            'create_date': now,
                            'status': 'done',
                            'comment': cls.raise_user_error(
                                'success_simulation',
                                error_args=(code_external,),
                                raise_exception=False),
                            })
                else:
                    log_vlist.append({
                        'create_date': now,
                        'status': 'error',
                        'comment': cls.raise_user_error(
                            'code_not_found',
                            error_args=(row,),
                            raise_exception=False),
                        'archive': archive
                        })
                    CSVImport.create(log_vlist)
                    return

            if send_mail:  # create mails for each user in the profile group
                users = User.search([('groups', '=', profile.group.id)])
                body = (cls.raise_user_error('new_record',
                        error_args=(send_mail[0].__name__,
                            profile.name),
                        raise_exception=False) +
                    ''.join([str(x.id) + '\n' for x in set(send_mail)]))
                subject = cls.raise_user_error('request_title',
                    raise_exception=False)
                from_addr = CONFIG.get('smtp_user', False)
                if not from_addr:
                    log_vlist.append({
                            'create_date': now,
                            'status': 'error',
                            'comment': cls.raise_user_error(
                                'not_default_email_configured',
                                raise_exception=False),
                            'archive': archive
                            })
                    continue
                msg = MIMEText(body.encode('utf-8'))
                msg['From'] = from_addr
                msg['Subject'] = subject
                logger = logging.getLogger(__name__)
                for user in users:
                    to_addr = user.email
                    if to_addr:
                        msg['To'] = to_addr
                        try:
                            server = get_smtp_server()
                            server.sendmail(from_addr, to_addr,
                                msg.as_string())
                            server.quit()
                        except Exception, e:
                            logger.error('Unable to deliver email (%s):\n %s'
                                % (e, msg.as_string()))

        cls.post_import(ModelToImport, list(set(new_records)))
        for log in log_vlist:
            log['archive'] = archive
        CSVImport.create(log_vlist)

    @classmethod
    def post_import(cls, model, records):
        """ This method is made to be overridden and execute something with
            imported records after import them. At the end of the inherited
            method, you must call this super method to make a commit.
            @param self: The object pointer
            @param cr: The database cursor,
            @param uid: The current user's ID for security checks.
            @param model: String with the name of the model where records are
                imported.
            @param new_records: List of ids of the created records.
            @param context: A standard dictionary for contextual values
        """
        pass

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


class CSVImport(ModelSQL, ModelView):
    ' CSV Import'
    __name__ = 'csv.import'
    _rec_name = 'create_date'
    create_date = fields.DateTime('Create Date', readonly=True)
    record = fields.Reference('Imported Record', selection='get_origin', readonly=True)
    status = fields.Selection([
            ('done', 'Done'),
            ('error', 'Error'),
            ], 'Status', readonly=True)
    comment = fields.Text('Comment', readonly=True)
    archive = fields.Many2One('csv.archive', 'Archive', readonly=True)

    @classmethod
    def __setup__(cls):
        super(CSVImport, cls).__setup__()
        cls._order.insert(0, ('create_date', 'DESC'))
        cls._order.insert(1, ('id', 'DESC'))

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = Model.search([])
        return [('', '')] + [(m.model, m.name) for m in models]


class BaseExternalMapping:
    __name__ = 'base.external.mapping'
    profile = fields.Many2One('csv.profile', 'CSV Profile')
    parent = fields.Many2One('base.external.mapping', 'Parent Model')
    rel_field = fields.Many2One('ir.model.field', 'Related Field')
    required = fields.Boolean('Required', help='Avoid blank rows in csv file. '
        'If not, the previous row is given.')
