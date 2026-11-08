# Part of the mconfort_customer_photos module. Licensed under LGPL-3.

import base64
import json
from datetime import timedelta

from lxml import html

from odoo import fields
from odoo.fields import Command
from odoo.tests import HttpCase, tagged

from .test_customer_photo import Common, png


def raw_png(color='red'):
    return base64.b64decode(png(color))

PUBLISHED = [('is_published', '=', True), ('image_ids', '!=', False)]


@tagged('post_install', '-at_install')
class TestGallery(HttpCase, Common):
    def _approved(self, **vals):
        photo = self._submission(**vals)
        photo.action_approve()
        return photo

    def _doc(self, path):
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        return html.fromstring(response.content)

    def _card_ids(self, path):
        return [int(i) for i in self._doc(path).xpath('//a[contains(@class, "o_mcp_card")]/@data-id')]

    def _like(self, photo):
        return self.make_jsonrpc_request('/photos-clients/like', {'photo_id': photo.id})

    def test_public_sees_published_cards_only(self):
        pending = self._submission()
        approved = self._approved()
        ids = self._card_ids('/photos-clients')
        self.assertIn(approved.id, ids)
        self.assertNotIn(pending.id, ids)

    def test_published_submission_without_photo_is_left_out(self):
        empty = self._approved(image_ids=[])
        self.assertNotIn(empty.id, self._card_ids('/photos-clients'))
        self.assertFalse(self._doc(f'/photos-clients?open={empty.id}').xpath('//div[@id="wrap"]/@data-open'))

    def test_chip_counts_match_published_submissions(self):
        self._approved(product_id=self.sofa.id)
        self._approved(product_id=self.table.id)
        Photo = self.env['mconfort.customer.photo']
        empty_root = self.env['product.public.category'].create({'name': "Empty root test"})
        chips = {}
        for chip in self._doc('/photos-clients').xpath('//a[contains(@class, "o_mcp_chip")]'):
            chips[chip.get('href')] = ' '.join(chip.text_content().split())
        self.assertTrue(chips["/photos-clients"].endswith(f"({Photo.search_count(PUBLISHED)})"), chips)
        for root in (self.salon_root, self.dining_root):
            expected = f"{root.name} ({Photo.search_count(PUBLISHED + [('public_categ_id', '=', root.id)])})"
            self.assertEqual(chips[f'/photos-clients?categ={root.id}'], expected)
        self.assertNotIn(f'/photos-clients?categ={empty_root.id}', chips)
        self.assertNotIn(f'/photos-clients?categ={self.salon_child.id}', chips)

    def test_phone_category_select_mirrors_the_chips_and_travels_with_the_sort(self):
        self._approved(product_id=self.sofa.id)
        self._approved(product_id=self.table.id)
        doc = self._doc(f'/photos-clients?categ={self.salon_root.id}&sort=likes')
        form = doc.xpath('//form[contains(@class, "o_mcp_sortform")]')[0]
        options = form.xpath('.//select[@name="categ"]/option')
        chip_ids = [h.split('categ=')[1].split('&')[0]
                    for h in doc.xpath('//a[contains(@class, "o_mcp_chip")]/@href') if 'categ=' in h]
        self.assertEqual([o.get('value') for o in options], ['all'] + chip_ids)
        self.assertEqual([o.get('value') for o in options if o.get('selected') is not None], [str(self.salon_root.id)])
        self.assertEqual(len(form.xpath('.//label[@for="o_mcp_categ"]')), 1)
        self.assertEqual(len(form.xpath('.//label[@for="o_mcp_sort"]')), 1)
        self.assertEqual(form.xpath('.//select[@name="sort"]/option[@selected]/@value'), ['likes'])
        form = self._doc('/photos-clients').xpath('//form[contains(@class, "o_mcp_sortform")]')[0]
        self.assertEqual(form.xpath('.//select[@name="categ"]/option[@selected]/@value'), ['all'])

    def test_breadcrumb_and_the_single_upload_bar(self):
        doc = self._doc('/photos-clients')
        crumbs = doc.xpath('//ol[contains(@class, "o_mcp_breadcrumb")]/li')
        self.assertEqual(len(crumbs), 2)
        self.assertEqual(crumbs[0].xpath('./a/@href'), ['/'])
        self.assertFalse(doc.xpath('//ol[contains(@class, "o_mcp_breadcrumb")]//i[contains(@class, "fa-home")]'))
        bar = doc.xpath('//button[contains(@class, "o_mcp_cta_bar")]')
        self.assertEqual(len(bar), 1)
        self.assertNotIn('d-sm-none', bar[0].get('class'))
        self.assertFalse(doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " o_mcp_cta ")]'))
        self.assertEqual(len(doc.xpath('//*[contains(@class, "o_mcp_open_upload")]')), 1)
        lines = [' '.join(t.text_content().split()) for t in bar[0].xpath('.//strong | .//span[@class="o_mcp_cta_bar_text"]/span')]
        self.assertEqual(lines, ["Envoyez-nous votre intérieur", "Partagez une photo de votre achat M'Confort"])

    def test_cards_are_plain_photos_and_the_details_are_in_the_lightbox(self):
        photo = self._approved(product_id=self.sofa.id, city="Kaweni")
        doc = self._doc('/photos-clients')
        card = doc.xpath(f'//a[@data-id="{photo.id}"]')[0]
        self.assertTrue(card.xpath('.//img'))
        self.assertFalse(card.xpath('.//*[contains(@class, "o_mcp_pill")]'))
        self.assertFalse(card.xpath('.//figcaption'))
        self.assertNotIn("Salon LEXUS", card.text_content())
        self.assertNotIn("purchase", card.text_content().lower())
        lightbox = doc.xpath('//div[contains(@class, "o_mcp_lightbox")]')[0]
        self.assertTrue(lightbox.xpath('.//*[contains(@class, "o_mcp_pill_verified")]'))
        self.assertTrue(lightbox.xpath('.//*[@data-slot="product"]'))
        self.assertTrue(lightbox.xpath('.//*[@data-slot="likes"]'))
        self.assertEqual(json.loads(card.get('data-lightbox'))['product'], "Salon LEXUS")

    def test_chips_keep_the_sort(self):
        self._approved(product_id=self.sofa.id)
        hrefs = self._doc('/photos-clients?sort=likes').xpath('//a[contains(@class, "o_mcp_chip")]/@href')
        self.assertIn('/photos-clients?sort=likes', hrefs)
        self.assertIn(f'/photos-clients?categ={self.salon_root.id}&sort=likes', hrefs)

    def test_category_filter(self):
        salon = self._approved(product_id=self.sofa.id)
        dining = self._approved(product_id=self.table.id)
        ids = self._card_ids(f'/photos-clients?categ={self.salon_root.id}')
        self.assertIn(salon.id, ids)
        self.assertNotIn(dining.id, ids)
        ids = self._card_ids(f'/photos-clients?categ={self.dining_root.id}')
        self.assertIn(dining.id, ids)
        self.assertNotIn(salon.id, ids)

    def test_unknown_filter_and_sort_fall_back(self):
        photo = self._approved()
        self.assertIn(photo.id, self._card_ids('/photos-clients?categ=nope&sort=nope'))
        self.assertIn(photo.id, self._card_ids(f'/photos-clients?categ={self.salon_child.id}'))
        self.assertIn(photo.id, self._card_ids('/photos-clients?categ=salon'))

    def test_sort_recent_then_most_liked(self):
        older = self._approved(like_count=5)
        newer = self._approved(like_count=1)
        recent = self._card_ids('/photos-clients')
        self.assertLess(recent.index(newer.id), recent.index(older.id))
        liked = self._card_ids('/photos-clients?sort=likes')
        self.assertLess(liked.index(older.id), liked.index(newer.id))

    def test_like_toggles_once_per_session(self):
        photo = self._approved(like_count=3)
        self.assertEqual(self._like(photo), {'liked': True, 'count': 4})
        self.assertEqual(self._like(photo), {'liked': False, 'count': 3})
        self.assertEqual(photo.like_count, 3)

    def test_liked_state_comes_back_in_the_card(self):
        photo = self._approved()
        self._like(photo)
        card = self._doc('/photos-clients').xpath(f'//a[@data-id="{photo.id}"]/@data-lightbox')[0]
        data = json.loads(card)
        self.assertTrue(data['liked'])
        self.assertEqual(data['likes'], 1)

    def test_unpublished_photo_cannot_be_liked(self):
        pending = self._submission()
        self.assertEqual(self._like(pending), {'error': 'not_found'})
        self.assertEqual(pending.like_count, 0)

    def test_card_carries_everything_the_lightbox_shows(self):
        photo = self._approved(product_id=self.sofa.id, city="Kaweni", comment="Super")
        card = json.loads(self._doc('/photos-clients').xpath(f'//a[@data-id="{photo.id}"]/@data-lightbox')[0])
        self.assertEqual(card['author'], "Mehdi F.")
        self.assertEqual((card['product'], card['city'], card['comment']), ("Salon LEXUS", "Kaweni", "Super"))
        self.assertEqual(len(card['photos']), 1)
        self.assertIn(f"/web/image/mconfort.customer.photo.image/{photo.image_ids.id}/image_1920", card['photos'][0]['full'])

    def test_product_name_links_to_the_product_only_when_it_is_published(self):
        photo = self._approved(product_id=self.sofa.id)
        card = lambda: json.loads(self._doc('/photos-clients').xpath(f'//a[@data-id="{photo.id}"]/@data-lightbox')[0])  # noqa: E731
        self.sofa.is_published = True
        self.assertEqual(card()['product_url'], self.sofa.website_url)
        self.assertTrue(card()['product_url'].startswith('/shop/'))
        self.sofa.is_published = False
        self.assertEqual(card()['product_url'], '')
        bare = self._approved()
        data = json.loads(self._doc('/photos-clients').xpath(f'//a[@data-id="{bare.id}"]/@data-lightbox')[0])
        self.assertEqual(data['product_url'], '')

    def test_deep_link_opens_a_published_photo_even_when_filtered_out(self):
        photo = self._approved(product_id=self.sofa.id)
        doc = self._doc(f'/photos-clients?categ={self.dining_root.id}&open={photo.id}')
        self.assertEqual(json.loads(doc.xpath('//div[@id="wrap"]/@data-open')[0])['id'], photo.id)

    def test_deep_link_ignores_unpublished_and_garbage(self):
        pending = self._submission()
        for value in (pending.id, 'abc', 0, 999999999):
            doc = self._doc(f'/photos-clients?open={value}')
            self.assertFalse(doc.xpath('//div[@id="wrap"]/@data-open'), value)


@tagged('post_install', '-at_install')
class TestSubmit(HttpCase, Common):
    LAST = "Zxqtest"

    def _csrf(self):
        page = html.fromstring(self.url_open('/photos-clients').content)
        return page.xpath('//form[contains(@class, "o_mcp_upload_form")]//input[@name="csrf_token"]/@value')[0]

    def _post(self, photos=None, csrf=True, **fields):
        data = {'firstname': "Mehdi", 'lastname': self.LAST, 'comment': "Super salon", **fields}
        if csrf:
            data['csrf_token'] = self._csrf()
        files = [('photos', (name, content, 'image/png')) for name, content in (photos if photos is not None else [('a.png', raw_png())])]
        return self.url_open('/photos-clients/submit', data=data, files=files or None)

    def _created(self):
        return self.env['mconfort.customer.photo'].search([('lastname', '=', self.LAST)])

    def test_valid_submission_is_pending_with_its_photos(self):
        response = self._post(photos=[('a.png', raw_png('red')), ('b.png', raw_png('blue'))])
        self.assertEqual((response.status_code, response.json()), (200, {'ok': True}))
        photo = self._created()
        self.assertEqual((photo.state, photo.is_published, photo.name, photo.comment),
                         ('pending', False, "Mehdi Z.", "Super salon"))
        self.assertEqual(photo.image_ids.mapped('sequence'), [0, 1])
        self.assertEqual(photo.submitter_ip, '127.0.0.1')
        self.assertFalse(photo.partner_id)
        self.assertTrue(photo.activity_ids)

    def test_pending_submission_stays_off_the_gallery(self):
        self._post()
        self.assertNotIn(self._created().id, self._card_ids_public())

    def _card_ids_public(self):
        doc = html.fromstring(self.url_open('/photos-clients').content)
        return [int(i) for i in doc.xpath('//a[contains(@class, "o_mcp_card")]/@data-id')]

    def test_not_an_image_is_refused(self):
        response = self._post(photos=[('a.png', b"just text, not an image")])
        self.assertEqual((response.status_code, response.json()), (400, {'error': 'file'}))
        self.assertFalse(self._created())

    def test_svg_is_refused_even_if_named_png(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        response = self._post(photos=[('a.png', svg)])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self._created())

    def test_one_bad_file_refuses_the_whole_submission(self):
        response = self._post(photos=[('a.png', raw_png()), ('b.png', b"nope")])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self._created())

    def test_file_over_8_mb_is_refused(self):
        response = self._post(photos=[('a.png', raw_png() + b'0' * (8 * 1024 * 1024))])
        self.assertEqual((response.status_code, response.json()), (400, {'error': 'file'}))
        self.assertFalse(self._created())

    def test_nine_photos_is_too_many_and_eight_is_fine(self):
        response = self._post(photos=[(f'{i}.png', raw_png()) for i in range(9)])
        self.assertEqual((response.status_code, response.json()), (400, {'error': 'too_many'}))
        self.assertFalse(self._created())
        self.assertEqual(self._post(photos=[(f'{i}.png', raw_png()) for i in range(8)]).status_code, 200)
        self.assertEqual(len(self._created().image_ids), 8)

    def test_name_and_photo_are_required(self):
        for fields, photos in (({'lastname': "  "}, None), ({'firstname': ''}, None), ({}, [])):
            response = self._post(photos=photos, **fields)
            self.assertEqual((response.status_code, response.json()), (400, {'error': 'invalid'}), fields)
        self.assertFalse(self._created())

    def test_honeypot_answers_ok_and_creates_nothing(self):
        response = self._post(hp_url="http://spam.example")
        self.assertEqual((response.status_code, response.json()), (200, {'ok': True}))
        self.assertFalse(self._created())

    def test_csrf_token_is_required(self):
        self.assertEqual(self._post(csrf=False).status_code, 400)
        self.assertFalse(self._created())

    def test_review_is_cut_at_1000_characters(self):
        self._post(comment="x" * 1500)
        self.assertEqual(len(self._created().comment), 1000)

    def test_sixth_submission_in_ten_minutes_from_one_ip_is_refused(self):
        for _i in range(5):
            self._submission(submitter_ip='127.0.0.1')
        response = self._post()
        self.assertEqual((response.status_code, response.json()), (429, {'error': 'rate'}))
        self.assertFalse(self._created())

    def test_old_submissions_do_not_count_for_the_rate_limit(self):
        old = self.env['mconfort.customer.photo']
        for _i in range(5):
            old |= self._submission(submitter_ip='127.0.0.1')
        eleven_minutes_ago = fields.Datetime.now() - timedelta(minutes=11)
        self.env.cr.execute("UPDATE mconfort_customer_photo SET create_date = %s WHERE id IN %s", [eleven_minutes_ago, tuple(old.ids)])
        old.invalidate_recordset()
        self.assertEqual(self._post().status_code, 200)

    def test_logged_in_customer_is_prefilled_and_linked(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': "Nadia Boinali", 'login': 'mcp_customer', 'password': 'Mcp-Customer-123!',
            'group_ids': [Command.set([self.env.ref('base.group_portal').id])],
        })
        self.authenticate('mcp_customer', 'Mcp-Customer-123!')
        page = html.fromstring(self.url_open('/photos-clients').content)
        self.assertEqual(page.xpath('//input[@name="firstname"]/@value'), ["Nadia"])
        self.assertEqual(page.xpath('//input[@name="lastname"]/@value'), ["Boinali"])
        self.assertEqual(self._post(lastname="Boinali").status_code, 200)
        photo = self.env['mconfort.customer.photo'].search([('lastname', '=', "Boinali")])
        self.assertEqual(photo.partner_id, user.partner_id)

    WEBP_LOSSY = base64.b64decode(
        "UklGRvIBAABXRUJQVlA4IOYBAABwDACdASowACAAPm00lUgkIqIhJWmYgA2JbACxHv/zf4B+NPEH7gHiKbgD9eP1y7AHoAdIBz6Xsa/uB+s3s5ZhKfABqiH875Avk72A/013xb9o1CsPWPmAhrs96ailI77BxiYf7dxXGWEk4gAA/rE+2Obn/2nxngDy3GfonzhmmymENLhdRq9fsLIu8YaV262e3xz//zr6mM5XY3mo91a//7DP1gP0uuQu+9hnYT/n9afidT0tknfFdcOL7oebn02mVbKQ//MWiDvwbJb77OSFcedY0o2Fu1XQEtlLeP0j1fwB/b/XleIq04unffTz/utsoxMChbX5Nny/Uhxy/otCbtNs/gnb5Z8mPuPSZqZEtCj2L830gKogvXdw2sz2vl+/Pl8e8nnZfjOEY4oI5UfJ0N5XjPW5qxqU4P3vDZ17I5R8v+v/5/w92/o4cD1BF5DTFffJGrPsYpPjvb9xO/GPOOD6G0P3hxyyj63uux3r0LLQVDbB/5N/m2Q6oggEcezIOAvJiIZ4AcCtR14jhgacBya/mAMfy++TKCfMNJMdAW0N7sTYXdy2yFhvoIjcBLGr0jo+m/WEsKSzqnfzax0oS2MrsdKvyG5P1pfWXvrYVW+YjkEUtZo/brffupGh0Zp5sfAAAAA=")
    WEBP_LOSSLESS = base64.b64decode(
        "UklGRl4AAABXRUJQVlA4TFEAAAAvL8AHAA8w//M///MfWnAUybbVdAoBSHhSkAZSkfCW+c+SxEFE/yfAH+eAbzhq4ayVWYN7bbxr51tdqbr94Vu58K6de23MGpy1ctSCbzCHHwIA")

    def _raw(self, fmt):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (80, 60), 'red').save(buf, format=fmt)
        return buf.getvalue()

    def test_jpeg_png_webp_gif_are_accepted_and_stored(self):
        samples = {
            'JPEG': self._raw('JPEG'), 'PNG': self._raw('PNG'), 'GIF': self._raw('GIF'),
            'WEBP lossy': self.WEBP_LOSSY, 'WEBP lossless': self.WEBP_LOSSLESS,
        }
        for label, raw in samples.items():
            last = self.LAST + label.replace(' ', '')
            response = self._post(photos=[(f'a.{label[:4].lower()}', raw)], lastname=last)
            self.assertEqual((label, response.status_code), (label, 200), response.text)
            photo = self.env['mconfort.customer.photo'].search([('lastname', '=', last)])
            self.assertTrue(photo.image_ids.image_512, label)

    def test_other_image_formats_are_refused(self):
        tiff_header = b'II*\x00\x08\x00\x00\x00' + b'\x00' * 64
        for label, raw in (('BMP', self._raw('BMP')), ('TIFF', tiff_header)):
            response = self._post(photos=[(f'a.{label.lower()}', raw)])
            self.assertEqual((label, response.status_code, response.json()), (label, 400, {'error': 'file'}))
        self.assertFalse(self._created())

    def test_webp_is_stored_as_a_small_resized_jpeg(self):
        import io
        import random
        from PIL import Image, WebPImagePlugin  # noqa: F401
        rnd = random.Random(1)
        noise = Image.frombytes('RGB', (360, 240), bytes(rnd.randrange(256) for _ in range(360 * 240 * 3)))
        big = noise.resize((3600, 2400))
        buf = io.BytesIO()
        big.save(buf, format='WEBP', quality=90)
        webp = buf.getvalue()
        self.assertEqual(webp[:4], b'RIFF')
        response = self._post(photos=[('big.webp', webp)])
        self.assertEqual(response.status_code, 200, response.text)
        image = self._created().image_ids
        for field in ('image_1920', 'image_512', 'image_256'):
            data = base64.b64decode(image[field])
            self.assertEqual(data[:3], b'\xff\xd8\xff', f"{field} is not a JPEG")
        self.assertLessEqual(max(Image.open(io.BytesIO(base64.b64decode(image.image_1920))).size), 1920)
        self.assertLess(len(base64.b64decode(image.image_512)), len(webp) / 4)

    def test_webp_with_transparency_and_animation_is_accepted(self):
        import io
        from PIL import Image, WebPImagePlugin  # noqa: F401
        frames = [Image.new('RGBA', (60, 40), (255, 0, 0, a)) for a in (0, 128, 255)]
        buf = io.BytesIO()
        frames[0].save(buf, format='WEBP', save_all=True, append_images=frames[1:], duration=100)
        self.assertEqual(self._post(photos=[('anim.webp', buf.getvalue())]).status_code, 200)
        self.assertTrue(self._created().image_ids.image_512)

    def test_extension_and_mimetype_do_not_matter_only_the_content(self):
        self.assertEqual(self._post(photos=[('holiday.jpg', self.WEBP_LOSSY)]).status_code, 200)
        for name, raw in (('fake.webp', b'not an image'), ('cut.webp', self.WEBP_LOSSY[:15]), ('cut2.webp', self.WEBP_LOSSY[:20])):
            response = self._post(photos=[(name, raw)], lastname=self.LAST + 'x')
            self.assertEqual((name, response.status_code), (name, 400))
        self.assertFalse(self.env['mconfort.customer.photo'].search([('lastname', '=', self.LAST + 'x')]))


@tagged('post_install', '-at_install')
class TestFeatured(HttpCase, Common):
    def _featured(self, **params):
        return self.make_jsonrpc_request('/photos-clients/featured', params)

    def _approved(self, **vals):
        photo = self._submission(**vals)
        photo.action_approve()
        return photo

    def test_featured_first_then_latest_published_only(self):
        oldest_featured = self._approved(featured=True)
        older = self._approved()
        newer = self._approved()
        pending = self._submission()
        ids = [p['id'] for p in self._featured(limit=6)]
        self.assertNotIn(pending.id, ids)
        self.assertEqual([i for i in ids if i in (oldest_featured.id, newer.id, older.id)],
                         [oldest_featured.id, newer.id, older.id])

    def test_limit_is_respected_and_garbage_falls_back_to_three(self):
        for _i in range(4):
            self._approved()
        self.assertEqual(len(self._featured(limit=2)), 2)
        self.assertEqual(len(self._featured(limit=99)), 3)
        self.assertEqual(len(self._featured(limit="x")), 3)
        self.assertEqual(len(self._featured()), 3)

    def test_item_carries_what_the_block_draws(self):
        photo = self._approved(product_id=self.sofa.id, city="Kaweni", featured=True)
        item = next(p for p in self._featured(limit=6) if p['id'] == photo.id)
        self.assertEqual(item['url'], f"/photos-clients?open={photo.id}")
        self.assertEqual((item['alt'], item['caption']), ("Salon LEXUS", "Client M'Confort – Kaweni"))
        self.assertIn(f"/web/image/mconfort.customer.photo.image/{photo.image_ids.id}/image_1024", item['image'])

    def test_caption_without_city(self):
        photo = self._approved(featured=True)
        item = next(p for p in self._featured(limit=6) if p['id'] == photo.id)
        self.assertEqual((item['caption'], item['alt']), ("Client M'Confort", "Mehdi F."))

    def test_published_submission_without_photo_is_left_out(self):
        empty = self._approved(image_ids=[], featured=True)
        self.assertNotIn(empty.id, [p['id'] for p in self._featured(limit=6)])


@tagged('post_install', '-at_install')
class TestUploadPicture(HttpCase, Common):
    def _aside(self):
        page = html.fromstring(self.url_open('/photos-clients').content)
        return page.xpath('//aside[contains(@class, "o_mcp_up_aside")]')[0]

    def test_no_picture_keeps_the_plain_panel(self):
        self.env['website'].get_current_website().customer_photos_upload_image = False
        aside = self._aside()
        self.assertNotIn('has_image', aside.get('class'))
        self.assertFalse(aside.get('style'))

    def test_picture_set_on_the_website_shows_and_is_public(self):
        website = self.env['website'].get_current_website()
        website.customer_photos_upload_image = png('green', size=(900, 1200))
        aside = self._aside()
        self.assertIn('has_image', aside.get('class'))
        url = aside.get('style').split('url(')[1].split(')')[0]
        self.assertTrue(url.startswith(f'/web/image/website/{website.id}/customer_photos_upload_image/'), url)
        response = self.url_open(url + '&download=true' if '?' in url else url + '?download=true')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['Content-Type'].startswith('image/'))

    def test_settings_screen_reads_the_website_picture(self):
        website = self.env['website'].get_current_website()
        website.customer_photos_upload_image = png()
        settings = self.env['res.config.settings'].create({'website_id': website.id})
        self.assertEqual(settings.customer_photos_upload_image, website.customer_photos_upload_image)
