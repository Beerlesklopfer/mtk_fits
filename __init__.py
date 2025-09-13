from django.apps import AppConfig


class Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'fits'
    title              = 'Passungen nach DIN ISO 286'
    app                = 'fits'
    description        = 'Passungen nach DIN ISO 286'
    icon               = 'fa-solid fa-circle-nodes'
    color              = 'bg-primary'
    endpoint           = 'index'