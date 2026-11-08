import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { renderToElement } from "@web/core/utils/render";

export class CustomerPhotosSnippet extends Interaction {
    static selector = ".s_customer_photos";
    dynamicContent = {
        _root: {
            "t-att-class": () => ({ "d-none": !this.editMode && !this.photos.length }),
        },
    };

    setup() {
        this.photos = [];
        this.editMode = false;
    }

    get limit() {
        return parseInt(this.el.dataset.limit) || 3;
    }

    async willStart() {
        this.photos = await this.waitFor(rpc("/photos-clients/featured", { limit: this.limit }));
    }

    start() {
        const photos = this.photos.length
            ? this.photos
            : this.editMode
            ? Array.from({ length: this.limit }, () => ({}))
            : [];
        const contentEl = this.el.querySelector(".s_customer_photos_content");
        contentEl.replaceChildren(renderToElement("mconfort_customer_photos.FeaturedMosaic", { photos }));
    }

    destroy() {
        this.el.querySelector(".s_customer_photos_content").replaceChildren();
    }
}

registry.category("public.interactions").add("mconfort_customer_photos.s_customer_photos", CustomerPhotosSnippet);

registry.category("public.interactions.edit").add("mconfort_customer_photos.s_customer_photos", {
    Interaction: CustomerPhotosSnippet,
    mixin: (I) =>
        class extends I {
            setup() {
                super.setup();
                this.editMode = true;
            }
        },
});
