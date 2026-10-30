from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class DailyChecklist(models.Model):
    _name = 'imran.daily.checklist'
    _description = 'Daily Task Checklist'
    _order = 'due_date, id desc'
    _check_company_auto = True

    name = fields.Char(string='Checklist', required=True)
    user_id = fields.Many2one('res.users', string='Owner', required=True,
                             default=lambda self: self.env.user, readonly=True, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    due_date = fields.Date(string='Due Date', default=fields.Date.context_today)
    notes = fields.Text()
    active = fields.Boolean(default=True)
    item_ids = fields.One2many('imran.daily.checklist.item', 'checklist_id', string='Tasks', copy=True)
    total_items = fields.Integer(string='Tasks', compute='_compute_progress')
    completed_items = fields.Integer(string='Completed', compute='_compute_progress')
    progress = fields.Float(string='Progress', compute='_compute_progress')
    state = fields.Selection([('todo', 'To Do'), ('in_progress', 'In Progress'), ('done', 'Done')],
                             compute='_compute_progress', store=True, string='Status')

    @api.depends('item_ids', 'item_ids.done')
    def _compute_progress(self):
        for record in self:
            total = len(record.item_ids)
            completed = len(record.item_ids.filtered('done'))
            record.total_items = total
            record.completed_items = completed
            record.progress = 100.0 * completed / total if total else 0.0
            record.state = 'done' if total and completed == total else 'in_progress' if completed else 'todo'

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if not self.env.su and values.get('user_id', self.env.uid) != self.env.uid:
                raise AccessError(_('You can create checklists only for yourself.'))
            if values.get('company_id', self.env.company.id) not in self.env.companies.ids:
                raise AccessError(_('Select a company you are allowed to use.'))
            if {'progress', 'state', 'total_items', 'completed_items'} & values.keys():
                raise AccessError(_('Completion totals are calculated from the tasks.'))
        return super().create(vals_list)

    def write(self, values):
        self.check_access('write')
        if not self.env.su and 'user_id' in values:
            raise AccessError(_('The checklist owner cannot be changed.'))
        if 'company_id' in values and values['company_id'] not in self.env.companies.ids:
            raise AccessError(_('Select a company you are allowed to use.'))
        if {'progress', 'state', 'total_items', 'completed_items'} & values.keys():
            raise AccessError(_('Completion totals are calculated from the tasks.'))
        return super().write(values)

    def action_complete_all(self):
        self.check_access('write')
        self.item_ids.write({'done': True})
        return True

    def action_reset(self):
        self.check_access('write')
        self.item_ids.write({'done': False})
        return True


class DailyChecklistItem(models.Model):
    _name = 'imran.daily.checklist.item'
    _description = 'Daily Checklist Task'
    _order = 'sequence, id'

    checklist_id = fields.Many2one('imran.daily.checklist', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Task', required=True)
    done = fields.Boolean(string='Done')
    company_id = fields.Many2one(related='checklist_id.company_id', store=True, readonly=True)
    user_id = fields.Many2one(related='checklist_id.user_id', store=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if {'company_id', 'user_id'} & values.keys():
                raise AccessError(_('Task ownership follows its checklist.'))
            self.env['imran.daily.checklist'].browse(values.get('checklist_id')).check_access('write')
        return super().create(vals_list)

    def write(self, values):
        self.check_access('write')
        self.checklist_id.check_access('write')
        if {'company_id', 'user_id'} & values.keys():
            raise AccessError(_('Task ownership follows its checklist.'))
        if values.get('checklist_id'):
            self.env['imran.daily.checklist'].browse(values['checklist_id']).check_access('write')
        return super().write(values)
