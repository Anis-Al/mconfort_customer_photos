# Part of the mconfort_customer_photos module. Licensed under LGPL-3.

{
    'name': "M'Confort Customer Photos",
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': "Customers share photos of their purchase; staff validate them; approved photos show on the website",
    'author': "Anis Alim",
    'maintainer': "Anis Alim",
    'depends': ['website_sale', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/customer_photo_views.xml',
        'views/res_config_settings_views.xml',
        'views/website_templates.xml',
        'views/snippets/s_customer_photos.xml',
        'data/ir_cron_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'mconfort_customer_photos/static/src/scss/customer_photos.scss',
            'mconfort_customer_photos/static/src/scss/s_customer_photos.scss',
            'mconfort_customer_photos/static/src/interactions/**/*',
            'mconfort_customer_photos/static/src/snippets/**/*',
        ],
        'website.website_builder_assets': [
            'mconfort_customer_photos/static/src/website_builder/**/*',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
}
