# mconfort_customer_photos — working log

Implements `PLAN_mconfort_customer_photos.md` (sibling of this module, in `odoo/mnt/`).
Design reference: `odoo/mnt/_photo_mockup/html/index.html`.

## How to work on this module

Same standing rules as `aa_loyalty_points` — they outlive any single conversation:

1. **Build one lot, run the suite, log it here, then start the next.**
2. **Log every change in this file** (date + what it does). Assume the conversation is gone.
3. **Design rationale lives in "Design notes"** at the bottom.
4. **`mconfort` is the working database.** Install and test there.
5. Wording is **English** in the source; French in `i18n/fr.po`, copy taken verbatim from the mockups.

| Lot | Scope | Status |
|---|---|---|
| 1 | Models, security, back office, approve/reject, activity on arrival | **done** — 12 tests green, back office checked in the browser (2026-11-04) |
| 2 | `/photos-clients` page, cards, filters, sort, pager, lightbox, likes | **done** — 24 tests green (12 lot 1 + 12 lot 2), checked in the browser desktop + phone (2026-11-08) |
| 3 | Upload modal + `/photos-clients/submit` | **done** — 38 tests green (24 + 14 new), submit checked end to end in the browser (2026-11-08) |
| 4 | Home building block (snippet + builder option) + `/photos-clients/featured` | **done** — 43 tests green (38 + 5 new); block checked on a throwaway page (desktop, phone, empty); **editor drop + option not exercised in a browser** (needs a login) (2026-11-08) |
| 5 | Optional: decision e-mail, loyalty points, settings | ask first |

## Commands

Install / update + tests (HttpCase tests need a port of their own):

```powershell
& "C:\Program Files\Odoo 19.0.20260724\python\python.exe" "C:\Program Files\Odoo 19.0.20260724\server\odoo-bin" `
  -c "C:\Program Files\Odoo 19.0.20260724\server\odoo.conf" -d mconfort `
  -u mconfort_customer_photos --test-tags /mconfort_customer_photos --stop-after-init --no-http `
  --http-port=8299 --logfile="<scratch>\mcp_tests.log" --log-level=test
```

Then `Select-String -Path <log> -Pattern "ERROR|FAIL|tests? ran|failed"`. `--logfile=-` is lost
under PowerShell 5.1.

**Python changes need `Restart-Service odoo-server-19.0` (elevated)** — the running service
reuses the already-imported `.py` (repo CLAUDE.md trap 4). XML/CSV/JS only: `-u` is enough.

## Change log

### 2026-11-04 — lot 1 written

- `models/customer_photo.py`: `mconfort.customer.photo` (`mail.thread`, `mail.activity.mixin`,
  `website.published.mixin`) and `mconfort.customer.photo.image` (`image.mixin`, related
  `website_published`).
- `security/`: group `group_manager` ("Customer Photos: Validator", implies internal user);
  public/portal read rules on `website_published = True`.
- `views/customer_photo_views.xml`: kanban grouped by state (cover thumbnail), list, form
  (Approve / Reject / Reset buttons, publish stat button, photos tab), search with
  "To Validate" default; menu Website ▸ Customer Photos (validators only).
- `tests/test_customer_photo.py`: name initial, one todo per validator, category from the
  root public category, approve publishes + closes todo, reject needs a reason, sale order ⇒
  verified, cover = first by sequence, `website_url`, public sees published only; HttpCase:
  `/web/image/.../image_512` is 200 once approved and not 200 while pending.

### 2026-11-04 — lot 1 installed on `mconfort`, 12 tests, 0 failed

Three Odoo 19 traps hit on the way, all fixed in the files:

- `res.groups` has **no `category_id`** any more: a group hangs off a `res.groups.privilege`
  (which carries the category). The module ships its own privilege "Customer Photos" so the
  validator group is a checkbox in Settings ▸ Users, not a level competing with Website's
  editor roles.
- Search views: `<group string="…">` is **rejected by the 19 RNG** — use a bare `<group>`.
- `/web/image/...` answers an access error with the **placeholder image and HTTP 200**
  (so pages never show broken images). Tests that want to prove a photo is *not* served must
  add `?download=true`, which turns the access error into a 404.
- Cover photo: right after `create`, the one2many cache keeps creation order, so the compute
  sorts `image_ids` by `(sequence, id)` itself instead of trusting `[:1]`.

Known noise in every run here (not ours): `ai.embedding has no table`,
`website_sale_default_order` / `website_snippets` not loadable, and `FileNotFoundError` on
three filestore blobs (`21/213f…`, `2f/2f59…`, `32/32f9…`) that the restored DB references but
the dev filestore lacks.

`Restart-Service odoo-server-19.0` is refused without elevation; the live service runs the old
registry until someone restarts it from an elevated shell.

### 2026-11-04 — menu placement

First attempt was a first-level "Photos clients" entry in the Website app. It stayed invisible
even with the group fixed, while the menu service did return it. Cause:
`website/static/src/components/navbar/navbar.js` (and the burger menu) override
`currentAppSections` with `.filter((section) => section.childrenTree.length)` — **first-level
entries of the Website app without children are never drawn.** A section with two children
worked, but the client asked for a single entry instead: it now lives in
**Website ▸ eCommerce ▸ Produits ▸ Photos clients** (`parent="website_sale.menu_catalog"`).
Caveat: the eCommerce menu itself is `groups="sales_team.group_sale_salesman"`, so a validator
who is not at least a salesperson will not see it (the action still opens by URL / activities).
The two sub-menus and `action_customer_photo_all` were removed; `-u` deletes their records.

### 2026-11-04 — administrators imply the validator group

The menu is `groups="mconfort_customer_photos.group_manager"`, and nobody was in that group
after install, so "Photos clients" was invisible to everyone — admin included. `group_manager`
now carries `implied_by_ids = base.group_system` (Website does the same for its designer
group), so administrators see it at once; moderators are added in Settings ▸ Users ▸ Website
▸ "Photos clients".

### 2026-11-04 — French translations

`i18n/fr.po` written from the exported POT (`odoo-bin i18n export mconfort_customer_photos -c … -d mconfort -l pot fr_FR`;
the old `--i18n-export` server flag is gone in 19) and loaded with `-u`. Checked in the DB:
menu "Photos clients", fields "Prénom" / "Statut" / "Achat vérifié". Only the module's own
terms are translated; the mixin fields (mail, activities, website) come from core `.po` files.

**Trap — the POT gates the PO.** `odoo.tools.translate.PoFileReader` merges `fr.po` with
`i18n/mconfort_customer_photos.pot` (`self.pofile.merge(pot)`), so a `.po` entry that is not in
the POT is silently dropped and the *occurrences* are taken from the POT. Adding terms means:
(1) `-u` so the records exist, (2) re-export the POT (`odoo-bin i18n export mconfort_customer_photos
-c … -d mconfort -l pot`), (3) edit `fr.po`, (4) `-u` or `odoo-bin i18n import fr.po -l fr_FR`.
Never export `-l fr_FR` over an edited `fr.po`: it rewrites it from the DB.

### 2026-11-04 — back office checked in the browser (live service, after an elevated restart)

Done as ANIS on `mconfort`: Website ▸ eCommerce ▸ Produits ▸ Photos clients opens the kanban
on "À valider" with the French empty state; "Nouveau" → form in French, the title computes
"Mehdi F." live; saving created record 32 and the top-bar activity badge went to 1 (the
validator to-do); setting the product RUNE filled the category; **Approuver** switched the
status bar to "Approuvée", the globe button to "Publié", and the header to Refuser / Remettre
à valider. Not exercised in the browser: photo upload through the form (the pane cannot drive
a file dialog — covered by the tests), and the reject path (covered by the tests).

Record 32 "Mehdi F." is real data left in `mconfort` by that check — delete it or keep it as
the first example.

Tip while the service cannot be restarted: a second server on another port runs the new code
without touching it — `odoo-bin -c odoo.conf -d mconfort --http-port=8299 --max-cron-threads=0`
(start it from the Terminal panel; a background tool call kills it after 10 minutes).

### 2026-11-08 — lot 2: public gallery `/photos-clients`

Files: `controllers/main.py` (`gallery`, `like`), `models/customer_photo.py` `_gallery_values()`,
`views/website_templates.xml`, `static/src/interactions/gallery.js`, `static/src/scss/customer_photos.scss`,
`tests/test_controllers.py`; manifest gets the template + `web.assets_frontend` entries.

- Route `/photos-clients[/page/<n>]?categ=salon|dining&sort=likes&open=<id>`. Unknown `categ`/`sort`
  fall back to `all`/`recent`; defaults stay out of pager URLs. 24 per page. `sitemap=True`.
- Only published submissions **with at least one photo** are listed (a published record with no image
  would break the card and the lightbox). Chip counts use the same domain.
- **Deviations from the plan, on purpose:**
  - **Lightbox is not a Bootstrap modal / OWL template.** The server renders the whole lightbox once
    (translated like any view) and `gallery.js` only fills its `data-slot` elements from the card's
    `data-lightbox` JSON. No `renderToElement`, so no client-side translation plumbing (frontend only
    loads translations of modules listed by `_get_translation_frontend_modules_name`).
  - **Likes shown on the card are a count only** (as in the mockup, the heart there is decorative);
    the like button lives in the lightbox. "Liked" state comes back from `request.session['mcp_likes']`
    inside the card JSON, so no localStorage.
  - **`?open=<id>` ships the card in `#wrap[data-open]`**, so the deep link works when the photo is on
    another page or filtered out. Unpublished / unknown / garbage ids: nothing opens.
  - **"Partagez votre intérieur" banner and "Ajouter ma photo" button are NOT there** — they belong to
    lot 3 (upload modal). No dead button meanwhile. No menu entry either (plan §7, decide with lot 3).
  - City is shown as typed ("Kaweni"); the mockup's ", Mayotte" is not appended.
- **Sass trap:** `min()` / `clamp()` with mixed units are evaluated by Sass → `Incompatible units: '%' and
  'px'` and the **whole `web.assets_frontend` bundle fails to compile** (logged as a WARNING, the site
  loses CSS). Write `unquote("min(1180px, 100%)")`.
- Test traps: the `mconfort` db holds real data, so lot 2 tests are relative (position of our records,
  ORM counts). The lot 1 "one todo per validator" test now allows extra validators (administrators imply
  the group).
- i18n: POT re-exported and `fr.po` regenerated from it (script merges existing msgstr + the new French
  copy). The export now also lists mixin field labels (Messages, Followers…): **drop them** from POT and
  PO, core already translates them.
- Browser check ran on a second server (`--http-port=8299 --max-cron-threads=0`) because the live
  service has to be restarted (elevated) to load the new `.py`. Five demo submissions (`lastname =
  DEMOTMP`) were created for it and deleted afterwards; record 32 "Mehdi F." (no photo) is still there.

### 2026-11-08 — lot 3: upload modal + `/photos-clients/submit`

Files: `controllers/main.py` (`submit`, prefill in `gallery`), `views/website_templates.xml` (CTA banner +
`.o_mcp_upload` modal), `static/src/interactions/gallery.js` (same Interaction as lot 2),
`static/src/scss/customer_photos.scss`, `tests/test_controllers.py` (`TestSubmit`, 14 tests).

- Route: `POST /photos-clients/submit`, `auth='public'`, CSRF **on** (form carries `csrf_token`),
  `max_content_length` = 8 × 8 MB. Answers JSON: `{ok: true}` or `{error: invalid|too_many|file|rate}` with
  400/429. The page shows the matching message (server-rendered, hidden `[data-error]` paragraphs, so it
  is translated like any view); `network` is client-only (non-JSON answer, e.g. the framework's own 413).
- Limits: 1–8 photos, 8 MB each, first/last name ≤ 60, review ≤ 1000. One bad file refuses the whole post.
- **(Corrected 2026-11-08 — see "WebP was refused" below.)** Files are checked by content (JPEG / PNG / GIF
  decoded by Pillow, WebP by its RIFF header), not by the browser's
  mimetype or extension: an SVG renamed `.png` would otherwise be served back by `/web/image` with its
  script. HEIC is refused (Pillow cannot decode it) — phones normally convert to JPEG on upload.
- Honeypot field `hp_url` (off-screen, `tabindex=-1`): filled → `{ok: true}` and nothing created.
- Rate limit: 5 per `submitter_ip` per 10 minutes → 429. **Behind a proxy that does not forward the
  client address, every visitor shares one budget** (`remote_addr`). Check the production proxy setup
  before relying on it.
- `create` runs in a savepoint, so a late failure leaves no half-record. The new record is `pending`,
  not published, and every validator gets the to-do (lot 1).
- Logged-in customer: `partner_id` set, form prefilled from the partner name (split on the first space).
- The modal reuses the lightbox pattern (own overlay, Escape closes, Tab trapped, focus returned).
  Photos are kept in a JS array (so single files can be removed before sending) and appended to the
  `FormData` as `photos`; the file input itself has no `name`.
- Left panel of the mockup is a decorative photo; there is no asset for it, so it is a navy gradient with
  the camera icon (hidden under 768 px).
- **French copy:** form and banner text is the mockup's, verbatim. The error messages and the thank-you
  state are **not in the mockups** — wording written here ("Merci !", "Votre photo a bien été reçue…").
  Ask the client to validate them.
- Test traps: PG `now()` is **not UTC** on this server (session timezone), so a test that backdates
  `create_date` must pass a Python `fields.Datetime.now() - timedelta(...)`, not `now() - interval`.
  Each submit test posts a unique last name to find its own record among the real ones.
- i18n merge: regenerated `fr.po` from the POT again; entries with no mapping (mixin field labels) are
  dropped from POT and PO.
- Still **no menu entry** for `/photos-clients` (plan §7) — the page is only reachable by URL until the
  client decides. The pending submission created by the browser check was deleted.

### 2026-11-08 — lot 4: home block "Chez vous, avec M'Confort" + `/photos-clients/featured`

Files: `views/snippets/s_customer_photos.xml` (template + registration under group **People**),
`static/src/snippets/s_customer_photos/s_customer_photos.{js,xml}` (Interaction + mosaic template),
`static/src/website_builder/customer_photos_option.{js,xml}` (option), `static/src/scss/s_customer_photos.scss`,
`static/description/s_customer_photos.svg` (thumbnail), `controllers/main.py` `featured`, `tests/test_controllers.py` `TestFeatured`.

- `/photos-clients/featured` (jsonrpc, public, readonly): `limit` 1–6 (anything else → 3); featured first,
  then newest; published with ≥ 1 photo only. Returns `{id, url (= ?open=<id>), image (image_1024), alt, caption}`.
  The **caption is built server-side** (`_("Client M'Confort – %s")`) so JS carries no translatable text.
- Block = plain editable section (title, subtitle, button, trust row — all English source, French in `fr.po`)
  + `.s_customer_photos_content` (`o_not_editable`) that the Interaction fills. Option "Photos shown" 1/2/3
  (`data-limit`, default 3) restarts the interaction; the mosaic has a layout for each count.
- **Empty = the block hides itself on the public site** (`d-none` via `dynamicContent`), so dropping it before
  any photo is approved leaves no hole. In the editor it shows empty tiles.
- Tiles link to `/photos-clients?open=<id>` → the gallery opens that photo's lightbox (lot 2 deep link).
- Plan said `/featured` count option 3/5; changed to 1/2/3 because the mosaic is a fixed 3-slot layout.
- Python trap again: a bad-parse Bash heredoc created **no files** — if a multi-file `cat <<EOF` fails with a
  syntax error, nothing ran; use the Write tool.
- **Placing it:** the block is database data once dropped. After the elevated service restart: open the home
  page in the editor, drop *Customer Photos* (People) between "Ils nous font confiance" and the next section,
  save. Same manual drop on production after `-u`.
- **Not verified:** dropping the block in the website editor and the option panel (no login in the browser
  pane). Verified instead: both bundles contain the option / interaction / templates (`_get_asset_bundle`),
  JS parses (`node --check`), XML well-formed, public rendering on a throwaway `website.page` (deleted after).
  First thing to check once logged in: People group lists "Customer Photos" with its thumbnail; option shows.
- Test photos created for the check (`lastname = DEMOTMP`) and the throwaway page were deleted afterwards.

### 2026-11-08 — client changes after lot 4: "Achat vérifié" for all, reject reason optional

- **Removed `verified_purchase`** (model field + compute, form, list, kanban badge, search filter, `verified`
  key in the card JSON, JS toggles). "Achat vérifié" (card pill) and "Client vérifié" (lightbox) now show on
  **every** published photo. The old `-u` drops the `ir.model.fields` row; the PG column stays (harmless).
- **`reject_reason` is optional**: `action_reject` no longer raises; the form placeholder says "Optional note for
  the team. Not shown on the website." The lot 1 test `test_reject_needs_a_reason` became
  `test_reject_reason_is_optional`; the sale-order-verifies test is gone. 42 tests, 0 failed.
- i18n: stale entries (Verified, Verified Purchase, its help, "Give a reason…") fall out of POT/PO by themselves;
  one new term (placeholder) translated.
- Needs the elevated service restart (Python model change) like the rest of lots 2–4.

### 2026-11-08 — no menu entry, on purpose

Client decision: **do not ship a website menu item for `/photos-clients`.** The mconfort website here is
behind the live one (the live site already has a new menu), so adding a `website.menu` record now would
fight that. Plan §7 (`data/website_menu_data.xml`) is **dropped**. The gallery is reached through the home
block's button, the gallery's own upload banner and the direct URL. The client adds the menu link by hand on
the live site (Website ▸ Site ▸ Menus ▸ new entry → `/photos-clients`) when they want it. A menu file was
written and removed again the same day; nothing was installed.

### 2026-11-08 — fix: kanban OwlError "Cannot read properties of undefined (reading 'raw_value')"

The back-office kanban card used `record.featured.raw_value` (lot 1 also `record.verified_purchase`) without
`<field name="featured"/>` in the arch → `record.featured` is `undefined` in the browser and the whole kanban
crashes as soon as **one record exists**. Latent since lot 1: the lot 1 browser check saw an empty kanban, so
the card template never rendered. Fix: `<field name="featured"/>` next to `state` in the kanban arch.
New test `test_kanban_declares_every_field_its_template_reads` (every `record.<name>` must have a `<field>`).
XML only → `-u` is enough, no restart. Rule: **in a kanban, every `record.x` needs `<field name="x"/>`**.
43 tests, 0 failed.

### 2026-11-08 — lightbox: product name is a link

- `_gallery_values()` adds `product_url` = the product's `website_url` (`/shop/...`) **only if the product is
  published** (`product_id.is_published`); otherwise `''`. An unpublished product would 404 for visitors.
- Lightbox markup: `<strong id="o_mcp_lb_title"><a class="o_mcp_lb_product" data-slot="product"/></strong>`;
  `gallery.js` sets / removes the `href`. No `href` → plain text (also when the photo has no product and the
  title falls back to the author name). Gold underline when it is a link. Opens in the same tab.
- Cards on the grid are unchanged (the whole card opens the lightbox, so no nested link there).
- Test `test_product_name_links_to_the_product_only_when_it_is_published`. 44 tests, 0 failed. Checked in the
  browser on :8299 with one published and one unpublished product. Python change → elevated restart.
- i18n: the lightbox title block changed; POT re-exported, `fr.po` merged (needed the "Purchased at M'Confort"
  fragment in the merge script again — **when `fr.po` loses "Achat réalisé chez M'Confort", that is why**).

### 2026-11-08 — categories come from the shop's own first-level categories

Client request: use the existing website categories in the Category field, first level only.

- **Field:** `category` (Selection salon/dining/other) **replaced by** `public_categ_id` (M2o
  `product.public.category`, label "Category", domain `parent_id = False`, `ondelete='set null'`, stored
  compute from `product_id.public_categ_ids`, `readonly=False`). New name on purpose: changing a field's type in
  place makes Odoo move the old column aside. Existing records were recomputed by `-u` (all landed in
  Salon, id 38). Form: `no_create`; list / search group-by updated. Old column `category` stays in PG (harmless).
- **Gallery chips are dynamic:** "All (n)" + one chip per first-level category that has published photos
  (with photos, so never an empty chip), in the shop's order, names translated by the shop's own category
  translations. `?categ=<category id>`; anything else (old `?categ=salon`, a sub-category id, garbage)
  falls back to All. The sort form and chip links keep each other's parameters.
- **Icons dropped:** the sofa / dining-table icons on the chips, card pills and lightbox header depended on the
  hard-coded categories, so they are gone: category chips are text only, the lightbox header circle shows a
  camera. If the client wants icons back, add an optional icon mapping by category id (a setting), not a
  name match.
- Photos with no category (product without one, or no product) show under All only.
- `category` also dropped from the card JSON. Tests rewritten (47): first-level rule, two trees, manual
  override, chips per category, no chip for empty categories / sub-categories, sort kept in chip links, filter,
  old links fall back. **A gallery test must not assert the "All" label**: the public visitor sees fr_FR
  ("Toutes").
- i18n: Living Room / Dining Room / Other and the chip strings fall out of POT and PO; two help texts added.
  Python field change → elevated service restart.

### 2026-11-08 — configurable picture in the upload window ("Partagez votre intérieur avec M'Confort")

- **Where to set it:** Website ▸ Configuration ▸ Settings ▸ General ▸ **Customer Photos Picture** (right under
  "Website Identification"). Per website. Empty = the previous navy gradient panel.
- **How:** new field `website.customer_photos_upload_image` (`fields.Image`, max 1920) in `models/website.py`,
  mirrored on `res.config.settings` (`related=website_id…`, `readonly=False`) and shown by
  `views/res_config_settings_views.xml` (inherits `website.res_config_settings_view_form`, `block website_info_settings`).
- **Served:** `/web/image/website/<id>/customer_photos_upload_image/800x1100?unique=…` — public can read the
  `website` record, no extra access code needed (same as the site logo). The gallery controller only asks
  *whether* a picture exists (`with_context(bin_size=True)`) so no binary is read per page view.
- **Display:** `aside.o_mcp_up_aside.has_image` with the picture as inline `background-image`, `cover`, plus a
  navy fade at the bottom so the white text stays readable (mockup layout). Hidden under 768 px like the panel.
- 3 tests (`TestUploadPicture`): no picture → plain panel; picture → class + public URL returns an image;
  settings screen reads the website's picture. 50 tests, 0 failed. Checked in the browser with a temporary
  picture, removed afterwards (website picture is empty again).
- Python (new field) → **elevated service restart**, then upload the picture in the settings.
- Not verified in a browser: the settings screen itself (needs a login); the view loads (`-u` validates it)
  and the related field is covered by a test.

### 2026-11-08 — home block: phone layout from the client's screenshot

Phone / tablet (< 992 px) order is now: gold rule, title, subtitle (centered, **one line each**), mosaic
(large tile left, two stacked right, 16:9 by ratio), trust row (3 items on one line, dividers), outlined
button last. Desktop unchanged.

- **Button last without a second copy:** under 992 px the container is a flex column, the first `.row` and
  `.col-lg-4` get `display: contents`, so rule / title / subtitle / button become siblings of the mosaic and
  the trust row and `order` moves the button to the end. (Desktop keeps the button in the text column.)
  Editing in the website editor works on the same single button.
- **Title / subtitle are two spans, not a `<br/>`:** `<span class="s_cp_line">At home,</span><span>with
  M'Confort</span>`. `.s_cp_line` is `display: block` from lg up, inline with a gap otherwise. Reason: hiding a
  `<br/>` on phones needs a space before it, and **Odoo's translation step strips whitespace (even a
  non-breaking one) next to a `<br/>`** → "Chez vous,avec". Do not go back to `<br/>`.
- Mosaic mobile: `grid-template-columns: 1.3fr 1fr`, `aspect-ratio: 16/9` (4/3 for one photo), small captions.
  Trust row `col-4` on every size, `.64rem` text under 576 px; button `.85rem`; title `1.5rem`, subtitle `1.02rem`
  under 576 px so both fit on one line at 375 px.
- Checked at 375 px and at the pane's desktop width on a throwaway `website.page` (deleted). The home block was
  placed there by `t-call`, not through the editor. 50 tests, 0 failed. XML/SCSS/i18n only: `-u`, no restart.
- **Trust row can never wrap on phones** (follow-up, same day): under 576 px `.s_cp_trust` is `flex-wrap:
  nowrap`, each item is exactly a third (`flex: 0 0 33.33%`, `white-space: nowrap`), the text scales with the
  screen (`clamp(.54rem, 2.6vw, .7rem)`) and the icon is `1.5em` of it. Measured at 320 / 375 / 390 px: same top
  for the three items, nothing clipped, no horizontal page scroll. It also overrides the old `col-12` classes,
  so a block dropped before this change gets the one-row trust row too (the rest of the old markup does not
  improve: title still has its `<br/>`).
- **Desktop trust row sits lower** (client asked, same day): `margin-top: 3.5rem !important` from 992 px up
  (was Bootstrap `mt-4`, 1.5rem). `!important` because `mt-4` is, and it also fixes blocks dropped earlier.
  Phones unchanged. Compiled with `-u`; not looked at in a browser.
- Existing blocks already dropped on a page keep the **old markup** (a `<br/>` title, `col-12 col-md-4` trust
  row): re-drop the block or edit the HTML there. New drops get the new markup.

### 2026-11-08 — no "?" help tooltips on the back-office form

Client asked to drop the helps from the form. Removed `help=` from `partner_id`, `city`, `product_id`,
`public_categ_id`, `featured` in `models/customer_photo.py` (the meaning is kept as a code comment). Their
French entries fell out of POT / PO. **Kept:** the `placeholder` texts inside the form (review, optional
reject note) and the help on the Website-settings picture field (`models/website.py`, not on this form). Mixin
fields (activities, messages, publish) keep core's own tooltips. 50 tests, 0 failed. Python metadata only, but
the form tooltips come from `fields_get`, so the running service needs the elevated restart to drop them.

### 2026-11-08 — bug fix: WebP uploads were refused

The upload accepted JPEG / PNG / **WebP** / GIF on paper, but **WebP was refused**: the route identified files
with `Image.open`, and **Odoo restricts the Pillow of its own process to the core formats** (`odoo/tools/image.py`:
`Image.preinit()` then `Image._initialized = 2`, which makes `Image.init()` a no-op). Pillow therefore cannot
identify WebP inside the server, and Odoo itself special-cases WebP by header (`get_webp_size`). A stand-alone
Python (or an `odoo-bin shell` test that calls `Image.init()`) shows WebP working, which is how this was missed.
Found by a test that tried to *write* a WebP in the Odoo process (`KeyError: 'WEBP'`).

- Fix: `CustomerPhotos._is_accepted_photo(raw)` in `controllers/main.py`. `RIFF…WEBPVP8` + `get_webp_size` (VP8 /
  VP8X / VP8L, size > 0, truncated header → refused) for WebP; Pillow for the rest. `PHOTO_FORMATS` is now
  `{JPEG, PNG, GIF}`. WebP is stored untouched (Odoo does not resize it, so its 512/256 variants are the original).
- Accepted: JPEG, PNG, GIF, WebP (lossy + lossless). Refused: everything else (BMP, TIFF, SVG, HEIC, text…).
  The error text still says "JPEG, PNG, WebP or GIF, 8 MB maximum".
- Tests added in `TestSubmit` (53 total, 0 failed): the four formats incl. real lossy + lossless WebP files
  (embedded as base64, because the Pillow in the Odoo process cannot write WebP), BMP / TIFF refused, extension
  does not matter, truncated WebP headers refused. **Never test image formats from `odoo-bin shell`:** it does
  not behave like a stand-alone Python.
- Python → elevated service restart.

### 2026-11-08 — gallery filter bar redone for phones

Client: the filter bar in `/photos-clients` on mobile "should be refactored". Done to the mobile mockup
(`MobileGallery`): chips in one swipe row, sort select under it, no visible sort label.

- **Markup:** Bootstrap utility soup replaced by `.o_mcp_filters` > `nav.o_mcp_chips[aria-label="Categories"]` +
  `form.o_mcp_sortform`. Same links, same `?categ=&sort=` behaviour, same chip data from the controller.
- **Desktop (≥ 576 px):** unchanged look: chips left, "Sort:" + select right on one row.
- **Phone (< 576 px):** chips are a horizontal scroll row that runs **edge to edge** (cancels the container
  gutter, pads inside), scroll-snap, hidden scrollbar, a **fade on the right edge** (`mask-image`, written with
  `unquote()` because of the Sass `calc` trap) so it is clear there is more to swipe; 44 px chips, 14 px text.
  The sort is a **full-width select** below; its label is kept for screen readers only (visually hidden).
- **`gallery.js` `start()`** scrolls the chips row so the **active category is centred** (manual `scrollLeft` from
  `offsetLeft`, not `scrollIntoView`, which would jump the page); `.o_mcp_chips` is `position: relative` for that.
- i18n: one new term (`aria-label` "Categories" → "Catégories").
- Checked in the browser at 375 px (real data has few categories, so a long list was simulated by cloning chips:
  overflow, fade, no page scroll sideways) and at desktop width (same row, label visible, filter + sort kept).
  The centring of an active chip that is off-screen was **not** exercised (needs more real categories).
  XML / SCSS / JS only: `-u`, no restart.

### 2026-11-08 — phone gallery: categories as a dropdown, plain cards, slim upload bar; two sentences smaller

Three client requests in a row, all on `/photos-clients`. **Phones only (< 576 px)** unless said otherwise; desktop
and tablets keep the mockup design (chips, pills, banner). 55 tests, 0 failed. XML / SCSS / JS / i18n only: `-u`,
no restart.

- **Categories = dropdown on phones** (replaces the swipe row of the entry above, which is gone: no chip
  centring in `gallery.js`, no mask / scroll CSS). `select#o_mcp_categ[name=categ]` ("All (n)" + one option per
  chip, selected = current) sits in the **same GET form** as the sort select, side by side (`1fr 1fr`); either one
  submits the form (`gallery.js` `".o_mcp_sort, .o_mcp_categ_select"`), so each keeps the other's value. The chips
  are `display: none` on phones (also hidden from screen readers); on desktop the select is hidden but, being a
  select, still submits the current category with the sort (the old hidden `<input name=categ>` is gone).
  The hidden labels ("Category", "Sort:") are screen-reader-only on phones.
- **Plain photo cards on phones** (client's screenshot): no verified pill, no product / likes pills (all of it is in
  the lightbox the card opens); `.o_mcp_grid` gutter 12 px, corners 14 px. Breadcrumb now reads
  **icon › Accueil › Photos clients** on every size (mockup + screenshot).
- **Upload bar on phones:** `button.o_mcp_cta_bar.o_mcp_open_upload.d-sm-none` (camera, "Envoyez-nous votre
  intérieur" / "Partagez une photo de votre achat M'Confort", chevron; whole bar opens the modal). The desktop
  banner is now `d-none d-sm-flex`. **Two upload triggers exist in the DOM** (one hidden per size); both carry
  `.o_mcp_open_upload`. Second line is `nowrap` with a `clamp()` size so it stays on one line at 320-390 px.
- **Upload window texts smaller:** "Inspirez d'autres clients en partageant une photo de votre achat." (left panel)
  `.8rem` (was 1rem) and "Votre photo sera vérifiée par notre équipe avant publication." `.72rem` (was Bootstrap
  `small`, .875rem): classes `o_mcp_up_aside_text`, `o_mcp_up_note`.
- i18n: "Home" → "Accueil", the bar's two lines, "Categories" (kept); old chip-swipe strings unchanged.
- **Open question for the client:** their screenshot shows **no filter bar at all** on the phone gallery (no
  dropdowns). The dropdowns are kept because the client asked for them; confirm whether they want them hidden
  when there is only one category.
- Checked in the browser at 390 px (breadcrumb, side-by-side dropdowns, "Les plus récentes" fits, plain cards,
  bar on one line, no sideways scroll) and desktop (chips, pills, banner as before; modal texts 12.8 / 11.5 px).
  Not exercised: choosing an option in the dropdown (native select; covered by the test of the form and the
  JS handler being the same one as the sort's).

### 2026-11-08 — plain cards on every screen size; lightbox shows the whole photo

Two follow-ups to the entry above. 56 tests, 0 failed. The cards change is XML / SCSS / JS; the lightbox
resolution change is Python (`_gallery_values`) → **elevated service restart**.

- **Cards are plain photos on desktop too** (was phones only): the verified pill, product-name pill and like
  count are **removed from the card markup** (not just hidden), together with their CSS (`o_mcp_caption`,
  `o_mcp_pill_product`, `o_mcp_clamp`, `o_mcp_pill_likes`, the phone overrides) and the JS line that updated the
  card's like count. Everything is in the lightbox the card opens. Test
  `test_cards_are_plain_photos_and_the_details_are_in_the_lightbox`. The `.o_mcp_pill` / `_verified` CSS stays
  (the lightbox uses it).
- **Lightbox photo: nothing cropped, nothing on top, full resolution.**
  - `object-fit: contain` (was `cover`, which cut the edges) on a dark navy stage (`#0F1730`).
  - The left column is now **top bar** (verified badge + like) / **stage** (photo + prev / next arrows) /
    **thumbnails**, stacked, so the badge, like button and thumbnail strip no longer sit on the picture.
    Markup: `.o_mcp_lb_top`, `.o_mcp_lb_stage` added; `gallery.js` unchanged (slots / classes the same).
  - Source is now **`image_1920`** (the largest variant Odoo stores; was `image_1024`); thumbnails stay
    `image_256`. A small photo is scaled up to the stage, a large one down; nothing is cut.
  - Checked with a test photo with coloured corner squares and a cross (landscape 1800×1000, portrait 900×1400,
    square): all four corners and the cross visible on desktop and at 390 px; natural size served = stored size.
    Test photo deleted afterwards.
- Home block mosaic still uses `image_1024` cover tiles (decorative crop, unchanged).

### 2026-11-08 — desktop banner uses the phone bar's text; visible captions on the phone selects

56 tests, 0 failed. XML / SCSS / i18n only: `-u`, no restart.

- **Desktop upload banner text = phone bar text** (client: "use the text from the mobile view"): title
  "Envoyez-nous votre intérieur" (`Send us your interior`), line "Partagez une photo de votre achat M'Confort"
  (`Share a photo of your M'Confort purchase`). The old "Share your interior / Bought from M'Confort? …inspire other
  customers" msgids are gone. The "Ajouter ma photo" button is unchanged. (The upload window's left panel keeps its
  own "Partagez votre intérieur avec M'Confort" text: different element, from the mockup.) Test compares the two.
- **Captions ("indices") on the phone dropdowns:** each select now has a small visible label above it,
  **"Catégorie"** and **"Trier par"** (`.o_mcp_field_label`, .72rem, muted, 600). Markup: the sort label + select are
  wrapped in `span.o_mcp_sort_field`; the category label lost its screen-reader-only class. **The sort label text
  changed from "Sort:" to "Sort by" ("Trier par") on every size**, so on desktop it now reads "Trier par [select]"
  on one line (same label, one source of truth).
- i18n: "Sort by" → "Trier par"; "Category" → "Catégorie" (existing msgid).

### 2026-11-08 — breadcrumb without the home icon

Client: "home / Accueil / Photos clients is too much". The home-icon item is removed: the breadcrumb is now
**Accueil › Photos clients** on every size (the "Accueil" link goes to `/`). The mockup and the earlier screenshot had
the icon; the client dropped it. Test updated (2 items, no `fa-home`). The "Home" tooltip term left the POT/PO by
itself. XML only, no restart.

### 2026-11-08 — "change of mind": cropped photos in bigger modals; one upload bar everywhere

56 tests, 0 failed. XML / SCSS / i18n only: `-u`, no restart. **This supersedes the "whole photo, uncropped" part of the
lightbox entry above** (the 1920 px source stays).

- **Lightbox photo is cropped to fit its panel again** (`object-fit: cover`), as in the mockup: the photo fills the
  whole left panel; badge + like sit on top of it, the arrows on its sides, the thumbnails at the bottom
  (`.o_mcp_lb_top` / `.o_mcp_lb_stage` are now absolutely positioned layers; the markup from the previous change stays).
  Edges of a photo are cut by design.
- **Bigger modals:** lightbox dialog `min(1400px, 100%)` (was 1180), photo panel `min-height: 700px` on desktop
  (was 560) and 380 px on phones (was 260–360); the upload window `min(1200px, 100%)` (was 1060). The photo column is
  `flex: 2 1 600px` next to the 380 px details column: **a bigger basis (640) made the details drop *under* the photo at
  a 1024 px window** — keep `photo basis + 380 ≤ 992`.
- **Upload card = the phone bar on every size** (client: "make the entire card identical to the mobile"): the big
  desktop banner (camera tile, text, "Ajouter ma photo" button) is **deleted** with its CSS and its two
  translations. `button.o_mcp_cta_bar.o_mcp_open_upload` (camera, "Envoyez-nous votre intérieur", "Partagez une photo de
  votre achat M'Confort", chevron) is shown on all sizes, full container width. There is now **one** upload trigger
  in the page. Test `test_breadcrumb_and_the_single_upload_bar`.
- Checked in the browser with the corner-marker test photo (deleted afterwards): desktop 1024 px (side by side, photo
  fills 608×700) and 390 px (photo fills 358×380, no sideways scroll).

### 2026-11-08 — lightbox photo "a tiny bit uncropped"

Client after the cropped-photo change: show a bit more of the photo (zoom out slightly). JS + SCSS only (`-u`).

- **How:** plain CSS cannot sit between `cover` and `contain`, so `gallery.js` `fitImage()` sizes the photo itself:
  `scale = contain + (cover − contain) × LIGHTBOX_FILL`, centred in the panel (`.o_mcp_lb_image` is centred with
  `left/top 50% + translate(-50%,-50%)`, `.o_mcp_lb_stage { overflow: hidden }`; before JS runs it is plain `cover`).
  Runs when a photo finishes loading, when the lightbox opens (the panel is `display: none` before that, so its size
  is 0 while rendering) and on window resize.
- **The knob:** `LIGHTBOX_FILL` at the top of `gallery.js`: **0.75** now (1 = cropped to fill, as before; 0 = whole
  photo). Measured in the real side-by-side layout (panel 608 × 700, test photo 1800 × 1000): shows **55 %** of the
  width instead of 48 % with plain `cover`, with a ~46 px dark band above and below. Portrait photos get thin side
  bands instead. A first try at 0.85 changed the crop by only ~4 points, too little to notice.
- Remember: the `<img>` carries `loading="lazy"` (added by Odoo's lazy-loading interaction) — fine here because the
  `src` is set before the lightbox is shown.
- Test photo (corner-marker image, `lastname = DEMOTMP`) deleted afterwards. 56 tests, 0 failed.

### 2026-11-08 — code review fix: WebP uploads are converted to JPEG

From the full module review: WebP was stored **untouched** (Odoo never resizes it), so its `image_512` / `image_256`
variants were the 8 MB original — a page of 24 could weigh ~190 MB. **This supersedes "WebP is stored untouched" in the
"WebP was refused" entry.**

- `submit` still validates WebP by its RIFF header (`_is_accepted_photo`), then `_webp_to_jpeg(raw)` re-encodes it:
  first frame of an animated file, transparency flattened on white, JPEG quality 88, refused above `MAX_PIXELS`
  (40 Mpx) or if undecodable. Stored as a normal JPEG → resized to 1920 and its variants are small. Metadata (EXIF /
  GPS) is dropped as a side effect.
- Odoo registers only core Pillow formats at startup; `_webp_to_jpeg` does `from PIL import WebPImagePlugin` to load
  the decoder (the plugin is available in this Pillow build).
- Not covered: a **staff** adding a WebP through the back-office form still stores it as is (the conversion lives in
  the public route). Rare; convert in the model's `create` if it ever matters.
- Tests (58 total, 0 failed): a 3600×2400 heavy WebP ends up as JPEG in `image_1920` (≤ 1920 px), `image_512` and
  `image_256`, the 512 variant under a quarter of the original size; a transparent animated WebP is accepted.
- **Still open from the review** (not done): strip EXIF/GPS from JPEGs ≤ 1920 px (privacy, `image_1920` is served
  publicly), rate-limit check before decoding files, purge `submitter_ip`, minor items. Python → elevated restart.

### 2026-11-08 — code review fix: submitter IPs are erased after a day

`submitter_ip` is personal data used only for the 10-minute upload rate limit, but it was kept forever.
`data/ir_cron_data.xml` (noupdate) adds the daily cron **"Customer Photos: erase submitter IPs"** →
`mconfort.customer.photo._cron_purge_submitter_ip()`: clears the IP of every submission created more than 24 h ago
(`mail_notrack`). Test: old one erased, recent one kept, cron installed and active (59 tests, 0 failed). Run once by hand
on `mconfort` after install. The cron's name is not translated into French (admin-only). Python + data → elevated restart.
The first git commit (`0f34ead`, pushed to `Anis-Al/mconfort_customer_photos`, no co-author) predates this fix and the
WebP conversion log entry's code is in it; this change is **not committed yet**.

## Design notes

- **Notification = `activity_schedule`** on every validator (group `all_user_ids`), closed by
  `activity_feedback` on approve/reject. Bell + Activities menu + activity digest mail, nothing
  custom. WhatsApp push is not possible: `mconfort_whatsapp` only builds `wa.me` links.
- **Public photo access** relies on `website/models/models.py` `_can_return_content`: the image
  model carries a related `website_published`, so `/web/image/<model>/<id>/image_512` works for
  anonymous visitors exactly when the submission is approved. No controller, no public attachment.
- **Category** (`public_categ_id`, since 2026-11-08) is a Many2one to `product.public.category`, computed from
  the product's **first-level** shop category (Salon > Canapé gives Salon; several trees → first root in the
  shop's own order). Stored, `readonly=False`, staff can override (domain: roots only). The old
  `salon/dining/other` Selection `category` is gone. See the 2026-11-08 "categories" entry.
- **No `verified_purchase` field any more** (removed 2026-11-08): the client wants "Achat vérifié" on every
  photo, so the badge is static text in the templates. `sale_order_id` stays as an optional link, it no
  longer drives anything.
- **Rejection reason** is a plain optional field + a button, no wizard.
