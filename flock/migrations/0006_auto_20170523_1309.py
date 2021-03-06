# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-23 20:09
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flock', '0005_auto_20170520_2347'),
    ]

    operations = [
        migrations.AlterField(
            model_name='personinscheduledclass',
            name='status',
            field=models.CharField(choices=[('SO?', 'Verifying'), ('MAB', 'Maybe'), ('NOP', 'No'), ('YES', 'Yes'), ('INV', 'Invoiced'), ('G2G', 'Good to Go')], max_length=3),
        ),
        migrations.AlterField(
            model_name='resourceinscheduledclass',
            name='status',
            field=models.CharField(choices=[('SO?', 'Verifying'), ('G2G', 'Good to Go')], max_length=3),
        ),
    ]
