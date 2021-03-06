# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-09 22:26
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flock', '0002_auto_20170408_1653'),
    ]

    operations = [
        migrations.AlterField(
            model_name='timepattern',
            name='person',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='flock.Person'),
        ),
        migrations.AlterField(
            model_name='timepattern',
            name='resource',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='flock.Resource'),
        ),
    ]
