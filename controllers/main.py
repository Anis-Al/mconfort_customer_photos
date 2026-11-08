# Part of the mconfort_customer_photos module. Licensed under LGPL-3.

import base64
import io
import json
from datetime import timedelta

from PIL import Image
from werkzeug import urls

from odoo import _, _lt, fields, http
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.http import request
from odoo.tools.image import get_webp_size

MAX_PHOTOS = 8
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000
PHOTO_FORMATS = {'JPEG', 'PNG', 'GIF'}
RATE_LIMIT = (5, timedelta(minutes=10))
SORTS = {
    'recent': 'submitted_on desc, id desc',
    'likes': 'like_count desc, submitted_on desc, id desc',
}


class CustomerPhotos(http.Controller):
    _per_page = 24

    @http.route(['/photos-clients', '/photos-clients/page/<int:page>'],
                type='http', auth='public', website=True, sitemap=True, readonly=True,
                list_as_website_content=_lt("Customer Photos"))
    def gallery(self, page=1, categ='all', sort='recent', open=0, **kw):
        Photo = request.env['mconfort.customer.photo'].sudo()
        sort = sort if sort in SORTS else 'recent'
        published = [('is_published', '=', True), ('image_ids', '!=', False)]

        groups = Photo._read_group(published, ['public_categ_id'], ['__count'])
        total_all = sum(count for _categ, count in groups)
        chips = sorted(((c, n) for c, n in groups if c), key=lambda g: (g[0].sequence, g[0].id))
        chip_ids = {c.id for c, _n in chips}
        categ = int(categ) if str(categ).isdigit() and int(categ) in chip_ids else 'all'
        domain = published + ([('public_categ_id', '=', categ)] if categ != 'all' else [])

        def chip_url(categ_id):
            args = {k: v for k, v in (('categ', categ_id), ('sort', sort)) if v not in ('all', 'recent')}
            return '/photos-clients' + ('?' + urls.url_encode(args) if args else '')

        chips = [{'id': c.id, 'name': c.name, 'count': n, 'url': chip_url(c.id)} for c, n in chips]
        all_url = chip_url('all')
        url_args = {k: v for k, v in (('categ', categ), ('sort', sort)) if v not in ('all', 'recent')}
        pager = request.website.pager(url='/photos-clients', total=Photo.search_count(domain),
                                      page=page, step=self._per_page, url_args=url_args)
        photos = Photo.search(domain, order=SORTS[sort], offset=pager['offset'], limit=self._per_page)

        liked = request.session.get('mcp_likes', [])
        cards = photos._gallery_values(liked)
        for card in cards:
            card['json'] = json.dumps(card)

        open_card = None
        if str(open).isdigit() and int(open):
            target = Photo.search(published + [('id', '=', int(open))])
            if target:
                open_card = json.dumps(target._gallery_values(liked)[0])

        user = request.env.user
        first, _sep, last = ('' if user._is_public() else user.partner_id.name or '').partition(' ')

        website = request.website
        has_image = website.sudo().with_context(bin_size=True).customer_photos_upload_image
        upload_image = website.image_url(website, 'customer_photos_upload_image', '800x1100') if has_image else False

        return request.render('mconfort_customer_photos.gallery', {
            'upload_image': upload_image,
            'prefill_first': first,
            'prefill_last': last,
            'cards': cards,
            'pager': pager,
            'categ': categ,
            'sort': sort,
            'chips': chips,
            'all_url': all_url,
            'total_all': total_all,
            'open_card': open_card,
        })

    @staticmethod
    def _is_accepted_photo(raw):
        if raw[0:4] == b'RIFF' and raw[8:15] == b'WEBPVP8':
            try:
                size = get_webp_size(raw)
            except (IndexError, ValueError, UserError):
                return False
            return bool(size and size[0] > 0 and size[1] > 0)
        try:
            with Image.open(io.BytesIO(raw)) as img:
                return img.format in PHOTO_FORMATS
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _webp_to_jpeg(raw):
        from PIL import WebPImagePlugin  # noqa: F401, PLC0415
        try:
            with Image.open(io.BytesIO(raw)) as img:
                if img.width * img.height > MAX_PIXELS:
                    return None
                frame = img.convert('RGBA')
            flat = Image.new('RGB', frame.size, 'white')
            flat.paste(frame, mask=frame.getchannel('A'))
            out = io.BytesIO()
            flat.save(out, format='JPEG', quality=88, optimize=True)
            return out.getvalue()
        except Exception:  # noqa: BLE001
            return None

    @http.route('/photos-clients/submit', type='http', auth='public', website=True, methods=['POST'],
                max_content_length=MAX_PHOTOS * MAX_PHOTO_BYTES)
    def submit(self, firstname='', lastname='', comment='', hp_url='', **kw):
        if hp_url:
            return request.make_json_response({'ok': True})
        firstname, lastname = firstname.strip()[:60], lastname.strip()[:60]
        files = [f for f in request.httprequest.files.getlist('photos') if f.filename]
        if not (firstname and lastname) or not files:
            return request.make_json_response({'error': 'invalid'}, status=400)
        if len(files) > MAX_PHOTOS:
            return request.make_json_response({'error': 'too_many'}, status=400)

        images = []
        for sequence, upload in enumerate(files):
            raw = upload.read(MAX_PHOTO_BYTES + 1)
            if len(raw) > MAX_PHOTO_BYTES:
                return request.make_json_response({'error': 'file'}, status=400)
            if not self._is_accepted_photo(raw):
                return request.make_json_response({'error': 'file'}, status=400)
            if raw[0:4] == b'RIFF':
                raw = self._webp_to_jpeg(raw)
                if not raw:
                    return request.make_json_response({'error': 'file'}, status=400)
            images.append(Command.create({'image_1920': base64.b64encode(raw), 'sequence': sequence}))

        Photo = request.env['mconfort.customer.photo'].sudo()
        ip = request.httprequest.remote_addr
        limit, window = RATE_LIMIT
        if Photo.search_count([('submitter_ip', '=', ip), ('create_date', '>', fields.Datetime.now() - window)]) >= limit:
            return request.make_json_response({'error': 'rate'}, status=429)

        user = request.env.user
        try:
            with request.env.cr.savepoint():
                Photo.create({
                    'firstname': firstname,
                    'lastname': lastname,
                    'comment': (comment or '').strip()[:1000],
                    'partner_id': False if user._is_public() else user.partner_id.id,
                    'image_ids': images,
                    'submitter_ip': ip,
                })
        except (UserError, ValueError):
            return request.make_json_response({'error': 'file'}, status=400)
        return request.make_json_response({'ok': True})

    @http.route('/photos-clients/featured', type='jsonrpc', auth='public', website=True, readonly=True)
    def featured(self, limit=3):
        limit = limit if isinstance(limit, int) and 1 <= limit <= 6 else 3
        photos = request.env['mconfort.customer.photo'].sudo().search(
            [('is_published', '=', True), ('image_ids', '!=', False)],
            order='featured desc, submitted_on desc, id desc', limit=limit)
        website = request.env['website']
        return [{
            'id': photo.id,
            'url': photo.website_url,
            'image': website.image_url(photo.cover_image_id, 'image_1024'),
            'alt': photo.product_id.name or photo.name,
            'caption': _("Client M'Confort – %s", photo.city) if photo.city else _("Client M'Confort"),
        } for photo in photos]

    @http.route('/photos-clients/like', type='jsonrpc', auth='public', website=True)
    def like(self, photo_id):
        photo = request.env['mconfort.customer.photo'].sudo().search(
            [('id', '=', photo_id if isinstance(photo_id, int) else 0), ('is_published', '=', True)])
        if not photo:
            return {'error': 'not_found'}
        liked = set(request.session.get('mcp_likes', []))
        if photo.id in liked:
            liked.discard(photo.id)
            photo.like_count = max(0, photo.like_count - 1)
        else:
            liked.add(photo.id)
            photo.like_count += 1
        request.session['mcp_likes'] = sorted(liked)
        return {'liked': photo.id in liked, 'count': photo.like_count}
