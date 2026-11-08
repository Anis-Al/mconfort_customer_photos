# Part of the mconfort_customer_photos module. Licensed under LGPL-3.

import base64
import io

from PIL import Image

from odoo.fields import Command
from odoo.tests import HttpCase, TransactionCase, tagged


def png(color='red', size=(64, 48)):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, format='PNG')
    return base64.b64encode(buf.getvalue())


class Common(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref('mconfort_customer_photos.group_manager')
        cls.validator = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': "Val Idator",
            'login': 'mcp_validator',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id, cls.group.id])],
        })
        cls.validator_2 = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': "Val Idator 2",
            'login': 'mcp_validator_2',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id, cls.group.id])],
        })
        cls.salon_root = cls.env['product.public.category'].create({'name': "Salon test"})
        cls.salon_child = cls.env['product.public.category'].create({'name': "Canapé test", 'parent_id': cls.salon_root.id})
        cls.dining_root = cls.env['product.public.category'].create({'name': "Salle à manger test"})
        cls.sofa = cls.env['product.template'].create({'name': "Salon LEXUS", 'public_categ_ids': [Command.set([cls.salon_child.id])]})
        cls.table = cls.env['product.template'].create({'name': "Table MIAMI", 'public_categ_ids': [Command.set([cls.dining_root.id])]})
        cls.lamp = cls.env['product.template'].create({'name': "Lampe"})
        cls.partner = cls.env['res.partner'].create({'name': "Mehdi Ferreux"})

    @classmethod
    def _submission(cls, **vals):
        vals = {
            'firstname': "Mehdi",
            'lastname': "ferreux",
            'image_ids': [Command.create({'image_1920': png()})],
            **vals,
        }
        return cls.env['mconfort.customer.photo'].create(vals)


@tagged('post_install', '-at_install')
class TestCustomerPhoto(Common):

    def test_name_is_first_name_and_initial(self):
        self.assertEqual(self._submission().name, "Mehdi F.")

    def test_creation_schedules_one_todo_per_validator(self):
        photo = self._submission()
        todos = photo.activity_ids.filtered(lambda a: a.activity_type_id == self.env.ref('mail.mail_activity_data_todo'))
        # >= : administrators imply the group, so real users on mconfort get a todo too.
        self.assertGreaterEqual(set(todos.mapped('user_id')), {self.validator, self.validator_2})
        self.assertEqual(len(todos), len(self.group.all_user_ids))

    def test_category_is_the_first_level_shop_category_of_the_product(self):
        # Salon > Canapé gives Salon; a product directly in a root category gives that root
        self.assertEqual(self._submission(product_id=self.sofa.id).public_categ_id, self.salon_root)
        self.assertEqual(self._submission(product_id=self.table.id).public_categ_id, self.dining_root)
        # no category on the product, or no product: none
        self.assertFalse(self._submission(product_id=self.lamp.id).public_categ_id)
        self.assertFalse(self._submission().public_categ_id)

    def test_category_follows_the_shop_order_when_the_product_is_in_two_trees(self):
        self.dining_root.sequence = 1
        self.salon_root.sequence = 2
        both = self.env['product.template'].create({
            'name': "Pack", 'public_categ_ids': [Command.set([self.salon_child.id, self.dining_root.id])]})
        self.assertEqual(self._submission(product_id=both.id).public_categ_id, self.dining_root)

    def test_category_can_be_changed_by_hand_and_follows_a_new_product(self):
        photo = self._submission(product_id=self.sofa.id)
        photo.public_categ_id = self.dining_root
        self.assertEqual(photo.public_categ_id, self.dining_root)
        photo.product_id = self.table
        photo.product_id = self.sofa
        self.assertEqual(photo.public_categ_id, self.salon_root)

    def test_approve_publishes_and_closes_the_todo(self):
        photo = self._submission()
        photo.with_user(self.validator).action_approve()
        self.assertEqual(photo.state, 'approved')
        self.assertTrue(photo.is_published)
        self.assertTrue(photo.image_ids.website_published)
        self.assertFalse(photo.activity_ids)

    def test_reject_reason_is_optional(self):
        for reason in (False, "Blurry"):
            photo = self._submission(reject_reason=reason, featured=True)
            photo.action_reject()
            self.assertEqual(photo.state, 'rejected')
            self.assertFalse(photo.is_published)
            self.assertFalse(photo.featured)
            self.assertFalse(photo.activity_ids)
            self.assertEqual(photo.reject_reason, reason)

    def test_cover_is_the_first_photo_by_sequence(self):
        photo = self._submission(image_ids=[
            Command.create({'image_1920': png('red'), 'sequence': 20}),
            Command.create({'image_1920': png('blue'), 'sequence': 10}),
        ])
        self.assertEqual(photo.image_count, 2)
        self.assertEqual(photo.cover_image_id.sequence, 10)

    def test_kanban_declares_every_field_its_template_reads(self):
        # `record.<name>.raw_value` is undefined in the browser unless <field name="<name>"/> is in
        # the arch: the card then crashes (OwlError) as soon as one record exists.
        import re
        from lxml import etree
        arch = self.env['mconfort.customer.photo'].get_views([(False, 'kanban')])['views']['kanban']['arch']
        root = etree.fromstring(arch)
        declared = set(root.xpath('//field/@name'))
        used = set(re.findall(r'record\.(\w+)', ' '.join(root.xpath('//@*[contains(., "record.")]'))))
        self.assertFalse(used - declared, used - declared)

    def test_cron_erases_ips_older_than_a_day_and_keeps_recent_ones(self):
        from datetime import timedelta
        from odoo import fields
        old = self._submission(submitter_ip='10.0.0.1')
        recent = self._submission(submitter_ip='10.0.0.2')
        # create_date is set by the ORM: backdate it in SQL (with the Python clock, PG's is not UTC here)
        self.env.cr.execute("UPDATE mconfort_customer_photo SET create_date = %s WHERE id = %s",
                            [fields.Datetime.now() - timedelta(days=2), old.id])
        old.invalidate_recordset()
        self.env['mconfort.customer.photo']._cron_purge_submitter_ip()
        self.assertFalse(old.submitter_ip)
        self.assertEqual(recent.submitter_ip, '10.0.0.2')
        self.assertTrue(self.env.ref('mconfort_customer_photos.ir_cron_purge_submitter_ip').active)

    def test_website_url_opens_the_lightbox(self):
        photo = self._submission()
        self.assertEqual(photo.website_url, f"/photos-clients?open={photo.id}")

    def test_public_user_only_sees_published_submissions(self):
        pending = self._submission()
        approved = self._submission()
        approved.action_approve()
        public = self.env.ref('base.public_user')
        visible = self.env['mconfort.customer.photo'].with_user(public).search([])
        self.assertIn(approved, visible)
        self.assertNotIn(pending, visible)


@tagged('post_install', '-at_install')
class TestCustomerPhotoBinary(HttpCase, Common):

    def _image_url(self, photo):
        return f"/web/image/mconfort.customer.photo.image/{photo.image_ids[0].id}/image_512"

    def test_approved_photo_is_served_to_the_public(self):
        photo = self._submission()
        photo.action_approve()
        response = self.url_open(self._image_url(photo))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['Content-Type'].startswith('image/'))

    def test_pending_photo_is_not_served_to_the_public(self):
        # Without ?download=true /web/image hides access errors behind the placeholder image (200),
        # with it the access error becomes a 404.
        photo = self._submission()
        response = self.url_open(self._image_url(photo) + '?download=true')
        self.assertEqual(response.status_code, 404)

    def test_approved_photo_can_be_downloaded_by_the_public(self):
        photo = self._submission()
        photo.action_approve()
        response = self.url_open(self._image_url(photo) + '?download=true')
        self.assertEqual(response.status_code, 200)
