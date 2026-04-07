{
    'name': 'Appointment Equipment Availability',
    'summary': 'Equipment availability control for Appointments',
    'author': 'ERP Ukraine LLC',
    'website': 'https://erp.co.ua',
    'support': 'support@erp.co.ua',
    'license': 'LGPL-3',
    'category': 'Services/Appointment',
    'version': '1.0',
    'depends': [
        'appointment',
        'maintenance',
    ],
    'data': [
        'views/appointment_type_views.xml',
        'views/calendar_event_views.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}
