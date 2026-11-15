"""Create the team accounts once (never touches an existing account or password).
Starter password = DJANGO_SUPERUSER_PASSWORD; everyone should change it on the Account page."""
import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.users.models import Role, User

TEAM = [('ali', 'Ali', Role.ANALYST), ('ray', 'Ray', Role.ANALYST), ('lyees', 'Lyees', Role.ANALYST),
        ('admin', 'Admin', Role.ADMIN)]


class Command(BaseCommand):
    def handle(self, *args, **opts):
        owner_email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
        pw = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        owner = User.objects.filter(email__iexact=owner_email).first() if owner_email else None
        if owner:
            changed = []
            if not owner.username and not User.objects.filter(username='sachin').exists():
                owner.username = 'sachin'; changed.append('username')
            if owner.full_name in ('', 'Admin'):
                owner.full_name = 'Sachin'; changed.append('full_name')
            if owner.password_changed_at is None:
                owner.password_changed_at = owner.date_joined or timezone.now(); changed.append('password_changed_at')
            if changed:
                owner.save(update_fields=changed)
        if not pw:
            self.stdout.write('DJANGO_SUPERUSER_PASSWORD not set — team accounts not created')
            return
        for un, name, role in TEAM:
            if User.objects.filter(username__iexact=un).exists():
                continue
            email = f'{un}@deal-analysis.local'
            if User.objects.filter(email__iexact=email).exists():
                continue
            u = User(email=email, username=un, full_name=name, role=role, is_staff=(role == Role.ADMIN))
            u.set_password(pw)
            u.save()
            self.stdout.write(f'Team account created: {un} ({role})')
