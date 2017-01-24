# pylint: disable=C0330

# Standard
from datetime import date
from decimal import Decimal
from typing import Dict, List
import abc
from logging import getLogger

# Third party
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from nameparser import HumanName
from django.core.urlresolvers import reverse

# Local
from abutils.utils import generate_ctrlid

logger = getLogger("books")

ORG_NAME = settings.XEROPS_CONFIG['ORG_NAME']

# class PayerAKA(models.Model):
#     """ Intended primarily to record name variations that are used in payments, etc. """
#
#     member = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE,
#         help_text="The member who has payments under another name.")
#
#     aka = models.CharField(max_length=50, null=False, blank=False,
#         help_text="The AKA, probably their spouse's name or a simple variation on their own name.")
#
#     class Meta:
#         verbose_name = "Payer AKA"


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# CTRLID UTILITIES
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =


def next_monetarydonation_ctrlid() -> str:
    """Provides an arbitrary default value for the ctrlid field, necessary when data is being entered manually."""
    return generate_ctrlid(MonetaryDonation)


def next_sale_ctrlid() -> str:
    '''Provides an arbitrary default value for the ctrlid field, necessary when check, cash, or gift-card data is being entered manually.'''
    return generate_ctrlid(Sale)


def next_otheritem_ctrlid() -> str:
    """Provides an arbitrary default value for the ctrlid field, necessary when data is being entered manually."""
    return generate_ctrlid(OtherItem)


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# Note
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class Note(models.Model):

    author = models.ForeignKey(User, null=True, blank=True,
        on_delete=models.SET_NULL,  # Keep the note even if the user is deleted.
        help_text="The user who wrote this note.")

    content = models.TextField(max_length=2048,
        help_text="Anything you want to say about the item on which this note appears.")

    def __str__(self):
        return self.content[:40]

    class Meta:
        abstract = True


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# Account
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class Account(models.Model):

    name = models.CharField(max_length=40, blank=True,
        help_text="Name of the account.")

    CAT_ASSET     = "A"
    CAT_LIABILITY = "L"
    CAT_EQUITY    = "Q"
    CAT_REVENUE   = "R"
    CAT_EXPENSE   = "X"
    CAT_CHOICES = [
        (CAT_ASSET,     "Asset"),
        (CAT_LIABILITY, "Liability"),
        (CAT_EQUITY,    "Equity"),
        (CAT_REVENUE,   "Revenue"),
        (CAT_EXPENSE,   "Expense"),
    ]
    category = models.CharField(max_length=1, choices=CAT_CHOICES,
        null=False, blank=False,
        help_text="The category of the account.")

    TYPE_CREDIT = "C"
    TYPE_DEBIT  = "D"
    TYPE_CHOICES = [
        (TYPE_CREDIT, "Credit"),
        (TYPE_DEBIT,  "Debit"),
    ]
    type = models.CharField(max_length=1, choices=TYPE_CHOICES,
        null=False, blank=False,
        help_text="The type of the account.")

    manager = models.ForeignKey(User, null=True, blank=True,
        on_delete=models.SET_NULL,  # Keep this account even if the user is deleted.
        help_text="The user who manages this account.")

    description = models.TextField(max_length=1024,
        help_text="A discussion of the account's purpose. What is it for? What is it NOT for?")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class AccountGroup(models.Model):
    name = models.CharField(max_length=40, blank=True,
        help_text="Name of the group.")

    description = models.TextField(max_length=1024,
        help_text="The group's purpose, e.g. 'This acct group corresponds to a budget line item.'")

    accounts = models.ManyToManyField(to=Account,
        help_text="The accounts that are part of this group.")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

try:
    ACCT_LIABILITY_PAYABLE = Account.objects.get(name="Accounts Payable")
    ACCT_LIABILITY_UNEARNED_MSHIP_REVENUE = Account.objects.get(name="Unearned Membership Revenue")
    ACCT_ASSET_RECEIVABLE = Account.objects.get(name="Accounts Receivable")
    ACCT_ASSET_CASH = Account.objects.get(name="Cash")
    ACCT_EXPENSE_BUSINESS = Account.objects.get(name="Expense, Business")
    ACCT_REVENUE_DONATION = Account.objects.get(name="Revenue, Cash Donations")
    ACCT_REVENUE_MEMBERSHIP = Account.objects.get(name="Revenue, Membership")
except Account.DoesNotExist as e:
    logger.exception("Couldn't find account.")


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# JOURNAL - The journal is generated (and regenerated) from other models
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class JournalEntry(models.Model):

    frozen = models.BooleanField(default=False,
        help_text="If frozen, this entry (and its lines) won't be deleted/regenerated.")

    source_url = models.URLField(blank=False, null=False,
        help_text="URL to retrieve the item that gave rise to this journal entry.")

    when = models.DateField(null=False, blank=False,
        help_text="The date of the transaction.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prebatched lineitems are JournalEntryLineItems that are waiting for their associated
        # JournalEntry to get a PK in the database, at which time they'll have their
        # journal_entry_id assigned and they'll be batched.
        self.prebatched_lineitems = []  # type:List[JournalEntryLineItem]

    def prebatch(self, jeli: 'JournalEntryLineItem'):
        self.prebatched_lineitems.append(jeli)
        return jeli

    def process_prebatch(self):
        if len(self.prebatched_lineitems) == 0:
            print("Journal Entry for {} has no line items!".format(self.source_url))
        for jeli in self.prebatched_lineitems:
            jeli.journal_entry_id = self.id
            JournalLiner.batch(jeli)
        self.prebatched_lineitems = []

    def debits_and_credits(self):
        total_debits = Decimal(0.0)
        total_credits = Decimal(0.0)
        for line in self.journalentrylineitem_set.all():  # type: JournalEntryLineItem
            if line.iscredit():
                total_credits += line.amount
            else:
                total_debits += line.amount
        return total_debits, total_credits

    def dbcheck(self):
        # Relationships can't be checked in clean but can be checked later in a "db check" operation.
        total_debits, total_credits = self.debits_and_credits()
        if total_credits != total_debits:
            raise ValidationError(
                _("Total credits do not equal total debits (dr {} != cr {}.").format(total_debits, total_credits)
            )

    def __str__(self):
        return "Journal Entry #{} dated {}".format(self.pk, self.when)

    class Meta:
        ordering = ['when']


class JournalEntryLineItem(models.Model):

    journal_entry = models.ForeignKey(JournalEntry, null=False, blank=False,
        on_delete=models.CASCADE,  # Deletion and regeneration of journal entries will be common.
        help_text="The journal entry that this line item is part of.")

    account = models.ForeignKey(Account, null=False, blank=False,
        on_delete=models.PROTECT,  # Don't allow account to be deleted if transaction lines reference it.
        help_text="The account involved in this line item.")

    # "Increase" can mean 'credit' OR 'debit', depending on the account referenced! The same is true for "Decrease".
    # This approach is intended to make code more intuitive. Note that iscredit() and isdebit() can be used
    # to determine the traditional dual entry bookkeeping status of the line.
    ACTION_BALANCE_INCREASE = ">"
    ACTION_BALANCE_DECREASE = "<"
    ACTION_CHOICES = [
        (ACTION_BALANCE_INCREASE, "Increase"),
        (ACTION_BALANCE_DECREASE, "Decrease"),
    ]
    action = models.CharField(max_length=1, choices=ACTION_CHOICES,
        null=False, blank=False,
        help_text="Is the account balance increased or decreased?")

    amount = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The amount of the increase or decrease (always positive)",
        validators=[MinValueValidator(Decimal('0.00'))])

    def iscredit(self):
        if self.account.type == Account.TYPE_CREDIT:
            return self.action == self.ACTION_BALANCE_INCREASE
        if self.account.type == Account.TYPE_DEBIT:
            return self.action == self.ACTION_BALANCE_DECREASE

    def isdebit(self):
        return not self.iscredit()

    def __str__(self):
        actionstrs = dict(self.ACTION_CHOICES)
        dr_or_cr = "cr" if self.iscredit() else "dr"
        return "Line Item #{}, {} '{}', ${} {}".format(
            self.pk,
            actionstrs[self.action],
            str(self.account),
            self.amount,
            dr_or_cr,
        )


class Journaler(models.Model):

    __metaclass__ = abc.ABCMeta

    _batch = list()  # type:List[JournalEntry]
    _link_names_of_relevant_children = None
    _unbalanced_journal_entries = list()  # type:List[JournalEntry]
    _grand_total_debits = Decimal(0.00)
    _grand_total_credits = Decimal(0.00)

    class Meta:
        abstract = True

    # Each journaler will have its own logic for creating a journal entry.
    @abc.abstractmethod
    def create_journalentry(self):
        """
        Create the journal entry associated with this Journaler.
        Also create any line items that are intrinsic to the Journaler.
        Don't create line items that arise from JournalLiner children.
        """
        raise NotImplementedError

    @classmethod
    def link_names_of_relevant_children(cls):
        if cls._link_names_of_relevant_children == None:
            related_objects = [
                f for f in cls._meta.get_fields()
                  if (f.one_to_many or f.one_to_one)
                  and f.auto_created
                  and not f.concrete
            ]
            cls._link_names_of_relevant_children = [
                rel.get_accessor_name() for rel in related_objects
                  if (not hasattr(rel.field, 'is_not_parent'))  # Indicates that link is to a PEER transaction and not to a parent transaction.
                  and issubclass(rel.field.model, JournalLiner)
                ]
        return cls._link_names_of_relevant_children

    def create_lineitems_for(self, je: JournalEntry):
        link_names = self.link_names_of_relevant_children()
        for link_name in link_names:
            children = getattr(self, link_name).all()
            for child in children:
                child.create_journalentry_lineitems(je)

    def get_absolute_url(self):
        content_type = ContentType.objects.get_for_model(self.__class__)
        url_name = "admin:{}_{}_change".format(content_type.app_label, content_type.model)
        return reverse(url_name, args=[str(self.id)])

    @classmethod
    def save_batch(cls):
        # NOTE: As of 1/18/2016, this will only work in Django version 1.10 with Postgres
        JournalEntry.objects.bulk_create(cls._batch)
        for je in cls._batch:
            je.process_prebatch()
        cls._batch = []

    @classmethod
    def batch(cls, je: JournalEntry):
        balance = Decimal(0.00)
        for jeli in je.prebatched_lineitems:
            if jeli.iscredit():
                balance += jeli.amount
                cls._grand_total_credits += jeli.amount
            else:
                balance -= jeli.amount
                cls._grand_total_debits += jeli.amount
        if balance != Decimal(0.00):
            cls._unbalanced_journal_entries.append(je)
            # TODO: Perhaps set an IsUnbalanced field to True instead?
        cls._batch.append(je)
        if len(cls._batch) > 1000:
            cls.save_batch()
        return je

    @classmethod
    def get_unbalanced_journal_entries(cls):
        return cls._unbalanced_journal_entries


class JournalLiner:
    __metaclass__ = abc.ABCMeta

    _batch = list()  # type:List[JournalEntryListItem]

    # Each journal liner will have its own logic for creating its line items in the specified entry.
    @abc.abstractmethod
    def create_journalentry_lineitems(self, je: JournalEntry):
        raise NotImplementedError

    @classmethod
    def save_batch(cls):
        created = JournalEntryLineItem.objects.bulk_create(cls._batch)
        cls._batch = []

    @classmethod
    def batch(cls, jeli: JournalEntryLineItem):
        cls._batch.append(jeli)
        if len(cls._batch) > 1000:
            cls.save_batch()
        return jeli


registered_journaler_classes = []  # type: List[Journaler]


def register_journaler():
    """ Registers the given journaler class so that it will participate in bookkeeping """
    def _decorator(journaler_class):
        if not issubclass(journaler_class, Journaler):
            raise ValueError("Registered class must be a Journaler")
        registered_journaler_classes.append(journaler_class)
        return journaler_class
    return _decorator


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# ENTITY - Any person or organization that is not a member.
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class Entity(models.Model):

    name = models.CharField(max_length=40, blank=False,
        help_text="Name of person/organization.")

    email = models.EmailField(max_length=40, blank=True,
        help_text="Email address of person/organization.")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Non-Member Entity"
        verbose_name_plural = "Non-Member Entities"


class EntityNote(Note):

    entity = models.ForeignKey(Entity,
        on_delete=models.CASCADE,  # No point in keeping the note if the entity is gone.
        help_text="The entity to which the note pertains.")


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# INVOICES
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

def make_InvoiceBase(help: Dict[str, str]):

    class InvoiceBase(Journaler):

        invoice_date = models.DateField(null=False, blank=False, default=date.today,
            help_text = help["invoice_date"])

        user = models.ForeignKey(User, null=True, blank=True, default=None,
            on_delete=models.SET_NULL,
            help_text=help["user"])

        entity = models.ForeignKey(Entity, null=True, blank=True, default=None,
            on_delete=models.SET_NULL,
            help_text = help["entity"])

        amount = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
            help_text=help["amount"])

        description = models.TextField(max_length=1024,
            help_text = help["description"])

        def name(self):
            if self.entity is not None:
                return self.entity.name
            else:
                return self.user.username

        def clean(self):
            super().clean()

            if self.user is None and self.entity is None:
                raise ValidationError(_("Either user or entity must be specified."))

            if self.user is not None and self.entity is not None:
                raise ValidationError(_("Only one of user or entity can be specified."))

        def dbcheck(self):
            if self.amount != self.checksum():
                raise ValidationError(_("Total of line items must match amount of invoice."))

        class Meta:
            abstract = True

    return InvoiceBase


recv_invoice_help = {
    "invoice_date": "The date on which the invoice was created.",
    "user":         "If a user owes us, specify them here.",
    "entity":       "If some outside person/org owes us, specify them here.",
    "amount":       "The dollar amount we are invoicing them for.",
    "description":  "Description of goods and/or services we delivered to them.",
    "account":      "The revenue account associated with this invoice.",
}

@register_journaler()
class ReceivableInvoice(make_InvoiceBase(recv_invoice_help)):

    def checksum(self) -> Decimal:
        """
        :return: The sum total of all line items. Should match self.amount.
        """
        total = Decimal(0.0)
        for lineitem in self.receivableinvoicelineitem_set.all():
            total += lineitem.amount
        return total

    def __str__(self):
        return "${} owed to us by {} as of {}".format(
            self.amount,
            self.name(),
            self.invoice_date)

    def create_journalentry(self):
        je = JournalEntry(
            when=self.invoice_date,
            source_url=self.get_absolute_url(),
        )
        je.prebatch(JournalEntryLineItem(
            account=ACCT_ASSET_RECEIVABLE,
            action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
            amount=self.amount
        ))
        self.create_lineitems_for(je)
        Journaler.batch(je)

class ReceivableInvoiceNote(Note):

    invoice = models.ForeignKey(ReceivableInvoice,
        on_delete=models.CASCADE,  # No point in keeping the note if the invoice is gone.
        help_text="The invoice to which the note pertains.")


payable_invoice_help = {
    "invoice_date": "The date of the invoice.",
    "user":         "If we owe a user, specify them here.",
    "entity":       "If we owe some outside person/org, specify them here.",
    "amount":       "The dollar amount they invoiced.",
    "description":  "Description of goods and/or services we received from them.",
    "account":      "The expense account associated with this invoice.",
}


@register_journaler()
class PayableInvoice(make_InvoiceBase(payable_invoice_help)):

    def checksum(self) -> Decimal:
        """
        :return: The sum total of all line items. Should match self.amount.
        """
        total = Decimal(0.0)
        for lineitem in self.payableinvoicelineitem_set.all():
            total += lineitem.amount
        return total

    def __str__(self):
        return "${} owed to {} as of {}".format(
            self.amount,
            self.name(),
            self.invoice_date)

    def create_journalentry(self):
        je = JournalEntry(
            when=self.invoice_date,
            source_url=self.get_absolute_url(),
        )
        je.prebatch(JournalEntryLineItem(
            account=ACCT_LIABILITY_PAYABLE,
            action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
            amount=self.amount
        ))
        self.create_lineitems_for(je)
        Journaler.batch(je)

class PayableInvoiceNote(Note):

    invoice = models.ForeignKey(PayableInvoice,
        on_delete=models.CASCADE,  # No point in keeping the note if the invoice is gone.
        help_text="The invoice to which the note pertains.")


class InvoiceLineItem(models.Model):

    description = models.CharField(max_length=128, blank=False,
        help_text="A brief description of this line item.")

    delivery_date = models.DateField(null=False, blank=False,
        help_text="The date on which this line item was delivered.")

    amount = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The dollar amount for this line item.")

    account = models.ForeignKey(Account, null=False, blank=False,
        on_delete=models.PROTECT, # Don't allow acct to be deleted if there are invoices pointing to it.
        help_text="The account associated with this line item.")

    class Meta:
        abstract = True


class ReceivableInvoiceLineItem(InvoiceLineItem, JournalLiner):

    inv = models.ForeignKey(ReceivableInvoice, null=True, blank=True,
        on_delete=models.CASCADE,  # Line items are parts of the larger invoice, so delete if invoice is deleted.
        help_text="The receivable invoice on which this line item appears.")

    def clean(self):
        super().clean()

        if self.account.category is not Account.CAT_REVENUE:
             raise ValidationError(_("Account chosen must have category REVENUE."))

        if self.account.type is not Account.TYPE_CREDIT:
            raise ValidationError(_("Account chosen must have type CREDIT."))

    def create_journalentry_lineitems(self, je: JournalEntry):
        je.prebatch(JournalEntryLineItem(
            account=self.account,
            action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
            amount=self.amount
        ))


class PayableInvoiceLineItem(InvoiceLineItem, JournalLiner):

    inv = models.ForeignKey(PayableInvoice, null=True, blank=True,
        on_delete=models.CASCADE,  # Line items are parts of the larger invoice, so delete if invoice is deleted.
        help_text="The payable invoice on which this line item appears.")

    def clean(self):
        super().clean()

        if self.account.category not in [Account.CAT_EXPENSE, Account.CAT_ASSET]:
             raise ValidationError(_("Account chosen must have category EXPENSE or ASSET."))

        if self.account.type is not Account.TYPE_DEBIT:
            raise ValidationError(_("Account chosen must have type DEBIT."))

    def create_journalentry_lineitems(self, je: JournalEntry):
        je.prebatch(JournalEntryLineItem(
            account=self.account,
            action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
            amount=self.amount
        ))


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# SALE (aka Income Transaction in Admin)
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

@register_journaler()
class Sale(Journaler):

    sale_date = models.DateField(null=False, blank=False, default=date.today,
        help_text="The date on which the sale was made. Best guess if exact date not known.")

    deposit_date = models.DateField(null=True, blank=True, default=None,
        help_text="The date on which the income from this sale was (or will be) deposited.")

    payer_acct = models.ForeignKey(User, null=True, blank=True, default=None,
        on_delete=models.SET_NULL,  # Keep the note even if the user is deleted.
        help_text="It's preferable, but not necessary, to refer to the customer's account.")

    payer_name = models.CharField(max_length=40, blank=True,
        help_text="Name of person who made the payment. Not necessary if account was linked.")

    payer_email = models.EmailField(max_length=40, blank=True,
        help_text="Email address of person who made the payment.")

    PAID_BY_CASH     = "$"
    PAID_BY_CHECK    = "C"
    PAID_BY_SQUARE   = "S"
    PAID_BY_2CO      = "2"
    PAID_BY_WEPAY    = "W"
    PAID_BY_PAYPAL   = "P"
    PAID_BY_GOFUNDME = "G"
    PAID_BY_CHOICES = [
        (PAID_BY_CASH,     "Cash"),
        (PAID_BY_CHECK,    "Check"),
        (PAID_BY_SQUARE,   "Square"),
        (PAID_BY_2CO,      "2Checkout"),
        (PAID_BY_WEPAY,    "WePay"),
        (PAID_BY_PAYPAL,   "PayPal"),
        (PAID_BY_GOFUNDME, "GoFundMe"),
    ]
    payment_method = models.CharField(max_length=1, choices=PAID_BY_CHOICES,
        null=False, blank=False, default=PAID_BY_CASH,
        help_text="The payment method used.")
    payment_method.verbose_name = "Method"

    method_detail = models.CharField(max_length=40, blank=True,
        help_text="Optional detail specific to the payment method. Check# for check payments.")
    method_detail.verbose_name = "Detail"

    total_paid_by_customer = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The full amount paid by the person, including payment processing fee IF CUSTOMER PAID IT.")
    total_paid_by_customer.verbose_name = "Total Paid"

    processing_fee = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False, default=0,
        help_text="Payment processor's fee, REGARDLESS OF WHO PAID FOR IT. Zero for cash/check.")
    processing_fee.verbose_name = "Fee"

    FEE_PAID_BY_NOBODY = "N"
    FEE_PAID_BY_CUSTOMER = "C"
    FEE_PAID_BY_US = "U"
    FEE_PAID_CHOICES = [
        (FEE_PAID_BY_NOBODY, "N/A"),
        (FEE_PAID_BY_CUSTOMER, "Customer"),
        (FEE_PAID_BY_US, ORG_NAME),
    ]
    fee_payer = models.CharField(max_length=1, choices=FEE_PAID_CHOICES,
        null=False, blank=False, default=FEE_PAID_BY_US,
        help_text="Who paid the processing fee (if any)?")

    ctrlid = models.CharField(max_length=40, null=False, blank=False, default=next_sale_ctrlid,
        help_text="Payment processor's id for this payment.")

    protected = models.BooleanField(default=False,
        help_text="Protect against further auto processing by ETL, etc. Prevents overwrites of manually enetered data.")

    def link_to_user(self):

        if self.protected:
            return

        # Attempt to match by EMAIL
        try:
            email_matches = User.objects.filter(email=self.payer_email)
            if len(email_matches) == 1:
                self.payer_acct = email_matches[0]
        except User.DoesNotExist:
            pass

        # Attempt to match by NAME
        nameobj = HumanName(str(self.payer_name))
        fname = nameobj.first
        lname = nameobj.last
        try:
            name_matches = User.objects.filter(first_name__iexact=fname, last_name__iexact=lname)
            if len(name_matches) == 1:
                self.payer_acct = name_matches[0]
            # TODO: Else log WARNING (or maybe just INFO)
        except User.DoesNotExist:
            pass

    class Meta:
        unique_together = ('payment_method', 'ctrlid')
        verbose_name = "Income transaction"

    def checksum(self) -> Decimal:
        """
        :return: The sum total of all expense line items. Should match self.amount.
        """
        total = Decimal(0.0)

        # This is coded generically because the 'books' app doesn't know which models in other
        # apps will point back to a sale. So it looks for fields like "sale_price" and "qty_sold"
        # in all related models.

        # This is the new way to get_all_related_objects
        # per https://docs.djangoproject.com/en/1.10/ref/models/meta/
        related_objects = [
            f for f in self._meta.get_fields()
              if (f.one_to_many or f.one_to_one)
              and f.auto_created
              and not f.concrete
        ]
        link_names = [rel.get_accessor_name() for rel in related_objects]
        for link_name in link_names:
            if link_name in ['salenote_set', 'receivableinvoicereference_set']: continue
            # TODO: Can a select_related or prefetch_related improve performance here?
            line_items = getattr(self, link_name).all()
            for line_item in line_items:
                line_total = Decimal(0.0)
                if hasattr(line_item, 'amount'): line_total += line_item.amount
                elif hasattr(line_item, 'sale_price'): line_total += line_item.sale_price
                if hasattr(line_item, 'qty_sold'): line_total *= line_item.qty_sold
                total += line_total
        for invref in self.receivableinvoicereference_set.all():
            total += invref.portion if invref.portion is not None else invref.invoice.amount
        return total

    def clean(self):
        super().clean()

        # The following is a noncritical constraint, enforced here:
        if self.processing_fee == Decimal(0.00) and self.fee_payer != self.FEE_PAID_BY_NOBODY:
            self.fee_payer = self.FEE_PAID_BY_NOBODY

        if self.deposit_date is not None and self.sale_date is not None \
         and self.deposit_date < self.sale_date:
            raise ValidationError(_("Deposit date cannot be earlier than sale date."))

        if self.payment_method == self.PAID_BY_CHECK \
          and self.method_detail > "" and not self.method_detail.isnumeric():
            raise ValidationError(_("Detail for check payments should only be the bare check number without # or other text."))

        if self.payment_method == self.PAID_BY_CASH and self.method_detail > "":
            raise ValidationError(_("Cash payments shouldn't have detail. Cash is cash."))

    def dbcheck(self):
        sum = self.checksum()
        checksum_matches = sum == self.total_paid_by_customer \
         or sum == self.total_paid_by_customer - self.processing_fee
        if not checksum_matches:
            raise ValidationError(_("Total of line items must match amount transaction."))

    def __str__(self):
        if self.payer_name > "": return "{} sale to {}".format(self.sale_date, self.payer_name)
        elif self.payer_acct is not None: return "{} sale to {}".format(self.sale_date, self.payer_acct)
        elif self.payer_email > "": return "{} sale to {}".format(self.sale_date, self.payer_email)
        else: return "{} sale".format(self.sale_date)

    def create_journalentry(self):
        je = JournalEntry(
            when=self.sale_date,
            source_url=self.get_absolute_url(),
        )
        je.prebatch(JournalEntryLineItem(
            account=ACCT_ASSET_CASH,
            action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
            amount=self.total_paid_by_customer-self.processing_fee
        ))
        if self.processing_fee > Decimal(0.00):
            if self.fee_payer == self.FEE_PAID_BY_US:
                je.prebatch(JournalEntryLineItem(
                    account=ACCT_EXPENSE_BUSINESS,
                    action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
                    amount=self.processing_fee
                ))

        self.create_lineitems_for(je)
        Journaler.batch(je)


class SaleNote(Note):

    sale = models.ForeignKey(Sale,
        on_delete=models.CASCADE,  # No point in keeping the note if the sale is gone.
        help_text="The sale to which the note pertains.")


class OtherItemType(models.Model):
    """Cans of soda, bumper stickers, materials, etc."""

    name = models.CharField(max_length=40, unique=True,
        help_text="A short name for the item.")

    description = models.TextField(max_length=1024,
        help_text="A description of the item.")

    # TODO:
    # Revenue acct shouldn't ever be null but needs to temporarily so I can fix up existing entries.
    # Switch to null=False, blank=False, and delete default.
    revenue_acct = models.ForeignKey(Account, null=True, blank=True, default=None,
        on_delete=models.PROTECT,  # Don't allow deletion of acct if item types reference it.
        help_text="The revenue account associated with items of this type.")

    def __str__(self):
        return self.name


class OtherItem(models.Model, JournalLiner):

    type = models.ForeignKey(OtherItemType, null=False, blank=False, default=None,
        on_delete=models.PROTECT,  # Don't allow deletion of an item type that appears in a sale.
        help_text="The type of item sold.")

    # Sale related fields: sale, sale_price, qty_sold
    sale = models.ForeignKey(Sale,
        on_delete=models.CASCADE,  # No point in keeping the line item if the sale is gone.
        help_text="The sale for which this is a line item.")

    sale_price = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The UNIT price at which this/these item(s) sold.")

    qty_sold = models.IntegerField(null=False, blank=False, default=1,
        help_text="The quantity of the item sold.")

    # ETL related fields: sale, sale_price, qty_sol
    ctrlid = models.CharField(max_length=40, null=False, blank=False, unique=True,
        default=next_otheritem_ctrlid,
        help_text="Payment processor's id for this donation, if any.")

    protected = models.BooleanField(default=False,
        help_text="Protect against further auto processing by ETL, etc. Prevents overwrites of manually entered data.")

    def __str__(self):
        return self.type.name

    def create_journalentry_lineitems(self, je: JournalEntry):
        je.prebatch(JournalEntryLineItem(
            account=self.type.revenue_acct,
            action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
            amount=self.sale_price*self.qty_sold,
        ))


class MonetaryDonationReward(models.Model):

    name = models.CharField(max_length=40, blank=False,
        help_text="Name of the reward.")

    min_donation = models.DecimalField(max_digits=6, decimal_places=2,
        null=False, blank=False, default=Decimal(0.0),
        help_text="The minimum donation required to earn this reward.")

    cost_to_org = models.DecimalField(max_digits=6, decimal_places=2,
        null=False, blank=False, default=Decimal(0.0),
        help_text="The cost of this reward to {}.".format(ORG_NAME))

    fair_mkt_value = models.DecimalField(max_digits=6, decimal_places=2,
        null=False, blank=False, default=Decimal(0.0),
        help_text="The value of this reward to the donor, for tax purposes.")

    description = models.TextField(max_length=1024,
        help_text="Description of the reward.")

    def clean(self):
        super().clean()

        if self.cost_to_org > self.min_donation:
            raise ValidationError(_("Min donation should cover the cost of the reward."))

    def __str__(self):
        return self.name


class MonetaryDonation(models.Model, JournalLiner):

    # NOTE: A monetary donation can ONLY appear on a Sale.

    sale = models.ForeignKey(Sale, null=False, blank=False,
        on_delete=models.CASCADE,  # Line items are parts of the sale so they should be deleted.
        help_text="The sale that includes this line item.")

    amount = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The amount donated.")

    earmark = models.ForeignKey(Account, null=True, blank=True,
        on_delete=models.SET_NULL,  # In the unlikely evt that acct vanishes, just point to null.
        help_text="The account for which this donation is earmarked.")

    reward = models.ForeignKey(MonetaryDonationReward, null=True, blank=True, default=None,
        on_delete=models.PROTECT,  # Don't allow a reward to be deleted if donations point to it.
        help_text="The reward given to the donor, if any.")

    ctrlid = models.CharField(max_length=40, null=False, blank=False, unique=True,
        default=next_monetarydonation_ctrlid,
        help_text="Payment processor's id for this donation, if any.")

    protected = models.BooleanField(default=False,
        help_text="Protect against further auto processing by ETL, etc. Prevents overwrites of manually entered data.")

    def __str__(self):
        return str("$"+str(self.amount))

    def create_journalentry_lineitems(self, je: JournalEntry):
        je.prebatch(JournalEntryLineItem(
            account=ACCT_REVENUE_DONATION,
            action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
            amount=self.amount,
        ))


class ReceivableInvoiceReference(models.Model, JournalLiner):
    sale = models.ForeignKey(Sale, null=False, blank=False,
        on_delete=models.CASCADE,  # Delete this relation if the income transaction is deleted.
        help_text="The income transaction that pays the invoice.")

    # I wanted the following to be OneToOne but there might be multiple partial payments
    # toward a single invoice. I.e. I'm paralleling the ExpenseClaimReference case.
    invoice = models.ForeignKey(ReceivableInvoice, null=False, blank=False,
        on_delete=models.CASCADE,  # Delete this relation if the invoice is deleted.
        help_text="The invoice that is paid by the income transaction.")
    # 'not_part_of', below, indicates that this Reference is not part of the referenced Invoice.
    invoice.is_not_parent = True

    portion = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, default=None,
        help_text="Leave blank unless they're only paying a portion of the invoice.")

    def create_journalentry_lineitems(self, je: JournalEntry):

        amount = self.invoice.amount

        if self.portion is not None:
            amount = self.portion

        je.prebatch(JournalEntryLineItem(
            account=ACCT_ASSET_RECEIVABLE,
            action=JournalEntryLineItem.ACTION_BALANCE_DECREASE,
            amount=amount,
        ))


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# FUND RAISING CAMPAIGNS
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class Campaign(models.Model):

    name = models.CharField(max_length=40, blank=False,
        help_text="Short name of the campaign.")

    is_active = models.BooleanField(default=True,
        help_text="Whether or not this campaign is currently being pursued.")

    target_amount = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The total amount that needs to be collected in donations.")

    account = models.ForeignKey(Account, null=False, blank=False,
        on_delete=models.PROTECT,  # Don't allow deletion of account if campaign still exists.
        help_text="The account used by this campaign.")

    description = models.TextField(max_length=1024,
        help_text="A description of the campaign and why people should donate to it.")

    def clean(self):
        super().clean()

        if self.account.category is not Account.CAT_REVENUE:
             raise ValidationError(_("Account chosen must have category REVENUE."))

        if self.account.type is not Account.TYPE_CREDIT:
            raise ValidationError(_("Account chosen must have type CREDIT."))

    def __str__(self):
        return self.name


class CampaignNote(Note):

    is_public = models.BooleanField(default=False,
        help_text="Should this note be visible to the public as a campaign update?")

    campaign = models.ForeignKey(Campaign,
        on_delete=models.CASCADE,  # No point in keeping the update if the campaign is deleted.
        help_text="The campaign to which this public update applies.")


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# PHYSICAL (NOT MONETARY) DONATIONS
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class Donation(models.Model):

    donation_date = models.DateField(null=False, blank=False, default=date.today,
        help_text="The date on which the donation was made. Best guess if exact date not known.")

    donator_acct = models.ForeignKey(User, null=True, blank=True,
        on_delete=models.SET_NULL,  # Keep the note even if the user is deleted.
        help_text="It's preferable, but not necessary, to refer to the donator's account.")

    donator_name = models.CharField(max_length=40, blank=True,
        help_text="Name of person who made the donation. Not necessary if account is linked.")

    donator_email = models.EmailField(max_length=40, blank=True,
        help_text="Email address of person who made the donation.")

    # send_receipt will eventually be obsoleted by modelmailer app. Remove at that time.
    send_receipt = models.BooleanField(default=True,
        help_text="(Re)send a receipt to the donor. Note: Will send at night.")

    def __str__(self):
        name = "Anonymous"
        if len(str(self.donator_name)) > 0: name = self.donator_name
        elif self.donator_acct is not None: name = str(self.donator_acct)
        elif len(str(self.donator_email)) > 0: name = self.donator_email
        return "{} on {}".format(name, self.donation_date)

    def clean(self):
        super().clean()

        if self.send_receipt:
            if self.donator_acct is None:
                if self.donator_email=="":
                    raise ValidationError(_("No email address for receipt. Link to acct or provide donator email."))
            else:  # donator acct is specified
                if self.donator_acct.email=="" and self.donator_email=="":
                    raise ValidationError(_("No email address for receipt. Please fill the 'donator email' field."))

    def dbcheck(self):
        if len(self.donateditem_set.all()) < 1:
            raise ValidationError(_("Every phyisical donation must include at least one line item."))

    class Meta:
        verbose_name = "Physical donation"


class DonationNote(Note):

    donation = models.ForeignKey(Donation,
        on_delete=models.CASCADE,  # No point in keeping the note if the donation is deleted.
        help_text="The donation to which this note applies.")


class DonatedItem(models.Model):

    donation = models.ForeignKey(Donation, null=False, blank=False,
        on_delete=models.CASCADE,  # Line items are parts of the donation so delete them.
        help_text="The donation that includes this line item.")

    value = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The value of the item donated.")

    description = models.TextField(max_length=1024,
        help_text="A description of the item donated.")

    def __str__(self):
        return self.description[:40]


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# EXPENSE CLAIMS
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

@register_journaler()
class ExpenseClaim(Journaler):

    claimant = models.ForeignKey(User, null=True, blank=True,
        on_delete=models.SET_NULL,  # Keep the claim for accounting purposes, even if the user is deleted.
        help_text="The member who wrote this note.")

    amount = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The dollar amount for the entire claim.")

    when_submitted = models.DateField(null=True, blank=True, default=None,
        help_text="The date on which the claim was most recently (re)submitted for reimbursement.")

    submit = models.BooleanField(default=False,
        help_text="(Re)submit the claim for processing and reimbursement.")

    def reimbursed(self) -> Decimal:
        """
        :return: The sum total of all reimbursements.
        """
        total = Decimal(0.0)
        for ref in self.expenseclaimreference_set.all():
            if ref.portion is not None:
                total += ref.portion
            else:
                total += self.amount
        return total

    def remaining(self) -> Decimal:
        return self.amount - self.reimbursed()

    def status_str(self) -> str:
        if self.remaining() == Decimal(0):
            return "closed"
        if self.when_submitted is not None:
            return "submitted"
        if self.remaining() > Decimal(0):
            return "open"
        return "?"

    def checksum(self) -> Decimal:
        """
        :return: The sum total of all expense line items. Should match self.amount.
        """
        total = Decimal(0.0)
        for lineitem in self.expenselineitem_set.all():
            total += lineitem.amount
        return total

    # def is_reimbursed(self):
    #     """
    #     :return: True if claim has been reimbursed
    #     """
    #     return len(self.expenseclaimreference_set.all()) > 0
    # is_reimbursed.boolean = True

    def __str__(self):
        return "${} for {}".format(self.amount, self.claimant)

    def dbcheck(self):
        if  self.amount != self.checksum():
            raise ValidationError(_("Total of line items must match amount of claim."))

    def create_journalentry(self):

        # self.journal_entry = JournalEntry.objects.create(
        #     when=self.invoice_date
        # )
        # ar = Account.objects.get(name="Accounts Payable")  # TODO: Acct name can't be hard-coded?
        # JournalEntryLineItem.objects.create(
        #     journal_entry=self.journal_entry,
        #     account=ar,
        #     action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
        #     amount=self.amount
        # )
        """
        Unfortunately, due to the way that Expense Claims were misused as a sort of
        account in themselves, I'm unable to make sensible journale entries out of them.
        Instead, a journal entry will be made for each individual line item. This will
        date the transaction at the time of the purchase which is EARLIER than the date
        on which the claim was made, but it's close enough and will have to do.
        """
        self.create_lineitems_for(
            JournalEntry(id=-1, source_url=self.get_absolute_url()),
        )


class ExpenseClaimNote(Note):

    claim = models.ForeignKey(ExpenseClaim,
        on_delete=models.CASCADE,  # No point in keeping the note if the claim is gone.
        help_text="The claim to which the note pertains.")


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# EXPENSE TRANSACTION
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

@register_journaler()
class ExpenseTransaction(Journaler):

    payment_date = models.DateField(null=True, blank=True, default=None,
        help_text="The date on which the expense was paid (use bank statement date). Blank if not yet paid or statement not yet received. Best guess if paid but exact date not known.")

    recipient_acct = models.ForeignKey(User, null=True, blank=True, default=None,
        on_delete=models.SET_NULL,  # Keep the transaction even if the user is deleted.
        help_text="If payment was made to a user, speicfy them here.",
        verbose_name="User acct paid")

    recipient_entity = models.ForeignKey(Entity, null=True, blank=True, default=None,
        on_delete=models.SET_NULL,
        help_text="If some outside person/org was paid, specify them here.",
        verbose_name="Entity acct paid")

    # TODO: Once recipient_name and recipient_email data is moved to entities, these two fields should be removed.
    recipient_name = models.CharField(max_length=40, blank=True,
        help_text="Name of person/org paid. Not req'd if an acct was linked, above.",
        verbose_name="Name paid")
    recipient_email = models.EmailField(max_length=40, blank=True,
        help_text="Optional, sometimes useful ",
        verbose_name="Optional email")

    amount_paid = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The dollar amount of the payment.")

    PAID_BY_CASH   = "$"
    PAID_BY_CHECK  = "C"
    PAID_BY_XFER   = "X"  # Electronic transfer
    PAID_BY_CHOICES = [
        (PAID_BY_CASH,  "Cash"),
        (PAID_BY_CHECK, "Check"),
        (PAID_BY_XFER,  "Electronic"),
    ]
    payment_method = models.CharField(max_length=1, choices=PAID_BY_CHOICES,
        null=False, blank=False, default=PAID_BY_CASH,
        help_text="The payment method used.")
    payment_method.verbose_name = "Method"

    method_detail = models.CharField(max_length=40, blank=True,
        help_text="Optional detail specific to the payment method. Check# for check payments.")
    method_detail.verbose_name = "Detail"

    def payment_method_verbose(self):
        return dict(ExpenseTransaction.PAID_BY_CHOICES)[self.payment_method]

    def clean(self):
        super().clean()

        recip_spec_count = 0
        recip_spec_count += int(self.recipient_acct is not None)
        recip_spec_count += int(self.recipient_entity is not None)
        recip_spec_count += int(self.recipient_name > "")
        if recip_spec_count != 1:
            raise ValidationError(_("Recipient must be specified as EXACTLY ONE of user acct, entity acct, or name/email."))

        if self.payment_method == self.PAID_BY_CHECK \
          and self.method_detail > "" and not self.method_detail.isnumeric():
            raise ValidationError(_("Detail for check payments should only be the bare check number without # or other text."))

        if self.payment_method == self.PAID_BY_CASH and self.method_detail > "":
            raise ValidationError(_("Cash payments shouldn't have detail. Cash is cash."))

    def checksum(self) -> Decimal:
        """
        :return: The sum total of all line items. Should match self.amount_paid.
        """
        total = Decimal(0.0)
        for lineitem in self.expenselineitem_set.all():
            total += lineitem.amount
        for claimref in self.expenseclaimreference_set.all():
            total += claimref.portion if claimref.portion is not None else claimref.claim.amount
        return total

    def dbcheck(self):
        if  self.amount_paid != self.checksum():
            raise ValidationError(_("Total of line items must match amount of transaction."))

    def __str__(self):
        return "${} by {}".format(self.amount_paid, self.payment_method_verbose())

    def create_journalentry(self):
        # Child models will also contribute to this journal entry but that's handled by "generatejournal"
        je = JournalEntry(
            when=self.payment_date,
            source_url=self.get_absolute_url()
        )
        je.prebatch(JournalEntryLineItem(
            account=ACCT_ASSET_CASH,
            action=JournalEntryLineItem.ACTION_BALANCE_DECREASE,
            amount=self.amount_paid
        ))
        self.create_lineitems_for(je)
        Journaler.batch(je)


class ExpenseClaimReference(models.Model, JournalLiner):

    exp = models.ForeignKey(ExpenseTransaction, null=False, blank=False,
        on_delete=models.CASCADE,  # Delete this relation if the expense transaction is deleted.
        help_text="The expense transaction that pays the claim.")

    # I wanted the following to be OneToOne but there is at least one case of multiple partial
    # reimbursements for a single claim.
    claim = models.ForeignKey(ExpenseClaim, null=False, blank=False,
        on_delete=models.CASCADE,  # Delete this relation if the claim is deleted.
        help_text="The claim that is paid by the expense transaction.")

    portion = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, default=None,
        help_text="Leave blank unless you're only paying a portion of the claim.")

    def create_journalentry_lineitems(self, je: JournalEntry):

        amount = self.claim.amount

        if self.portion is not None:
            amount = self.portion

        je.prebatch(JournalEntryLineItem(
            account=ACCT_LIABILITY_PAYABLE,
            action=JournalEntryLineItem.ACTION_BALANCE_DECREASE,
            amount=amount,
        ))


class ExpenseLineItem(models.Model, JournalLiner):

    # An expense line item can appear in an ExpenseClaim or in an ExpenseTransaction

    claim = models.ForeignKey(ExpenseClaim, null=True, blank=True,
        on_delete=models.CASCADE,  # Line items are parts of the larger claim, so delete if claim is deleted.
        help_text="The claim on which this line item appears.")

    exp = models.ForeignKey(ExpenseTransaction, null=True, blank=True,
        on_delete=models.CASCADE,  # Line items are parts of the larger transaction, so delete if transaction is deleted.
        help_text="The expense transaction on which this line item appears.")

    description = models.CharField(max_length=80, blank=False,
        help_text="A brief description of this line item.")

    expense_date = models.DateField(null=False, blank=False,
        help_text="The date on which the expense was incurred.")

    amount = models.DecimalField(max_digits=6, decimal_places=2, null=False, blank=False,
        help_text="The dollar amount for this line item.")

    account = models.ForeignKey(Account, null=False, blank=False,
        on_delete=models.CASCADE,  # Line items are parts of the larger claim, so delete if claim is deleted.
        help_text="The account against which this line item is claimed, e.g. 'Wood Shop', '3D Printers'.")

    receipt_num = models.IntegerField(null=True, blank=True,
        help_text="The receipt number assigned by the treasurer and written on the receipt.")

    approved_by = models.ForeignKey(User, null=True, blank=True, default=None,
        on_delete=models.SET_NULL,  # If user is deleted, just null this out.
        help_text="Usually the shop/account manager. Leave blank if not yet approved.")

    def __str__(self):
        return "${} on {}".format(self.amount, self.expense_date)

    def clean(self):
        super().clean()

        if self.account.category not in [Account.CAT_EXPENSE, Account.CAT_ASSET]:
            raise ValidationError(_("Account chosen must have category EXPENSE or ASSET."))

    def dbcheck(self):
        # Relationships can't be checked in clean but can be checked later in a "db check" operation.
        if self.claim is None and self.exp is None:
            raise ValidationError(_("Expense line item must be part of a claim or transaction."))

    def create_journalentry_lineitems(self, je: JournalEntry):
        # Note: Sometimes entry will be real and sometimes it won't. This is intentional if undesirable.
        # When entry has id > 0, this line item is part of an ExpenseTransaction.
        # When entry has id == -1, this line item is part of an ExpenseClaim but journal entries are not
        # being created for ExpenseClaims because they were misused. See comments in ExpenseClaim.
        # Every line item associated with an ExpenseClaim will get its own JournalEntry, created here.

        if je.id == -1:

            je2 = JournalEntry(
                when=self.expense_date,
                source_url=je.source_url  # The fake je has source_url specified.
            )

            je2.prebatch(JournalEntryLineItem(
                account=ACCT_LIABILITY_PAYABLE,
                action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
                amount=self.amount,
            ))

        else:
            je2 = je

        je2.prebatch(JournalEntryLineItem(
            account=self.account,
            action=JournalEntryLineItem.ACTION_BALANCE_INCREASE,
            amount=self.amount,
        ))
        if je.id == -1:
            Journaler.batch(je2)


class ExpenseTransactionNote(Note):

    exp = models.ForeignKey(ExpenseTransaction,
        on_delete=models.CASCADE,  # No point in keeping the note if the transaction is gone.
        help_text="The expense transaction to which the note pertains.")


class PayableInvoiceReference(models.Model, JournalLiner):

    exp = models.ForeignKey(ExpenseTransaction, null=False, blank=False,
        on_delete=models.CASCADE,  # Delete this relation if the expense transaction is deleted.
        help_text="The expense transaction by which we pay the invoice.")

    # I wanted the following to be OneToOne but there might be multiple partial payments
    # toward a single invoice. I.e. I'm paralleling the ExpenseClaimReference case.
    invoice = models.ForeignKey(PayableInvoice, null=False, blank=False,
        on_delete=models.CASCADE,  # Delete this relation if the invoice is deleted.
        help_text="The invoice that is paid by the expense transaction.")
    # 'not_part_of', below, indicates that this Reference is not part of the referenced Invoice.
    invoice.is_not_parent = True

    portion = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, default=None,
        help_text="Leave blank unless we're only paying a portion of the invoice.")

    def create_journalentry_lineitems(self, je: JournalEntry):

        amount = self.invoice.amount

        if self.portion is not None:
            amount = self.portion

        je.prebatch(JournalEntryLineItem(
            account=ACCT_LIABILITY_PAYABLE,
            action=JournalEntryLineItem.ACTION_BALANCE_DECREASE,
            amount=amount,
        ))
