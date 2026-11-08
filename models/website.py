# Part of the mconfort_customer_photos module. Licensed under LGPL-3.

from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    customer_photos_upload_image = fields.Image(
        string="Upload Picture", max_width=1920, max_height=1920,
        help="Picture shown in the upload window.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    customer_photos_upload_image = fields.Image(
        related='website_id.customer_photos_upload_image', readonly=False)
