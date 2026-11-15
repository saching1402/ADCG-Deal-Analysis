"""Sign in by username; email becomes optional. Fills usernames, drops placeholder team emails."""
from django.db import migrations, models


def fill(apps, schema_editor):
    User = apps.get_model('users', 'User')
    taken = set(u.lower() for u in User.objects.exclude(username__isnull=True).values_list('username', flat=True))
    for u in User.objects.filter(username__isnull=True):
        base = (u.email or 'user').split('@')[0].lower() or 'user'
        name, n = base, 2
        while name in taken:
            name, n = f'{base}{n}', n + 1
        taken.add(name)
        u.username = name
        u.save(update_fields=['username'])
    User.objects.filter(email__iendswith='@deal-analysis.local').update(email=None)


class Migration(migrations.Migration):
    dependencies = [('users', '0002_user_password_changed_at_user_username')]
    operations = [
        migrations.AlterField('user', 'email', models.EmailField(blank=True, max_length=254, null=True, unique=True, verbose_name='email address')),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AlterField('user', 'username', models.CharField(max_length=40, unique=True)),
        migrations.AlterModelOptions('user', {'ordering': ['username']}),
    ]
