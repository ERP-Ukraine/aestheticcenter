from datetime import datetime, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    maintenance_equipment_ids = fields.Many2many(
        'maintenance.equipment',
        string='Equipment',
        help='Equipment units that can be used for this appointment type.',
    )

    def _ensure_maintenance_equipment_resources(self):
        self.mapped('maintenance_equipment_ids')._get_or_create_appointment_resource()

    @api.model_create_multi
    def create(self, vals_list):
        appointment_types = super().create(vals_list)
        appointment_types._ensure_maintenance_equipment_resources()
        return appointment_types

    def write(self, vals):
        res = super().write(vals)
        if 'maintenance_equipment_ids' in vals:
            self._ensure_maintenance_equipment_resources()
        return res

    @api.model
    def _equipment_to_utc_naive(self, dt_value):
        if not dt_value:
            return dt_value
        if not isinstance(dt_value, datetime):
            dt_value = fields.Datetime.to_datetime(dt_value)
        if dt_value.tzinfo:
            dt_value = dt_value.astimezone(pytz.utc).replace(tzinfo=None)
        return dt_value

    def _normalize_maintenance_equipment_interval(
        self, start_dt_utc, end_dt_utc, is_allday=False
    ):
        start_dt_utc = self._equipment_to_utc_naive(start_dt_utc)
        end_dt_utc = self._equipment_to_utc_naive(end_dt_utc)
        if not start_dt_utc or not end_dt_utc:
            return start_dt_utc, end_dt_utc
        if is_allday and end_dt_utc <= start_dt_utc:
            end_dt_utc += relativedelta(days=1)
        if end_dt_utc <= start_dt_utc:
            end_dt_utc = start_dt_utc + timedelta(seconds=1)
        return start_dt_utc, end_dt_utc

    @api.model
    def _maintenance_equipment_has_unavailability_overlap(self, start_dt_utc, end_dt_utc, intervals):
        if not intervals:
            return False
        if start_dt_utc.tzinfo:
            start_dt_utc = start_dt_utc.astimezone(pytz.utc)
        else:
            start_dt_utc = pytz.utc.localize(start_dt_utc)
        if end_dt_utc.tzinfo:
            end_dt_utc = end_dt_utc.astimezone(pytz.utc)
        else:
            end_dt_utc = pytz.utc.localize(end_dt_utc)

        return any(
            (i_stop - i_start) > timedelta(microseconds=1)
            and i_start < end_dt_utc
            and i_stop > start_dt_utc
            for i_start, i_stop in intervals
        )

    def _get_conflicting_maintenance_equipment_events(self, start_dt_utc, end_dt_utc, equipment_ids=None, is_allday=False, ignore_event_ids=None):
        self.ensure_one()
        equipment_ids = equipment_ids or self.maintenance_equipment_ids
        if not equipment_ids:
            return self.env['calendar.event']

        start_dt_utc, end_dt_utc = self._normalize_maintenance_equipment_interval(
            start_dt_utc,
            end_dt_utc,
            is_allday=is_allday,
        )
        if not start_dt_utc or not end_dt_utc:
            return self.env['calendar.event']

        ignored_ids = set(ignore_event_ids or [])
        ignored_ids.update(self.env.context.get('ignore_event_ids') or [])

        domain = [
            ("maintenance_equipment_id", "in", equipment_ids.ids),
            ("active", "=", True),
            ("appointment_status", "!=", "cancelled"),
            ("start", "<", end_dt_utc),
            ("stop", ">", start_dt_utc),
        ]
        if ignored_ids:
            domain.append(('id', 'not in', list(ignored_ids)))

        return self.env['calendar.event'].sudo().search(domain)

    def _get_maintenance_equipment_calendar_unavailabilities(self, equipment_ids, start_dt_utc, end_dt_utc):
        resources = equipment_ids.sudo().mapped('appointment_resource_id.resource_id')
        if not resources:
            return {}
        return resources._get_unavailable_intervals(start_dt_utc, end_dt_utc)

    def _is_maintenance_equipment_available(self, equipment, start_dt_utc, end_dt_utc, is_allday=False, ignore_event_ids=None):
        self.ensure_one()
        if not equipment:
            return False

        start_dt_utc, end_dt_utc = self._normalize_maintenance_equipment_interval(
            start_dt_utc,
            end_dt_utc,
            is_allday=is_allday,
        )
        if not start_dt_utc or not end_dt_utc:
            return False

        conflicts = self._get_conflicting_maintenance_equipment_events(
            start_dt_utc,
            end_dt_utc,
            equipment_ids=equipment,
            is_allday=is_allday,
            ignore_event_ids=ignore_event_ids,
        )
        if conflicts:
            return False

        unavailabilities = self._get_maintenance_equipment_calendar_unavailabilities(
            equipment,
            start_dt_utc,
            end_dt_utc,
        )
        resource = equipment.sudo().appointment_resource_id.resource_id
        intervals = unavailabilities.get(resource.id, []) if resource else []
        return not self._maintenance_equipment_has_unavailability_overlap(start_dt_utc, end_dt_utc, intervals)

    def _get_available_maintenance_equipment(self, start_dt_utc, end_dt_utc, is_allday=False, ignore_event_ids=None):
        self.ensure_one()
        if not self.maintenance_equipment_ids:
            return self.env['maintenance.equipment']

        start_dt_utc, end_dt_utc = self._normalize_maintenance_equipment_interval(
            start_dt_utc,
            end_dt_utc,
            is_allday=is_allday,
        )
        if not start_dt_utc or not end_dt_utc:
            return self.env['maintenance.equipment']

        conflicts = self._get_conflicting_maintenance_equipment_events(
            start_dt_utc,
            end_dt_utc,
            equipment_ids=self.maintenance_equipment_ids,
            is_allday=is_allday,
            ignore_event_ids=ignore_event_ids,
        )
        available = self.maintenance_equipment_ids - conflicts.maintenance_equipment_id
        if not available:
            return available

        unavailabilities = self._get_maintenance_equipment_calendar_unavailabilities(
            available,
            start_dt_utc,
            end_dt_utc,
        )
        return available.filtered(
            lambda equipment: not equipment.appointment_resource_id
            or not equipment.appointment_resource_id.resource_id
            or not self._maintenance_equipment_has_unavailability_overlap(
                start_dt_utc,
                end_dt_utc,
                unavailabilities.get(equipment.appointment_resource_id.sudo().resource_id.id, []),
            )
        )

    def _reserve_available_maintenance_equipment_portal(self, start_dt_utc, end_dt_utc, is_allday=False):
        """Reserve one equipment atomically for portal booking submission."""
        self.ensure_one()
        if not self.maintenance_equipment_ids:
            return self.env['maintenance.equipment']

        available_equipment = self._get_available_maintenance_equipment(
            start_dt_utc,
            end_dt_utc,
            is_allday=is_allday,
        )
        if not available_equipment:
            return self.env['maintenance.equipment']

        # Use Odoo standard ORM locking pattern (try_lock_for_update -> FOR UPDATE SKIP LOCKED)
        # to prevent concurrent portal requests from selecting the same equipment.
        locked_equipment = available_equipment.sorted('id').try_lock_for_update()[:1]
        if not locked_equipment:
            return self.env['maintenance.equipment']

        is_still_available = self._is_maintenance_equipment_available(
            locked_equipment,
            start_dt_utc,
            end_dt_utc,
            is_allday=is_allday,
        )
        return locked_equipment if is_still_available else self.env['maintenance.equipment']

    def _slot_availability_prepare_maintenance_equipment_values(self, start_dt_utc, end_dt_utc):
        self.ensure_one()
        values = {
            'equipment_to_conflicting_events': {},
            'equipment_resource_unavailabilities': {},
            'equipment_to_resource_id': {},
        }
        if not self.maintenance_equipment_ids:
            return values

        start_dt_utc, end_dt_utc = self._normalize_maintenance_equipment_interval(start_dt_utc, end_dt_utc)
        if not start_dt_utc or not end_dt_utc:
            return values

        conflicts = self._get_conflicting_maintenance_equipment_events(
            start_dt_utc,
            end_dt_utc,
            equipment_ids=self.maintenance_equipment_ids,
        )
        values['equipment_to_conflicting_events'] = conflicts.grouped('maintenance_equipment_id')

        resources = self.maintenance_equipment_ids.sudo().mapped('appointment_resource_id.resource_id')
        values['equipment_resource_unavailabilities'] = resources._get_unavailable_intervals(start_dt_utc, end_dt_utc) if resources else {}
        values['equipment_to_resource_id'] = {
            equipment.id: equipment.appointment_resource_id.sudo().resource_id.id
            for equipment in self.maintenance_equipment_ids
            if equipment.appointment_resource_id and equipment.appointment_resource_id.resource_id
        }
        return values

    def _is_slot_with_available_maintenance_equipment(self, slot, availability_values):
        self.ensure_one()
        if not self.maintenance_equipment_ids:
            return True

        slot_start_utc, slot_end_utc = slot['UTC'][0], slot['UTC'][1]
        conflicts_by_equipment = availability_values.get('equipment_to_conflicting_events') or {}
        unavailabilities = availability_values.get('equipment_resource_unavailabilities') or {}
        resource_id_by_equipment = availability_values.get('equipment_to_resource_id') or {}

        for equipment in self.maintenance_equipment_ids:
            equipment_conflicts = conflicts_by_equipment.get(equipment, self.env['calendar.event'])
            if equipment_conflicts.filtered(lambda event: event.start < slot_end_utc and event.stop > slot_start_utc):
                continue

            resource_id = resource_id_by_equipment.get(equipment.id)
            if resource_id and self._maintenance_equipment_has_unavailability_overlap(
                slot_start_utc,
                slot_end_utc,
                unavailabilities.get(resource_id, []),
            ):
                continue

            return True

        return False

    def _slot_availability_prepare_users_values(self, staff_users, start_dt, end_dt):
        values = super()._slot_availability_prepare_users_values(staff_users, start_dt, end_dt)
        if not self.maintenance_equipment_ids:
            return values
        values.update(self._slot_availability_prepare_maintenance_equipment_values(start_dt, end_dt))
        return values

    def _slot_availability_is_user_available(self, slot, staff_user, availability_values, asked_capacity=1):
        if not super()._slot_availability_is_user_available(
            slot,
            staff_user,
            availability_values,
            asked_capacity=asked_capacity,
        ):
            return False
        return self._is_slot_with_available_maintenance_equipment(slot, availability_values)

    def _prepare_calendar_event_values(
        self,
        asked_capacity,
        booking_line_values,
        description,
        duration,
        allday,
        appointment_invite,
        guests,
        name,
        customer,
        staff_user,
        start,
        stop,
    ):
        values = super()._prepare_calendar_event_values(
            asked_capacity,
            booking_line_values,
            description,
            duration,
            allday,
            appointment_invite,
            guests,
            name,
            customer,
            staff_user,
            start,
            stop,
        )
        if not self.maintenance_equipment_ids:
            return values

        available_equipment = self._get_available_maintenance_equipment(start, stop, is_allday=bool(allday))
        selected_equipment = available_equipment[:1]
        if selected_equipment:
            values['maintenance_equipment_id'] = selected_equipment.id
        return values
