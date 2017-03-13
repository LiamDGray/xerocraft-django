# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-28 19:58
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0055_auto_20170127_1208'),
    ]

    operations = [
        migrations.AddField(
            model_name='expenseclaim',
            name='donate_reimbursement',
            field=models.BooleanField(default=False, help_text='Claimant will not receive a payment. Reimbursement will become a donation.'),
        ),
        migrations.AlterField(
            model_name='expenselineitem',
            name='amount',
            field=models.DecimalField(decimal_places=2, help_text='The dollar amount for this line item BEFORE any discount.', max_digits=6),
        ),
    ]