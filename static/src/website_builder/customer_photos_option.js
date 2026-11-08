import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { BaseOptionComponent } from "@html_builder/core/utils";
import { BuilderAction } from "@html_builder/core/builder_action";

export class CustomerPhotosOption extends BaseOptionComponent {
    static template = "mconfort_customer_photos.CustomerPhotosOption";
    static selector = ".s_customer_photos";
}

export class CustomerPhotosSettingAction extends BuilderAction {
    static id = "customerPhotosSetting";
    static dependencies = ["edit_interaction"];

    getValue({ editingElement: el, params }) {
        return el.dataset[params.mainParam];
    }
    isApplied({ editingElement: el, params, value }) {
        return el.dataset[params.mainParam] === value;
    }
    apply({ editingElement: el, params, value }) {
        el.dataset[params.mainParam] = value;
        this.dependencies.edit_interaction.restartInteractions(el);
    }
}

class CustomerPhotosOptionPlugin extends Plugin {
    static id = "customerPhotosOption";
    resources = {
        builder_options: [CustomerPhotosOption],
        builder_actions: { CustomerPhotosSettingAction },
    };
}

registry.category("website-plugins").add(CustomerPhotosOptionPlugin.id, CustomerPhotosOptionPlugin);
