"""Accessp app with password policies."""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class APIAppConfig(AppConfig):
    """Password policies."""

    name = 'cpovc_api'
    verbose_name = _('Common API')
