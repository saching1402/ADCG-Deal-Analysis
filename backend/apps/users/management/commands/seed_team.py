"""Create the team accounts once (never touches an existing account or password).
Starter password = DJANGO_SUPERUSER_PASSWORD; everyone should change it on the Account page."""
import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.users.models import Role, User

TEAM = [('ali', 'Ali', Role.ANALYST), ('ray', 'Ray', Role.ANALYST), ('lyes', 'Lyes', Role.ANALYST),
        ('admin', 'Admin', Role.ADMIN)]


class Command(BaseCommand):
    def handle(self, *args, **opts):
        owner_email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
        pw = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        owner = User.objects.filter(email__iexact=owner_email).first() if owner_email else None
        if owner:
            changed = []
            if owner.username != 'sachin' and not User.objects.filter(username='sachin').exclude(pk=owner.pk).exists():
                owner.username = 'sachin'; changed.append('username')
            if owner.full_name in ('', 'Admin'):
                owner.full_name = 'Sachin'; changed.append('full_name')
            if owner.password_changed_at is None:
                owner.password_changed_at = owner.date_joined or timezone.now(); changed.append('password_changed_at')
            if changed:
                owner.save(update_fields=changed)
        # spelling fix: the first seed used 'lyees'; rename while the account is untouched (starter password)
        old = User.objects.filter(username='lyees', password_changed_at__isnull=True).first()
        if old and not User.objects.filter(username='lyes').exists():
            old.username, old.full_name = 'lyes', 'Lyes'
            old.save(update_fields=['username', 'full_name'])
        User.objects.filter(email__iendswith='@deal-analysis.local').update(email=None)
        if not pw:
            self.stdout.write('DJANGO_SUPERUSER_PASSWORD not set — team accounts not created')
            return
        for un, name, role in TEAM:
            if User.objects.filter(username__iexact=un).exists():
                continue
            u = User(username=un, full_name=name, role=role, is_staff=(role == Role.ADMIN))
            u.set_password(pw)
            u.save()
            self.stdout.write(f'Team account created: {un} ({role})')
