from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    maintenance_equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='Equipment',
        tracking=True,
        index='btree_not_null',
    )
    appointment_type_maintenance_equipment_ids = fields.Many2many(
        'maintenance.equipment',
        related='appointment_type_id.maintenance_equipment_ids',
        string='Available Equipment',
        readonly=True,
    )
    unavailable_maintenance_equipment_ids = fields.Many2many(
        'maintenance.equipment',
        string='Unavailable Equipment',
        compute='_compute_unavailable_maintenance_equipment_ids',
    )

    @api.constrains('maintenance_equipment_id', 'appointment_type_id')
    def _check_maintenance_equipment_match_appointment_type(self):
        for event in self:
            if not event.appointment_type_id or not event.maintenance_equipment_id:
                continue
            if event.maintenance_equipment_id not in event.appointment_type_id.maintenance_equipment_ids:
                raise ValidationError(_(
                    '"%(equipment)s" cannot be used for "%(appointment)s".',
                    equipment=event.maintenance_equipment_id.display_name,
                    appointment=event.appointment_type_id.display_name,
                ))

    def _get_conflicting_maintenance_equipment_events(self):
        self.ensure_one()
        if (
            not self.appointment_type_id
            or not self.maintenance_equipment_id
            or not self.active
            or self.appointment_status == 'cancelled'
            or not self.start
            or not self.stop
        ):
            return self.env['calendar.event']

        return self.appointment_type_id._get_conflicting_maintenance_equipment_events(
            self.start,
            self.stop,
            equipment_ids=self.maintenance_equipment_id,
            is_allday=bool(self.allday),
            ignore_event_ids=[self.id] if self.id else None,
        )

    @api.depends('maintenance_equipment_id', 'appointment_type_id', 'start', 'stop', 'allday', 'active', 'appointment_status')
    def _compute_unavailable_maintenance_equipment_ids(self):
        self.unavailable_maintenance_equipment_ids = False
        for event in self.filtered(lambda event: all([
            event.maintenance_equipment_id,
            event.appointment_type_id,
            event.start,
            event.stop,
            event.active,
            event.appointment_status != 'cancelled',
        ])):
            is_available = event.appointment_type_id._is_maintenance_equipment_available(
                event.maintenance_equipment_id,
                event.start,
                event.stop,
                is_allday=bool(event.allday),
                ignore_event_ids=[event.id] if event.id else None,
            )
            if not is_available:
                event.unavailable_maintenance_equipment_ids = event.maintenance_equipment_id

    @api.onchange('maintenance_equipment_id', 'appointment_type_id', 'start', 'stop', 'allday', 'active', 'appointment_status')
    def _onchange_maintenance_equipment_warning(self):
        for event in self:
            if not event.maintenance_equipment_id or not event.appointment_type_id or not event.start or not event.stop:
                continue
            is_available = event.appointment_type_id._is_maintenance_equipment_available(
                event.maintenance_equipment_id,
                event.start,
                event.stop,
                is_allday=bool(event.allday),
                ignore_event_ids=[event.id] if event.id else None,
            )
            if not is_available:
                return {
                    'warning': {
                        'title': _('Equipment is already booked'),
                        'message': _(
                            'Selected equipment "%(equipment)s" is already used for another appointment in this time range.',
                            equipment=event.maintenance_equipment_id.display_name,
                        ),
                    }
                }

    def _get_equipment_to_autofill(self):
        self.ensure_one()
        if not self.appointment_type_id or not self.appointment_type_id.maintenance_equipment_ids:
            return self.env['maintenance.equipment']
        if not self.start or not self.stop:
            return self.appointment_type_id.maintenance_equipment_ids[:1]

        available_equipment = self.appointment_type_id._get_available_maintenance_equipment(
            self.start,
            self.stop,
            is_allday=bool(self.allday),
            ignore_event_ids=[self.id] if self.id else None,
        )
        return available_equipment[:1]

    def _autofill_maintenance_equipment(self):
        for event in self:
            if not event.appointment_type_id or not event.appointment_type_id.maintenance_equipment_ids:
                continue
            if event.maintenance_equipment_id in event.appointment_type_id.maintenance_equipment_ids:
                continue
            equipment = event._get_equipment_to_autofill()
            if equipment:
                event.with_context(skip_maintenance_equipment_autofill=True).write({
                    'maintenance_equipment_id': equipment.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        if not self.env.context.get('skip_maintenance_equipment_autofill'):
            events._autofill_maintenance_equipment()
        return events

    def write(self, vals):
        should_autofill = bool(
            {'appointment_type_id', 'start', 'stop', 'allday', 'maintenance_equipment_id'}.intersection(vals)
            and 'maintenance_equipment_id' not in vals
        )
        if "appointment_type_id" in vals and "maintenance_equipment_id" not in vals:
            target_type_id = vals.get("appointment_type_id")
            if not target_type_id:
                to_clear = self.filtered("maintenance_equipment_id")
            else:
                target_type = self.env["appointment.type"].browse(target_type_id)
                to_clear = self.filtered(
                    lambda e: (
                        e.maintenance_equipment_id
                        and e.maintenance_equipment_id
                        not in target_type.maintenance_equipment_ids
                    )
                )
            if to_clear:
                to_clear.with_context(skip_maintenance_equipment_autofill=True).write(
                    {"maintenance_equipment_id": False}
                )
        res = super().write(vals)
        if self.env.context.get('skip_maintenance_equipment_autofill'):
            return res
        if should_autofill:
            self._autofill_maintenance_equipment()
        return res
