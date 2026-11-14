from django.db import migrations


def fill(apps, schema_editor):
    from apps.deals.roles import guess_role
    DealFile = apps.get_model('deals', 'DealFile')
    for f in DealFile.objects.filter(doc_role=''):
        f.doc_role = guess_role(f.name, f.digest)
        f.save(update_fields=['doc_role'])


class Migration(migrations.Migration):
    dependencies = [('deals', '0006_roles_and_risk')]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
