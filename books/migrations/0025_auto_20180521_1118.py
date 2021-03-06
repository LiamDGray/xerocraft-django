# Generated by Django 2.0.3 on 2018-05-21 18:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0024_auto_20180510_1400'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='otheritemtype',
            options={'ordering': ['name']},
        ),
        migrations.AlterField(
            model_name='monetarydonation',
            name='earmark',
            field=models.ForeignKey(default=35, help_text='Specify a donation subaccount, when possible.', limit_choices_to=models.Q(models.Q(('parent_id', 35), ('id', 35), _connector='OR'), models.Q(_negated=True, id=49)), on_delete=django.db.models.deletion.PROTECT, to='books.Account'),
        ),
    ]
