"""Files read before the verification gate existed: re-queue any whose fact sheet fails the quality check,
and every PDF/PowerPoint that went through the old text-only fallback, so the next run reads them properly."""
from django.db import migrations


def reverify(apps, schema_editor):
    from apps.deals.extract import Part, digest_ok
    DealFile = apps.get_model('deals', 'DealFile')
    for f in DealFile.objects.filter(status='digested'):
        ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
        old_fallback = f.method == 'text' and ext in ('pdf', 'pptx', 'ppt')
        ok, _ = digest_ok(f.digest, Part('', []))
        if old_fallback or not ok:
            f.status, f.digest, f.error = 'uploaded', '', ''
            f.save(update_fields=['status', 'digest', 'error'])


class Migration(migrations.Migration):
    dependencies = [('deals', '0003_file_checks')]
    operations = [migrations.RunPython(reverify, migrations.RunPython.noop)]
