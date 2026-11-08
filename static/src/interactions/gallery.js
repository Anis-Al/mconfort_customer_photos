import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

const FOCUSABLE = "button:not([disabled]):not(.d-none), input:not([type=hidden]):not([tabindex='-1']), textarea";
const MAX_PHOTOS = 8;
const LIGHTBOX_FILL = 0.75;

export class CustomerPhotoGallery extends Interaction {
    static selector = ".o_mcp_gallery";
    dynamicContent = {
        ".o_mcp_card": { "t-on-click.prevent": this.onCardClick },
        ".o_mcp_sort, .o_mcp_categ_select": { "t-on-change": this.onSortChange },
        ".o_mcp_lightbox": { "t-on-click": this.onLightboxClick },
        ".o_mcp_open_upload": { "t-on-click.prevent": this.openUpload },
        ".o_mcp_upload": { "t-on-click": this.onUploadClick },
        ".o_mcp_file_input": { "t-on-change": this.onFilesChosen },
        ".o_mcp_dropzone": {
            "t-on-dragover.prevent": this.onDragOver,
            "t-on-dragleave": this.onDragLeave,
            "t-on-drop.prevent": this.onDrop,
        },
        ".o_mcp_upload_form": { "t-on-submit.prevent": this.onSubmit },
        _document: { "t-on-keydown": this.onKeydown },
        _window: { "t-on-resize": this.fitImage },
    };

    setup() {
        this.card = null;
        this.index = 0;
        this.opener = null;
        this.uploadOpener = null;
        this.files = [];
        this.sending = false;
    }

    start() {
        this.addListener(this.slot("image"), "load", () => this.fitImage());
        if (this.el.dataset.open) {
            this.open(JSON.parse(this.el.dataset.open));
        }
    }

    get lightbox() {
        return this.el.querySelector(".o_mcp_lightbox");
    }

    slot(name) {
        return this.lightbox.querySelector(`[data-slot="${name}"]`);
    }


    onSortChange(ev) {
        ev.target.form.submit();
    }

    onCardClick(ev) {
        this.opener = ev.currentTarget;
        this.open(JSON.parse(ev.currentTarget.dataset.lightbox), this.opener);
    }

    onLightboxClick(ev) {
        const target = ev.target.closest("[data-action], [data-index]");
        if (!target) {
            return;
        }
        if (target.dataset.index !== undefined) {
            this.index = parseInt(target.dataset.index);
            this.render();
            return;
        }
        const action = target.dataset.action;
        if (action === "close") {
            this.close();
        } else if (action === "prev") {
            this.go(-1);
        } else if (action === "next") {
            this.go(1);
        } else if (action === "like") {
            this.toggleLike();
        }
    }

    onKeydown(ev) {
        const uploading = this.upload && !this.upload.classList.contains("d-none");
        if (!this.card && !uploading) {
            return;
        }
        if (ev.key === "Escape") {
            uploading ? this.closeUpload() : this.close();
        } else if (this.card && ev.key === "ArrowLeft") {
            this.go(-1);
        } else if (this.card && ev.key === "ArrowRight") {
            this.go(1);
        } else if (ev.key === "Tab") {
            const items = [...(uploading ? this.upload : this.lightbox).querySelectorAll(FOCUSABLE)];
            const first = items[0];
            const last = items.at(-1);
            if (ev.shiftKey && document.activeElement === first) {
                ev.preventDefault();
                last.focus();
            } else if (!ev.shiftKey && document.activeElement === last) {
                ev.preventDefault();
                first.focus();
            }
        }
    }


    get upload() {
        return this.el.querySelector(".o_mcp_upload");
    }

    uploadSlot(name) {
        return this.upload.querySelector(`[data-slot="${name}"]`);
    }

    openUpload(ev) {
        this.uploadOpener = ev.currentTarget;
        this.upload.classList.remove("d-none");
        document.body.classList.add("overflow-hidden");
        this.upload.querySelector(".o_mcp_upload_form").classList.remove("d-none");
        this.upload.querySelector(".o_mcp_thanks").classList.add("d-none");
        this.showUploadError(null);
        this.upload.querySelector(".o_mcp_up_close").focus();
    }

    closeUpload() {
        this.upload.classList.add("d-none");
        document.body.classList.remove("overflow-hidden");
        this.uploadOpener?.focus();
    }

    onUploadClick(ev) {
        const target = ev.target.closest("[data-upload-action], [data-remove]");
        if (!target) {
            return;
        }
        if (target.dataset.remove !== undefined) {
            this.files.splice(parseInt(target.dataset.remove), 1);
            this.renderPreviews();
        } else if (!this.sending) {
            this.closeUpload();
        }
    }

    onDragOver(ev) {
        ev.currentTarget.classList.add("o_mcp_dragging");
    }

    onDragLeave(ev) {
        ev.currentTarget.classList.remove("o_mcp_dragging");
    }

    onDrop(ev) {
        ev.currentTarget.classList.remove("o_mcp_dragging");
        this.addFiles(ev.dataTransfer.files);
    }

    onFilesChosen(ev) {
        this.addFiles(ev.target.files);
        ev.target.value = "";
    }

    addFiles(fileList) {
        for (const file of fileList) {
            if (file.type.startsWith("image/")) {
                this.files.push(file);
            }
        }
        this.files.length = Math.min(this.files.length, MAX_PHOTOS);
        this.renderPreviews();
    }

    renderPreviews() {
        this.upload.querySelectorAll(".o_mcp_preview img").forEach((img) => URL.revokeObjectURL(img.src));
        const word = this.uploadSlot("remove-word").textContent;
        this.uploadSlot("previews").replaceChildren(
            ...this.files.map((file, i) => {
                const wrap = document.createElement("span");
                wrap.className = "o_mcp_preview";
                const img = document.createElement("img");
                img.src = URL.createObjectURL(file);
                img.alt = file.name;
                const remove = document.createElement("button");
                remove.type = "button";
                remove.dataset.remove = i;
                remove.setAttribute("aria-label", `${word}: ${file.name}`);
                remove.textContent = "×";
                wrap.append(img, remove);
                return wrap;
            })
        );
    }

    showUploadError(code) {
        for (const p of this.upload.querySelectorAll("[data-error]")) {
            p.classList.toggle("d-none", p.dataset.error !== code);
        }
    }

    async onSubmit(ev) {
        if (this.sending) {
            return;
        }
        const form = ev.currentTarget;
        const button = form.querySelector(".o_mcp_submit");
        if (!form.firstname.value.trim() || !form.lastname.value.trim() || !this.files.length) {
            this.showUploadError("invalid");
            return;
        }
        this.showUploadError(null);
        const body = new FormData(form);
        this.files.forEach((file) => body.append("photos", file));
        this.sending = true;
        button.disabled = true;
        let error = null;
        try {
            const response = await this.waitFor(fetch(form.action, { method: "POST", body }));
            const data = await this.waitFor(response.json().catch(() => ({ error: "network" })));
            error = data.error || (response.ok ? null : "network");
        } catch {
            error = "network";
        }
        this.sending = false;
        button.disabled = false;
        if (error) {
            this.showUploadError(error);
            return;
        }
        form.reset();
        this.files = [];
        this.renderPreviews();
        form.classList.add("d-none");
        const thanks = this.upload.querySelector(".o_mcp_thanks");
        thanks.classList.remove("d-none");
        thanks.focus();
    }


    open(card, opener = null) {
        this.card = card;
        this.index = 0;
        this.opener = opener;
        this.render();
        this.lightbox.classList.remove("d-none");
        document.body.classList.add("overflow-hidden");
        this.fitImage();
        this.lightbox.querySelector(".o_mcp_lb_close").focus();
    }

    fitImage() {
        const img = this.slot("image");
        const { clientWidth: width, clientHeight: height } = img.parentElement;
        const { naturalWidth: nw, naturalHeight: nh } = img;
        if (!this.card || !nw || !width) {
            return;
        }
        const contain = Math.min(width / nw, height / nh);
        const cover = Math.max(width / nw, height / nh);
        const scale = contain + (cover - contain) * LIGHTBOX_FILL;
        img.style.width = `${Math.round(nw * scale)}px`;
        img.style.height = `${Math.round(nh * scale)}px`;
    }

    close() {
        this.card = null;
        this.lightbox.classList.add("d-none");
        document.body.classList.remove("overflow-hidden");
        this.opener?.focus();
    }

    go(step) {
        const count = this.card.photos.length;
        this.index = (this.index + step + count) % count;
        this.render();
    }

    async toggleLike() {
        const card = this.card;
        const res = await this.waitFor(rpc("/photos-clients/like", { photo_id: card.id }));
        if (res.error) {
            return;
        }
        card.liked = res.liked;
        card.likes = res.count;
        const cardEl = this.el.querySelector(`.o_mcp_card[data-id="${card.id}"]`);
        if (cardEl) {
            cardEl.dataset.lightbox = JSON.stringify(card);
        }
        if (this.card === card) {
            this.render();
        }
    }

    render() {
        const { card, index } = this;
        const photos = card.photos;
        const text = (name, value) => (this.slot(name).textContent = value);
        const toggle = (name, on) => this.slot(name).classList.toggle("d-none", !on);

        const image = this.slot("image");
        image.src = photos[index].full;
        image.alt = card.product || card.author;

        text("likes", card.likes);
        const like = this.lightbox.querySelector(".o_mcp_lb_like");
        like.classList.toggle("active", card.liked);
        like.setAttribute("aria-pressed", card.liked);

        const multiple = photos.length > 1;
        this.lightbox.querySelector(".o_mcp_lb_prev").classList.toggle("d-none", !multiple);
        this.lightbox.querySelector(".o_mcp_lb_next").classList.toggle("d-none", !multiple);
        const word = this.slot("photo-word").textContent;
        this.slot("thumbs").replaceChildren(
            ...(multiple ? photos : []).map((photo, i) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "o_mcp_lb_thumb";
                button.dataset.index = i;
                button.setAttribute("aria-label", `${word} ${i + 1}`);
                if (i === index) {
                    button.setAttribute("aria-current", "true");
                }
                const img = document.createElement("img");
                img.src = photo.thumb;
                img.alt = "";
                button.append(img);
                return button;
            })
        );

        text("product", card.product || card.author);
        const product = this.slot("product");
        if (card.product_url) {
            product.setAttribute("href", card.product_url);
        } else {
            product.removeAttribute("href");
        }
        text("city", card.city);
        toggle("city-row", !!card.city);
        text("date", card.date);
        text("comment", card.comment ? `“${card.comment}”` : "");
        toggle("comment", !!card.comment);
        text("author", card.author);
    }
}

registry.category("public.interactions").add("mconfort_customer_photos.gallery", CustomerPhotoGallery);
