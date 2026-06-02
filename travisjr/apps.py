from django.apps import AppConfig


class TravisjrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'travisjr'
    def ready(self):
        import travisjr.signals
