from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from dateutil.relativedelta import relativedelta

from odoo import api, fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.appointment_equipment_availability.controllers import appointment as appointment_controller


@tagged('post_install', '-at_install')
class TestAppointmentEquipmentAvailability(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.group_user = cls.env.ref('base.group_user')

        cls.user_main = cls.Users.create({
            'name': 'Appointment Equipment Availability Main User',
            'login': 'appointment_equipment_availability_main_user@example.com',
            'email': 'appointment_equipment_availability_main_user@example.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
            'tz': 'UTC',
        })

        cls.user_other = cls.Users.create({
            'name': 'Appointment Equipment Availability Other User',
            'login': 'appointment_equipment_availability_other_user@example.com',
            'email': 'appointment_equipment_availability_other_user@example.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
            'tz': 'UTC',
        })

        cls.equipment_1, cls.equipment_2 = cls.env['maintenance.equipment'].create([{
            'name': 'Equipment Availability Unit 1',
        }, {
            'name': 'Equipment Availability Unit 2',
        }])

        cls.appointment_type = cls.env['appointment.type'].create({
            'name': 'Equipment Availability Appointment',
            'category': 'recurring',
            'appointment_tz': 'UTC',
            'appointment_duration': 1,
            'min_schedule_hours': 0,
            'max_schedule_days': 7,
            'slot_ids': [(0, 0, {
                'weekday': weekday,
                'start_hour': 9,
                'end_hour': 10,
            }) for weekday in ['1', '2', '3', '4', '5', '6', '7']],
            'is_auto_assign': True,
            'schedule_based_on': 'users',
            'staff_user_ids': [(6, 0, [cls.user_main.id])],
            'maintenance_equipment_ids': [(6, 0, [cls.equipment_1.id, cls.equipment_2.id])],
        })

        cls.single_equipment_type = cls.env['appointment.type'].create({
            'name': 'Equipment Availability Appointment Single',
            'category': 'recurring',
            'appointment_tz': 'UTC',
            'appointment_duration': 1,
            'min_schedule_hours': 0,
            'max_schedule_days': 7,
            'slot_ids': [(0, 0, {
                'weekday': weekday,
                'start_hour': 9,
                'end_hour': 10,
            }) for weekday in ['1', '2', '3', '4', '5', '6', '7']],
            'is_auto_assign': True,
            'schedule_based_on': 'users',
            'staff_user_ids': [(6, 0, [cls.user_main.id])],
            'maintenance_equipment_ids': [(6, 0, [cls.equipment_1.id])],
        })

    def _create_event(self, appointment_type, equipment, start_dt, stop_dt, user):
        return self.env['calendar.event'].create({
            'name': 'Appointment equipment availability event',
            'appointment_type_id': appointment_type.id,
            'maintenance_equipment_id': equipment.id if equipment else False,
            'start': start_dt,
            'stop': stop_dt,
            'user_id': user.id,
            'partner_ids': [(6, 0, [user.partner_id.id])],
        })

    def _get_first_slot(self):
        slots = self.appointment_type._get_appointment_slots('UTC', filter_users=self.user_main)
        for month in slots:
            for week in month['weeks']:
                for day in week:
                    for slot in day.get('slots') or []:
                        return slot
        return False

    def _create_lock_test_fixture(self, *, equipment_count):
        with self.registry.cursor() as setup_cr:
            setup_env = api.Environment(setup_cr, self.env.uid, dict(self.env.context))
            user = setup_env['res.users'].with_context(no_reset_password=True).create({
                'name': f'Lock Test User {uuid4().hex[:8]}',
                'login': f'lock_test_user_{uuid4().hex}@example.com',
                'email': f'lock_test_user_{uuid4().hex}@example.com',
                'group_ids': [(6, 0, [self.group_user.id])],
                'tz': 'UTC',
            })
            equipments = setup_env['maintenance.equipment'].create([
                {'name': f'Lock Test Equipment {idx + 1} {uuid4().hex[:6]}'}
                for idx in range(equipment_count)
            ])
            appointment_type = setup_env['appointment.type'].create({
                'name': f'Lock Test Appointment {uuid4().hex[:8]}',
                'category': 'recurring',
                'appointment_tz': 'UTC',
                'appointment_duration': 1,
                'min_schedule_hours': 0,
                'max_schedule_days': 7,
                'slot_ids': [(0, 0, {
                    'weekday': weekday,
                    'start_hour': 9,
                    'end_hour': 10,
                }) for weekday in ['1', '2', '3', '4', '5', '6', '7']],
                'is_auto_assign': True,
                'schedule_based_on': 'users',
                'staff_user_ids': [(6, 0, [user.id])],
                'maintenance_equipment_ids': [(6, 0, equipments.ids)],
            })
            setup_cr.commit()
            return appointment_type.id, equipments.ids

    def test_busy_equipment_slot_is_hidden(self):
        slot = self._get_first_slot()
        self.assertTrue(slot, 'Expected at least one available slot.')

        slot_start = fields.Datetime.to_datetime(slot['datetime'])
        slot_end = slot_start + relativedelta(hours=float(slot['slot_duration']))
        self._create_event(self.appointment_type, self.equipment_1, slot_start, slot_end, self.user_other)
        self._create_event(self.appointment_type, self.equipment_2, slot_start, slot_end, self.user_other)

        slots_after_conflict = self.appointment_type._get_appointment_slots('UTC', filter_users=self.user_main)
        slot_datetimes_after_conflict = [
            day_slot['datetime']
            for month in slots_after_conflict
            for week in month['weeks']
            for day in week
            for day_slot in (day.get('slots') or [])
        ]
        self.assertNotIn(slot['datetime'], slot_datetimes_after_conflict)

    def test_portal_submission_redirects_when_equipment_is_busy(self):
        date_start = datetime(2030, 1, 12, 9, 0, 0)
        date_end = datetime(2030, 1, 12, 10, 0, 0)
        self._create_event(self.single_equipment_type, self.equipment_1, date_start, date_end, self.user_other)

        class DummyRequest:
            def __init__(self, env):
                self.env = env

            def redirect(self, url):
                return url

        controller = appointment_controller.AppointmentController()
        with patch.object(appointment_controller, 'request', DummyRequest(self.env)), patch.object(
            appointment_controller,
            'keep_query',
            return_value='state=failed-resource',
        ):
            result = controller._handle_appointment_form_submission(
                self.single_equipment_type,
                date_start,
                date_end,
                description='',
                duration=1,
                allday=False,
                answer_input_values=[],
                name='Portal Visitor',
                customer=self.user_main.partner_id,
                appointment_invite=False,
            )

        self.assertEqual(result, f'/appointment/{self.single_equipment_type.id}?state=failed-resource')

    def test_backend_warning_when_equipment_conflicts(self):
        date_start = datetime(2030, 1, 13, 9, 0, 0)
        date_end = datetime(2030, 1, 13, 10, 0, 0)
        self._create_event(self.single_equipment_type, self.equipment_1, date_start, date_end, self.user_other)

        draft_event = self.env['calendar.event'].new({
            'name': 'Backend warning check',
            'appointment_type_id': self.single_equipment_type.id,
            'maintenance_equipment_id': self.equipment_1.id,
            'start': date_start,
            'stop': date_end,
            'user_id': self.user_main.id,
            'partner_ids': [(6, 0, [self.user_main.partner_id.id])],
        })

        warning = draft_event._onchange_maintenance_equipment_warning()
        self.assertTrue(warning)
        self.assertIn('warning', warning)

    def test_cancelled_event_releases_equipment(self):
        start_dt = datetime(2030, 1, 14, 9, 0, 0)
        stop_dt = datetime(2030, 1, 14, 10, 0, 0)
        event = self._create_event(self.single_equipment_type, self.equipment_1, start_dt, stop_dt, self.user_other)

        available_before_cancel = self.single_equipment_type._get_available_maintenance_equipment(start_dt, stop_dt)
        self.assertNotIn(self.equipment_1, available_before_cancel)

        event.action_set_appointment_cancelled()
        available_after_cancel = self.single_equipment_type._get_available_maintenance_equipment(start_dt, stop_dt)
        self.assertIn(self.equipment_1, available_after_cancel)

    def test_equipment_calendar_leave_blocks_availability(self):
        start_dt = datetime(2030, 1, 15, 9, 0, 0)
        stop_dt = datetime(2030, 1, 15, 10, 0, 0)

        equipment_resource = self.equipment_1.appointment_resource_id.resource_id
        self.assertTrue(equipment_resource, 'Expected appointment resource to exist for linked equipment.')
        self.env['resource.calendar.leaves'].create({
            'name': 'Equipment planned downtime',
            'resource_id': equipment_resource.id,
            'date_from': start_dt,
            'date_to': stop_dt,
        })

        available = self.single_equipment_type._get_available_maintenance_equipment(start_dt, stop_dt)
        self.assertNotIn(self.equipment_1, available)

    def test_autofill_sets_allowed_equipment(self):
        start_dt = fields.Datetime.now() + relativedelta(days=2)
        stop_dt = start_dt + relativedelta(hours=1)

        event = self.env['calendar.event'].create({
            'name': 'Autofill equipment event',
            'appointment_type_id': self.appointment_type.id,
            'start': start_dt,
            'stop': stop_dt,
            'user_id': self.user_main.id,
            'partner_ids': [(6, 0, [self.user_main.partner_id.id])],
        })

        self.assertIn(event.maintenance_equipment_id, self.appointment_type.maintenance_equipment_ids)

    def test_autofill_does_not_pick_busy_equipment(self):
        start_dt = datetime(2030, 1, 16, 9, 0, 0)
        stop_dt = datetime(2030, 1, 16, 10, 0, 0)
        self._create_event(self.single_equipment_type, self.equipment_1, start_dt, stop_dt, self.user_other)

        event = self.env['calendar.event'].create({
            'name': 'Autofill must not fallback to busy equipment',
            'appointment_type_id': self.single_equipment_type.id,
            'start': start_dt,
            'stop': stop_dt,
            'user_id': self.user_main.id,
            'partner_ids': [(6, 0, [self.user_main.partner_id.id])],
        })

        self.assertFalse(event.maintenance_equipment_id)

    def test_prepare_values_do_not_fallback_to_busy_equipment(self):
        start_dt = datetime(2030, 1, 17, 9, 0, 0)
        stop_dt = datetime(2030, 1, 17, 10, 0, 0)
        self._create_event(self.single_equipment_type, self.equipment_1, start_dt, stop_dt, self.user_other)

        values = self.single_equipment_type._prepare_calendar_event_values(
            asked_capacity=1,
            booking_line_values=[{'capacity_reserved': 1}],
            description='',
            duration=1,
            allday=False,
            appointment_invite=self.env['appointment.invite'],
            guests=self.env['res.partner'],
            name='No fallback expected',
            customer=self.user_main.partner_id,
            staff_user=self.user_main,
            start=start_dt,
            stop=stop_dt,
        )

        self.assertNotIn('maintenance_equipment_id', values)

    def test_portal_reservation_skip_locked_returns_empty_when_single_equipment_locked(self):
        start_dt = datetime(2030, 1, 18, 9, 0, 0)
        stop_dt = datetime(2030, 1, 18, 10, 0, 0)
        appointment_type_id, equipment_ids = self._create_lock_test_fixture(equipment_count=1)
        equipment_id = equipment_ids[0]

        with self.registry.cursor() as cr_1:
            env_1 = api.Environment(cr_1, self.env.uid, dict(self.env.context))
            env_1['maintenance.equipment'].browse(equipment_id).try_lock_for_update()

            with self.registry.cursor() as cr_2:
                env_2 = api.Environment(cr_2, self.env.uid, dict(self.env.context))
                reserved = env_2['appointment.type'].browse(
                    appointment_type_id
                )._reserve_available_maintenance_equipment_portal(start_dt, stop_dt)
                self.assertFalse(reserved)
                cr_2.rollback()
            cr_1.rollback()

    def test_portal_reservation_skip_locked_picks_next_available_equipment(self):
        start_dt = datetime(2030, 1, 19, 9, 0, 0)
        stop_dt = datetime(2030, 1, 19, 10, 0, 0)
        appointment_type_id, equipment_ids = self._create_lock_test_fixture(equipment_count=2)
        first_equipment_id = equipment_ids[0]
        second_equipment_id = equipment_ids[1]

        with self.registry.cursor() as cr_1:
            env_1 = api.Environment(cr_1, self.env.uid, dict(self.env.context))
            env_1['maintenance.equipment'].browse(first_equipment_id).try_lock_for_update()

            with self.registry.cursor() as cr_2:
                env_2 = api.Environment(cr_2, self.env.uid, dict(self.env.context))
                reserved = env_2['appointment.type'].browse(
                    appointment_type_id
                )._reserve_available_maintenance_equipment_portal(start_dt, stop_dt)
                self.assertEqual(reserved, env_2['maintenance.equipment'].browse(second_equipment_id))
                cr_2.rollback()
            cr_1.rollback()

    def test_write_type_change_clears_only_incompatible_equipment(self):
        """Writing a new appointment_type_id must clear equipment only for records
        where that equipment is not in the new type's equipment list, not for all
        records in the recordset (regression test for bulk-clear bug)."""
        start_dt = datetime(2030, 2, 10, 9, 0, 0)
        stop_dt = datetime(2030, 2, 10, 10, 0, 0)

        # appointment_type has both equipment_1 and equipment_2
        event_eq1 = self._create_event(
            self.appointment_type, self.equipment_1, start_dt, stop_dt, self.user_main
        )
        # Both events share the same time slot so that after clearing equipment_2
        # from event_eq2, autofill cannot re-assign equipment_1 (it is busy with event_eq1).
        event_eq2 = self._create_event(
            self.appointment_type,
            self.equipment_2,
            start_dt,
            stop_dt,
            self.user_main,
        )

        # single_equipment_type only has equipment_1 — equipment_2 is incompatible with it
        (event_eq1 | event_eq2).write(
            {"appointment_type_id": self.single_equipment_type.id}
        )

        # equipment_1 is compatible with single_equipment_type → must be preserved
        self.assertEqual(event_eq1.maintenance_equipment_id, self.equipment_1)
        # equipment_2 is incompatible with single_equipment_type → must be cleared;
        # autofill cannot re-assign equipment_1 because event_eq1 already occupies it
        self.assertFalse(event_eq2.maintenance_equipment_id)
