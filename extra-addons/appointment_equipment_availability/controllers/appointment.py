from odoo.addons.appointment.controllers.appointment import AppointmentController as BaseAppointmentController
from odoo.addons.base.models.ir_qweb import keep_query
from odoo.http import request


class AppointmentController(BaseAppointmentController):
    def _handle_appointment_form_submission(
        self,
        appointment_type,
        date_start,
        date_end,
        description,
        duration,
        allday,
        answer_input_values,
        name,
        customer,
        appointment_invite,
        guests=None,
        staff_user=None,
        asked_capacity=1,
        booking_line_values=None,
        extra_calendar_event_params=None,
    ):
        extra_calendar_event_params = dict(extra_calendar_event_params or {})
        if appointment_type.maintenance_equipment_ids:
            reserved_equipment = appointment_type._reserve_available_maintenance_equipment_portal(
                date_start,
                date_end,
                is_allday=bool(allday),
            )
            if not reserved_equipment:
                return request.redirect('/appointment/%s?%s' % (
                    appointment_type.id,
                    keep_query('*', state='failed-resource'),
                ))
            extra_calendar_event_params['maintenance_equipment_id'] = reserved_equipment.id

        return super()._handle_appointment_form_submission(
            appointment_type,
            date_start,
            date_end,
            description,
            duration,
            allday,
            answer_input_values,
            name,
            customer,
            appointment_invite,
            guests=guests,
            staff_user=staff_user,
            asked_capacity=asked_capacity,
            booking_line_values=booking_line_values,
            extra_calendar_event_params=extra_calendar_event_params,
        )
