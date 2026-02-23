# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestAppointmentPortalUsers(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestAppointmentPortalUsers, cls).setUpClass()
        cls.users_model = cls.env['res.users'].with_context(no_reset_password=True)
        cls.group_portal = cls.env.ref('base.group_portal')
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_public = cls.env.ref('base.group_public')

    @classmethod
    def _create_user(cls, suffix, groups, **extra_vals):
        vals = {
            'name': f'Test User {suffix}',
            'login': f'test_user_{suffix}@example.com',
            'email': f'test_user_{suffix}@example.com',
            'group_ids': [(6, 0, groups)],
            **extra_vals,
        }
        return cls.users_model.create(vals)

    def test_staff_user_domain_allows_internal_and_flagged_portal_only(self):
        domain = self.env['appointment.type']._fields['staff_user_ids'].domain
        self.assertIn('is_portal_user', domain)
        self.assertIn('available_for_appointments', domain)
        self.assertNotIn("('share', '=', True)", domain)

    def test_portal_user_removed_from_staff_when_flag_disabled(self):
        portal_user = self._create_user(
            'portal_enabled',
            [self.group_portal.id],
            available_for_appointments=True,
        )
        internal_user = self._create_user(
            'internal',
            [self.group_user.id],
        )
        appointment_type = self.env['appointment.type'].create({
            'name': 'Portal Staff Test',
            'staff_user_ids': [(6, 0, [portal_user.id, internal_user.id])],
        })

        self.assertIn(portal_user, appointment_type.staff_user_ids)
        self.assertIn(internal_user, appointment_type.staff_user_ids)

        portal_user.write({'available_for_appointments': False})
        appointment_type.invalidate_recordset(['staff_user_ids'])

        self.assertNotIn(portal_user, appointment_type.staff_user_ids)
        self.assertIn(internal_user, appointment_type.staff_user_ids)

    def test_public_user_cannot_be_assigned_as_staff(self):
        public_user = self._create_user(
            'public',
            [self.group_public.id],
            available_for_appointments=True,
        )
        with self.assertRaises(ValidationError):
            self.env['appointment.type'].create({
                'name': 'Public Staff Test',
                'staff_user_ids': [(6, 0, [public_user.id])],
            })

    def test_portal_user_with_flag_can_be_assigned_as_staff(self):
        portal_user = self._create_user(
            'portal_allowed',
            [self.group_portal.id],
            available_for_appointments=True,
        )
        appointment_type = self.env['appointment.type'].create({
            'name': 'Portal Allowed Test',
            'staff_user_ids': [(6, 0, [portal_user.id])],
        })
        self.assertIn(portal_user, appointment_type.staff_user_ids)

    def test_portal_user_without_flag_cannot_be_assigned_as_staff(self):
        portal_user = self._create_user(
            'portal_denied',
            [self.group_portal.id],
            available_for_appointments=False,
        )
        with self.assertRaises(ValidationError):
            self.env['appointment.type'].create({
                'name': 'Portal Denied Test',
                'staff_user_ids': [(6, 0, [portal_user.id])],
            })

    def test_internal_user_not_removed_when_flag_disabled(self):
        internal_user = self._create_user(
            'internal_keep',
            [self.group_user.id],
        )
        appointment_type = self.env['appointment.type'].create({
            'name': 'Internal Staff Test',
            'staff_user_ids': [(6, 0, [internal_user.id])],
        })

        internal_user.write({'available_for_appointments': False})
        appointment_type.invalidate_recordset(['staff_user_ids'])

        self.assertIn(internal_user, appointment_type.staff_user_ids)

    def test_portal_user_removed_from_staff_when_portal_group_removed(self):
        portal_user = self._create_user(
            'portal_to_public',
            [self.group_portal.id],
            available_for_appointments=True,
        )
        appointment_type = self.env['appointment.type'].create({
            'name': 'Portal To Public Test',
            'staff_user_ids': [(6, 0, [portal_user.id])],
        })

        self.assertIn(portal_user, appointment_type.staff_user_ids)

        portal_user.write({'group_ids': [(6, 0, [self.group_public.id])]})
        appointment_type.invalidate_recordset(['staff_user_ids'])

        self.assertNotIn(portal_user, appointment_type.staff_user_ids)

    def test_public_user_becoming_portal_with_flag_can_be_assigned(self):
        user = self._create_user(
            'public_to_portal',
            [self.group_public.id],
            available_for_appointments=True,
        )

        with self.assertRaises(ValidationError):
            self.env['appointment.type'].create({
                'name': 'Public Before Portal Test',
                'staff_user_ids': [(6, 0, [user.id])],
            })

        user.write({'group_ids': [(6, 0, [self.group_portal.id])]})
        appointment_type = self.env['appointment.type'].create({
            'name': 'Public To Portal Test',
            'staff_user_ids': [(6, 0, [user.id])],
        })

        self.assertIn(user, appointment_type.staff_user_ids)
