from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    appointment_resource_id = fields.Many2one(
        'appointment.resource',
        string='Appointment Resource',
        copy=False,
        ondelete='set null',
    )

    def _prepare_appointment_resource_vals(self):
        self.ensure_one()
        vals = {
            'name': self.name,
            'active': self.active,
        }
        if 'company_id' in self._fields:
            vals['company_id'] = self.company_id.id or False
        return vals

    def _get_or_create_appointment_resource(self):
        appointment_resource_model = self.env['appointment.resource'].sudo()
        for equipment in self:
            if equipment.appointment_resource_id:
                continue
            appointment_resource = appointment_resource_model.create(equipment._prepare_appointment_resource_vals())
            equipment.sudo().appointment_resource_id = appointment_resource.id
        return self.mapped('appointment_resource_id')

    def write(self, vals):
        res = super().write(vals)

        mirrored_fields = {'name', 'active'}
        if 'company_id' in self._fields:
            mirrored_fields.add('company_id')
        if not mirrored_fields.intersection(vals):
            return res

        for equipment in self.filtered('appointment_resource_id'):
            resource_vals = {
                'name': equipment.name,
                'active': equipment.active,
            }
            if 'company_id' in self._fields:
                resource_vals['company_id'] = equipment.company_id.id or False
            equipment.appointment_resource_id.sudo().write(resource_vals)

        return res
