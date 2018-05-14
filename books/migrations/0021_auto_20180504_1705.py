# Generated by Django 2.0.3 on 2018-05-05 00:05

from decimal import Decimal
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0020_journalentrylineitem_description'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='budget',
            name='begins',
        ),
        migrations.RemoveField(
            model_name='budget',
            name='ends',
        ),
        migrations.AddField(
            model_name='budget',
            name='year',
            field=models.IntegerField(default=2018, help_text='The fiscal year during which this budget applies.'),
        ),
        migrations.AlterField(
            model_name='budget',
            name='amount',
            field=models.DecimalField(decimal_places=2, help_text='The amount budgeted for the year.', max_digits=7, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))]),
        ),
    ]