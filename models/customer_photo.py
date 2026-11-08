# Part of the mconfort_customer_photos module. Licensed under LGPL-3.

from odoo import _, api, fields, models
from odoo.tools.misc import format_date


class CustomerPhoto(models.Model):
    """One submission: a customer, their photos, an optional review.

    Lifecycle: pending (just submitted, validators get an activity) -> approved
    (published on the website) or rejected (never shown)."""
    _name = 'mconfort.customer.photo'
    _description = "Customer Photo"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'website.published.mixin']
    _order = 'submitted_on desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    firstname = fields.Char(string="First Name", required=True)
    lastname = fields.Char(string="Last Name", required=True)
    # No help= on the fields shown in the form: the back office wants no "?" tooltips.
    # (Customer: set automatically when logged in. City: shown as "Client M'Confort – <city>".)
    partner_id = fields.Many2one('res.partner', string="Customer", index=True)
    comment = fields.Text(string="Review")
    city = fields.Char()

    image_ids = fields.One2many('mconfort.customer.photo.image', 'submission_id', string="Photos", copy=True)
    image_count = fields.Integer(compute='_compute_cover_image')
    cover_image_id = fields.Many2one('mconfort.customer.photo.image', compute='_compute_cover_image')
    cover_image_128 = fields.Image(related='cover_image_id.image_128')
    cover_image_512 = fields.Image(related='cover_image_id.image_512')

    # Product fills the category (first-level shop category: Salon > Canapé gives Salon), which drives the
    # website's filter chips; the category can still be changed by hand.
    product_id = fields.Many2one('product.template', string="Product")
    public_categ_id = fields.Many2one(
        'product.public.category', string="Category", index=True, ondelete='set null',
        domain="[('parent_id', '=', False)]",
        compute='_compute_public_categ_id', store=True, readonly=False)
    sale_order_id = fields.Many2one('sale.order', string="Sale Order",
                                    domain="[('partner_id', 'child_of', partner_id)] if partner_id else []")

    state = fields.Selection([
        ('pending', "To Validate"),
        ('approved', "Approved"),
        ('rejected', "Rejected"),
    ], default='pending', required=True, tracking=True, index=True)
    reject_reason = fields.Text()
    featured = fields.Boolean()  # featured ones come first in the home page block
    like_count = fields.Integer(default=0)
    submitted_on = fields.Datetime(default=fields.Datetime.now, required=True)
    submitter_ip = fields.Char(groups='base.group_user')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends('firstname', 'lastname')
    def _compute_name(self):
        for rec in self:
            first = (rec.firstname or '').strip()
            last = (rec.lastname or '').strip()
            rec.name = f"{first} {last[:1].upper()}." if last else first

    @api.depends('image_ids.sequence')
    def _compute_cover_image(self):
        for rec in self:
            # Sort explicitly: right after creation the one2many cache keeps creation order.
            images = rec.image_ids.sorted(lambda i: (i.sequence, i.id or 0))
            rec.image_count = len(images)
            rec.cover_image_id = images[:1]

    @api.depends('product_id.public_categ_ids')
    def _compute_public_categ_id(self):
        Categ = self.env['product.public.category']
        for rec in self:
            # parent_path is "<root>/<child>/.../": its first id is the first-level ancestor.
            # A product in several trees gets the first root in the shop's own category order.
            roots = Categ.browse({int(c.parent_path.split('/')[0]) for c in rec.product_id.public_categ_ids if c.parent_path})
            rec.public_categ_id = roots.sorted(lambda r: (r.sequence, r.id))[:1]

    @api.depends_context('lang')
    def _compute_website_url(self):
        super()._compute_website_url()
        for rec in self:
            if rec.id:
                rec.website_url = f"/photos-clients?open={rec.id}"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_validators()
        return records

    def _notify_validators(self):
        validators = self.env.ref('mconfort_customer_photos.group_manager').all_user_ids
        for rec in self.filtered(lambda r: r.state == 'pending'):
            for user in validators:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary=_("New customer photo to validate"),
                )

    # ------------------------------------------------------------------
    # Website
    # ------------------------------------------------------------------

    def _gallery_values(self, liked_ids=()):
        """What the gallery card and the lightbox need, one dict per record.

        Everything the lightbox shows travels in the card (JSON in a data attribute), so
        there is no detail route. Call on sudo records of published submissions only."""
        website = self.env['website']
        values = []
        for rec in self:
            images = rec.image_ids.sorted(lambda i: (i.sequence, i.id))
            values.append({
                'id': rec.id,
                'author': rec.name,
                'product': rec.product_id.name or '',
                # Link only to a product the shop shows; an unpublished one would 404 for visitors.
                'product_url': rec.product_id.website_url if rec.product_id.is_published else '',
                'city': rec.city or '',
                'date': format_date(self.env, rec.submitted_on, date_format='MMMM yyyy').capitalize(),
                'comment': rec.comment or '',
                'likes': rec.like_count,
                'liked': rec.id in liked_ids,
                'image': website.image_url(images[:1], 'image_512') if images else '',
                'photos': [{'full': website.image_url(img, 'image_1920'),
                            'thumb': website.image_url(img, 'image_256')} for img in images],
            })
        return values

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_approve(self):
        self.write({'state': 'approved', 'is_published': True, 'reject_reason': False})
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reject(self):
        # The reason is optional: a note for the team, never shown on the website.
        self.write({'state': 'rejected', 'is_published': False, 'featured': False})
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reset_to_pending(self):
        self.write({'state': 'pending', 'is_published': False})


class CustomerPhotoImage(models.Model):
    """One photo of a submission. `image.mixin` gives the 1920/1024/512/256/128 variants.

    The related `website_published` is what lets `/web/image/<model>/<id>/image_512`
    serve approved photos to the public: website's `_can_return_content` grants
    read on binary fields when that field is True."""
    _name = 'mconfort.customer.photo.image'
    _description = "Customer Photo Image"
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    submission_id = fields.Many2one('mconfort.customer.photo', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char()
    image_1920 = fields.Image(required=True, max_width=1920, max_height=1920)
    website_published = fields.Boolean(related='submission_id.website_published')
