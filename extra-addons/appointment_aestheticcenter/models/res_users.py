from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_portal_user = fields.Boolean(
        compute='_compute_is_portal_user',
        compute_sudo=True,
        store=True,
    )
    available_for_appointments = fields.Boolean(
        string='Available for Appointments',
        help=(
            'Enable to allow this portal user to be selected in Appointments. '
            'Internal users remain available regardless of this option.'
        ),
        default=False,
    )

    @api.depends('group_ids')
    def _compute_is_portal_user(self):
        portal_group = self.env.ref('base.group_portal')
        for user in self:
            user.is_portal_user = portal_group in user.group_ids
