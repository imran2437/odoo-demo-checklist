from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestDailyChecklist(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login='checklist.owner.test', groups='base.group_user')
        cls.other = new_test_user(cls.env, login='checklist.other.test', groups='base.group_user')

    def _checklist(self):
        return self.env['imran.daily.checklist'].with_user(self.user).create({
            'name': 'Morning routine', 'item_ids': [Command.create({'name': name})
                for name in ('Check agenda', 'Review tasks', 'Plan next action')]})

    def test_progress_complete_and_reset(self):
        record = self._checklist()
        self.assertEqual((record.total_items, record.completed_items, record.progress, record.state), (3, 0, 0, 'todo'))
        record.item_ids[0].done = True
        self.assertEqual(record.completed_items, 1)
        self.assertAlmostEqual(record.progress, 100 / 3)
        self.assertEqual(record.state, 'in_progress')
        record.action_complete_all()
        self.assertEqual((record.completed_items, record.progress, record.state), (3, 100, 'done'))
        record.action_reset()
        self.assertEqual((record.completed_items, record.progress, record.state), (0, 0, 'todo'))

    def test_empty_checklist_and_task_removal(self):
        record = self._checklist()
        record.item_ids.unlink()
        self.assertEqual((record.total_items, record.progress, record.state), (0, 0, 'todo'))

    def test_other_user_cannot_read_edit_delete_or_complete(self):
        record = self._checklist()
        self.assertFalse(self.env['imran.daily.checklist'].with_user(self.other).search([('id', '=', record.id)]))
        for action in (lambda: record.with_user(self.other).read(['name']),
                       lambda: record.with_user(self.other).write({'name': 'Denied'}),
                       lambda: record.with_user(self.other).action_complete_all(),
                       lambda: record.with_user(self.other).unlink(),
                       lambda: record.item_ids[:1].with_user(self.other).write({'done': True})):
            with self.assertRaises(AccessError):
                action()

    def test_ownership_and_computed_fields_cannot_be_overridden(self):
        record = self._checklist()
        for values in ({'user_id': self.other.id}, {'progress': 100}, {'state': 'done'}):
            with self.assertRaises(AccessError):
                record.write(values)
        with self.assertRaises(AccessError):
            self.env['imran.daily.checklist'].with_user(self.user).create({'name': 'Denied', 'user_id': self.other.id})
        with self.assertRaises(AccessError):
            record.item_ids[:1].write({'user_id': self.other.id})

    def test_cannot_move_task_to_another_users_checklist(self):
        record = self._checklist()
        other = self.env['imran.daily.checklist'].with_user(self.other).create({'name': 'Private'})
        with self.assertRaises(AccessError):
            record.item_ids[:1].checklist_id = other
        with self.assertRaises(AccessError):
            self.env['imran.daily.checklist.item'].with_user(self.user).create({'name': 'Denied', 'checklist_id': other.id})

    def test_company_rules_and_disallowed_company_creation(self):
        company = self.env['res.company'].create({'name': 'Checklist Other Company'})
        self.user.company_ids = [Command.link(company.id)]
        record = self.env['imran.daily.checklist'].with_user(self.user).with_company(company).create({'name': 'Other company'})
        restricted = record.with_context(allowed_company_ids=self.env.company.ids)
        with self.assertRaises(AccessError):
            restricted.read(['name'])
        with self.assertRaises(AccessError):
            self.env['imran.daily.checklist'].with_user(self.other).create({'name': 'Denied', 'company_id': company.id})

    def test_copy_and_archive(self):
        record = self._checklist()
        copied = record.copy({'name': 'Tomorrow'})
        self.assertEqual(len(copied.item_ids), 3)
        self.assertFalse(copied.item_ids & record.item_ids)
        record.active = False
        self.assertNotIn(record, self.env['imran.daily.checklist'].with_user(self.user).search([]))
        self.assertIn(record, self.env['imran.daily.checklist'].with_user(self.user).with_context(active_test=False).search([]))
