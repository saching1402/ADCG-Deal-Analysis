from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('deals', '0026_fund_vintage_quartiles')]
    operations = [
        migrations.AddField('analysisjob', 'result', models.JSONField(blank=True, default=dict)),
        migrations.AlterField('analysisjob', 'mode', models.CharField(default='full', max_length=10)),
    ]
