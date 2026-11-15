"""Activity log — one row per change anyone makes (and per sign-in, download and analysis outcome).
Rows are append-only: there is no API to edit or delete them. Names are snapshotted so the log stays readable
after a user or deal is deleted."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    actor_name = models.CharField(max_length=255, blank=True)     # snapshot ('system' for the worker)
    action = models.CharField(max_length=60, db_index=True)        # e.g. deal.update, file.upload, auth.login
    summary = models.TextField(blank=True)
    deal_id = models.UUIDField(null=True, blank=True, db_index=True)
    deal_name = models.CharField(max_length=255, blank=True)
    target = models.CharField(max_length=255, blank=True)          # file name, framework key, user…
    changes = models.JSONField(default=dict, blank=True)           # {field: [old, new]} or request details
    ok = models.BooleanField(default=True)
    status_code = models.IntegerField(null=True, blank=True)
    method = models.CharField(max_length=8, blank=True)
    path = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-at', '-id']


def display_name(user) -> str:
    if not user or not getattr(user, 'is_authenticated', False):
        return ''
    return user.full_name or getattr(user, 'username', '') or user.email


def record(action: str, summary: str = '', *, actor=None, actor_name: str = '', deal=None, target: str = '',
           changes: dict | None = None, ok: bool = True, **extra) -> AuditEvent | None:
    """Write one event. Never raises — the log must not break the action it records."""
    try:
        if actor is not None and not getattr(actor, 'is_authenticated', False):
            actor = None
        return AuditEvent.objects.create(
            action=action, summary=summary[:4000], actor=actor, actor_name=actor_name or display_name(actor),
            deal_id=getattr(deal, 'pk', None), deal_name=getattr(deal, 'name', '') or '', target=target[:255],
            changes=changes or {}, ok=ok, **extra)
    except Exception:  # pragma: no cover
        import logging
        logging.getLogger(__name__).exception('audit record failed: %s', action)
        return None
