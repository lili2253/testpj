from odoo import api, fields, Command, models, _
import qrcode
import base64
import io

class MeetingRoomApplication(models.Model):
    _name = 'hledan.meeting.room.application'
    _description = 'Meeting  / Training Room Application Form'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'datetime desc, id desc'

# application details
    application_type=fields.Selection([
        ('internal' , 'Internal') ,
        ('external' , 'External')
    ] , string='Application Type',default='internal',required=True)
    employee_id = fields.Many2one('hr.employee', string='Name' , tracking=True)
    partner_id = fields.Many2one('res.partner', string='Name' , tracking=True)
    department_id = fields.Many2one('hr.department', string='Department')
    organization_id = fields.Many2one('res.partner', string='Organization')

    #booking details
    datetime=fields.Datetime(string='Date of Required', required=True)
    name = fields.Char(string='Serial Number', readonly=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('hledan.meeting.room.application'))

    qr_code = fields.Binary(string='QR Code', compute='_compute_qr_code', store=True)

#purpose of booking
    booking_type = fields.Selection([
        ('meeting', 'Meeting'),
        ('training', 'Training'),
        ('workshop', 'Workshop'),
        ('other', 'Other')
    ], string='Purpose of Booking', required=True)

    other_purpose = fields.Char(string='Other(Please specify)')

#states
    state = fields.Selection([
        ('tentative', 'Tentative'),
        ('confirmed', 'Confirmed'),
        ('amendment', 'Amendment'),
        ('cancelled', 'Cancelled'),
        ('finished', 'Finished')
    ], string='Status', default='tentative', tracking=True)


    # Room Information
    room_id = fields.Many2one('hledan.meeting.room', string='Room Number', tracking=True)
    attendee=fields.Integer(string='Number of Attendee' ,compute='_compute_attendee', tracking=True)

#preferred setup
    board=fields.Boolean(string='Boardroom Setup',tracking=True)
    shape=fields.Boolean(string='U-Shape',tracking=True)
    classroom=fields.Boolean(string='Classroom' , tracking=True)
    other_setup=fields.Boolean(string='Other',tracking=True)

    # facilities
    projector = fields.Boolean(string='Projector', tracking=True)
    whiteboard = fields.Boolean(string='White board', tracking=True)
    internet = fields.Boolean(string='High-Speed Internet',tracking=True)
    other_facilities=fields.Boolean(string='Other',tracking=True)

    #additional
    currency_id = fields.Many2one( 'res.currency',string='Currency',required=True,
                                   default=lambda self: self.env.company.currency_id.id)
    room_rate = fields.Monetary(string='Room Rate',currency_field='currency_id')
    additional_charges = fields.Monetary(string='Additional Charges', currency_field='currency_id')
    payment_info = fields.Text( string='Payment Information')
    additional_requests = fields.Text( string='Additional Requests')

    # Users who performed actions
    confirmed_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Confirmed By',
        readonly=True,
        help='User who confirmed the application'
    )
    cancelled_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Cancelled By',
        readonly=True,
        help='User who cancelled the application'
    )
    business_unit_head_id = fields.Many2one(
        comodel_name='res.users',
        string='Business Unit Head',
        readonly=True
    )
    amended_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Amended By',
        readonly=True
    )
    finished_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Finished By',
        readonly=True
    )

    # Dates for various states
    confirmed_date = fields.Datetime(
        string='Confirmed Date', readonly=True,
        help='Date of Application Confirmation',
    )
    cancelled_date = fields.Datetime(
        string='Cancelled Date', readonly=True,
        help='Date of Application Cancellation'
    )
    buh_approval_date = fields.Datetime(
        string='Business Unit Head Approval Date', readonly=True,
        help='Date of Business Unit Head Approval'
    )
    amended_date = fields.Datetime(
        string='Amended Date', readonly=True
    )
    finished_date = fields.Datetime(
        string='Finished Date', readonly=True
    )

    # Onchange methods
    @api.onchange('application_type')
    def _onchange_application_type(self):
        if self.application_type == 'internal':
            self.partner_id = False
            self.organization_id = False
        elif self.application_type == 'external':
            self.employee_id = False
            self.department_id = False

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id.id
        else:
            self.department_id = False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        # Assume the partner itself is the organization for external applications
        self.organization_id = self.partner_id.id if self.partner_id else False



    # Compute QR Code based on the 'name' field
    @api.depends('name')
    def _compute_qr_code(self):
        for rec in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

            # Use correct model, and find relevant action and menu if possible
            action = self.env.ref('properties_management.action_meeting_room_application_form', raise_if_not_found=False)
            menu_item = self.env.ref('properties_management.menu_meeting_room_application', raise_if_not_found=False)

            action_id = action.id if action else ''
            menu_id = menu_item.id if menu_item else ''

            qr_link = f"{base_url}/web#id={rec.id}&model=hledan.meeting.room.application&view_type=form"
            if action_id:
                qr_link += f"&action={action_id}"
            if menu_id:
                qr_link += f"&menu_id={menu_id}"

            qr = qrcode.make(qr_link)
            buffer = io.BytesIO()
            qr.save(buffer, format='PNG')
            buffer.seek(0)
            rec.qr_code = base64.b64encode(buffer.read())

    # Compute attendee based on room capacity
    @api.depends('room_id')
    def _compute_attendee(self):
        for record in self:
            if record.room_id:
                # Example: Count employees related to room
                employees_count = self.env['hr.employee'].search_count([('room_id', '=', record.room_id.id)])
                partners_count = self.env['res.partner'].search_count([('room_id', '=', record.room_id.id)])
                record.attendee = employees_count + partners_count
            else:
                record.attendee = 0

    # State transition methods
    def action_tentative(self):
        self.write({'state': 'tentative'})

    def action_confirm(self):
        self.write({
            'state': 'confirmed',
            'confirmed_user_id': self.env.uid,
            'confirmed_date': fields.Datetime.now()
        })

    def action_amendment(self):
        self.write({
            'state': 'amendment',
            'amended_user_id': self.env.uid,
            'amended_date': fields.Datetime.now()
        })

    def action_cancel(self):
        self.write({
            'state': 'cancelled',
            'cancelled_user_id': self.env.uid,
            'cancelled_date': fields.Datetime.now()
        })

    def action_set_to_draft(self):
        self.write({'state': 'tentative'})

    def action_finished(self):
        self.write({
            'state': 'finished',
            'finished_user_id': self.env.uid,
            'finished_date': fields.Datetime.now()
        })

    # Onchange for room and meeting_type to compute pax_number and rate

