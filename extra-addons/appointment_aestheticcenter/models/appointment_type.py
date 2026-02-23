from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    staff_user_ids = fields.Many2many(
        domain="['|', ('share', '=', False), '&', ('is_portal_user', '=', True), ('available_for_appointments', '=', True)]"
    )

    @api.depends(
        'schedule_based_on',
        'staff_user_ids.share',
        'staff_user_ids.is_portal_user',
        'staff_user_ids.available_for_appointments',
    )
    def _compute_staff_user_ids(self):
        super()._compute_staff_user_ids()
        for appointment_type in self.filtered(lambda appt: appt.schedule_based_on == 'users'):
            appointment_type.staff_user_ids = appointment_type.staff_user_ids.filtered(
                lambda user: (not user.share) or (user.is_portal_user and user.available_for_appointments)
            )

    @api.constrains('staff_user_ids')
    def _check_staff_users_portal_availability(self):
        for appointment_type in self:
            invalid_users = appointment_type.staff_user_ids.filtered(
                lambda user: user.share and (not user.is_portal_user or not user.available_for_appointments)
            )
            if invalid_users:
                raise ValidationError(_(
                    "Only internal users and portal users marked as Available for Appointments can be selected."
                ))
