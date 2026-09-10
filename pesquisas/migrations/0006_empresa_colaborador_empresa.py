import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Lower


def vincular_colaboradores_existentes(apps, schema_editor):
    Empresa = apps.get_model('pesquisas', 'Empresa')
    Colaborador = apps.get_model('pesquisas', 'Colaborador')
    colaboradores_sem_empresa = Colaborador.objects.filter(empresa__isnull=True)
    if colaboradores_sem_empresa.exists():
        empresa, _ = Empresa.objects.get_or_create(nome='Não informada')
        colaboradores_sem_empresa.update(empresa=empresa)


class Migration(migrations.Migration):

    dependencies = [
        ('pesquisas', '0005_colaborador_data_ativacao'),
    ]

    operations = [
        migrations.CreateModel(
            name='Empresa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=200, unique=True)),
            ],
            options={
                'ordering': ('nome',),
                'constraints': [
                    models.UniqueConstraint(Lower('nome'), name='empresa_nome_unico_case_insensitive'),
                ],
            },
        ),
        migrations.AddField(
            model_name='colaborador',
            name='empresa',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='colaboradores',
                to='pesquisas.empresa',
            ),
        ),
        migrations.RunPython(vincular_colaboradores_existentes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='colaborador',
            name='empresa',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='colaboradores',
                to='pesquisas.empresa',
            ),
        ),
    ]
