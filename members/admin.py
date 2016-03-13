from django.contrib import admin
from members.models import *
from books.admin import Sellable
from django.utils.translation import ugettext_lazy as _
from reversion.admin import VersionAdmin


@admin.register(Tag)
class TagAdmin(VersionAdmin):
    fields = ['name','meaning']


@admin.register(Tagging)
class TaggingAdmin(VersionAdmin):

    def members_username(self, object):
        return object.tagged_member.username
    members_username.admin_order_field = 'tagged_member__auth_user__username'
    raw_id_fields = ['tagged_member', 'authorizing_member']
    list_display = ['pk', 'tagged_member', 'members_username', 'tag', 'can_tag', 'date_tagged', 'authorizing_member']
    search_fields = [
        '^tagged_member__auth_user__first_name',
        '^tagged_member__auth_user__last_name',
        'tag__name',
        '^tagged_member__auth_user__username',
    ]


@admin.register(VisitEvent)
class VisitEventAdmin(admin.ModelAdmin):  # No need to version events.
    ordering = ['-when']
    list_display = ['pk', 'when', 'who', 'event_type', 'method', 'sync1']
    readonly_fields = ['when', 'who', 'event_type', 'method', 'sync1']
    search_fields = [
        '^who__auth_user__first_name',
        '^who__auth_user__last_name',
        '^who__auth_user__username',
    ]
    list_filter = ['when']
    date_hierarchy = 'when'


class MemberTypeFilter(admin.SimpleListFilter):
    title = "Worker Type"
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return (
            ('worktrade', _('Work-Trader')),
            ('intern', _('Intern')),
            ('scholar', _('Scholarship')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'worktrade': return queryset.filter(tags__name="Work-Trader")
        if self.value() == 'intern':    return queryset.filter(tags__name="Intern")
        if self.value() == 'scholar':   return queryset.filter(tags__name="Scholarship")


@admin.register(Member)
class MemberAdmin(VersionAdmin):

    list_display = ['pk', '__str__', 'auth_user', 'membership_card_when', 'membership_card_md5']

    search_fields = [
        '^auth_user__first_name',
        '^auth_user__last_name',
        '^auth_user__username',
    ]

    list_display_links = ['pk', '__str__']

    list_filter = [MemberTypeFilter]


PAYMENT_METHOD_CODE2STR = {code: str for (code, str) in PaidMembership.PAID_BY_CHOICES}
MEMBERSHIP_TYPE_CODE2STR = {code: str for (code, str) in PaidMembership.MEMBERSHIP_TYPE_CHOICES}


class PaymentLinkedFilter(admin.SimpleListFilter):
    title = "Linked"
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return (
            ('yes', _('Yes')),
            ('no', _('No')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes': return queryset.filter(member__isnull=False)
        if self.value() == 'no':  return queryset.filter(member__isnull=True)


@admin.register(PaidMembership)
class PaidMembershipAdmin(admin.ModelAdmin):  # Not versioning this since it will be deleted soon.

    ordering = ['-start_date']
    date_hierarchy = 'start_date'
    list_filter = [
        PaymentLinkedFilter,
        'payment_method',
        'membership_type',
        'protected',
    ]

    def fam_fmt(self,obj): return obj.family_count
    fam_fmt.admin_order_field = 'family_count'
    fam_fmt.short_description = 'fam'

    def paid_fmt(self,obj): return obj.paid_by_member
    paid_fmt.admin_order_field = 'paid_by_member'
    paid_fmt.short_description = 'paid'

    def fee_fmt(self,obj): return obj.processing_fee
    fee_fmt.admin_order_field = 'processing_fee'
    fee_fmt.short_description = 'fee'

    def type_fmt(self,obj): return MEMBERSHIP_TYPE_CODE2STR[obj.membership_type]
    type_fmt.admin_order_field = 'membership_type'
    type_fmt.short_description = 'type'

    def when_fmt(self,obj): return obj.payment_date
    when_fmt.admin_order_field = 'payment_date'
    when_fmt.short_description = 'when'

    def how_fmt(self,obj): return PAYMENT_METHOD_CODE2STR[obj.payment_method]
    how_fmt.admin_order_field = 'payment_method'
    how_fmt.short_description = 'how'

    list_display = [
        'pk',
        'member',
        'type_fmt',
        'fam_fmt',
        'start_date',
        'end_date',

        'payer_name',
        'payer_email',
        'paid_fmt',
        'fee_fmt',
        'when_fmt',
        'how_fmt',
    ]

    readonly_fields = ['ctrlid']

    fieldsets = [
        ('Membership Details', {'fields': [
            'member',
            'membership_type',
            'family_count',
            'start_date',
            'end_date',
        ]}),
        ('Payment Details', {'fields': [
            'payer_name',
            'payer_email',
            'payer_notes',
            'paid_by_member',
            'processing_fee',
            'payment_date',
            'payment_method',
        ]}),
        ('Other', {'fields': [
            'ctrlid',
            'protected',
        ]}),
    ]

    raw_id_fields = ['member']
    search_fields = [
        '^member__auth_user__first_name',
        '^member__auth_user__last_name',
        '^member__auth_user__username',
        'payer_name',
        'payer_email',
    ]


# @admin.register(PaymentAKA)
# class MemberAKAAdmin(VersionAdmin):
#     list_display = ['pk', 'member', 'aka']
#     raw_id_fields = ['member']


@admin.register(PaidMembershipNudge)
class PaidMembershipNudgeAdmin(admin.ModelAdmin):  # No need to version these
    list_display = ['pk', 'member', 'when']
    raw_id_fields = ['member']
    ordering = ['-when']


@admin.register(MemberLogin)
class MemberLogin(VersionAdmin):
    list_display = ['pk', 'member', 'when', 'ip']
    raw_id_fields = ['member']
    ordering = ['-when']


@admin.register(MembershipGiftCard)
class MembershipGiftCardAdmin(VersionAdmin):

    def sold(self, obj):
        ref = obj.membershipgiftcardreference
        if ref is None: return None
        return ref.sale.sale_date

    def created(self, obj):
        return obj.date_created

    def redeemed(self, obj):
        redemp = obj.membershipgiftcardredemption
        if redemp is None: return None
        return redemp.redemption_date

    list_display = [
        'pk',
        'redemption_code',
        'price',
        'month_duration',
        'created',
        'sold',
        'redeemed',
    ]
    search_fields = [
        'redemption_code',
    ]
    list_display_links = ['pk', 'redemption_code']
    list_filter = ['month_duration', 'price']
    ordering = ['redemption_code']


# This is an Inline for MembershipGiftCardRedemptionAdmin
class MembershipInline(admin.StackedInline):
    model = Membership
    extra = 0
    fields = [
        'member',
        'membership_type',
        'family_count',
        ('start_date', 'end_date'),
    ]
    raw_id_fields = ['member']


@admin.register(MembershipGiftCardRedemption)
class MembershipGiftCardRedemptionAdmin(VersionAdmin):
    def members(self, obj):
        return ",".join([str(mli.member) for mli in obj.membership_set.all()])

    list_display = ['pk', 'members', 'card']
    search_fields = ['card__redemption_code']
    inlines = [
        MembershipInline,
    ]
    raw_id_fields = ['card']


@admin.register(Membership)
class MembershipAdmin(VersionAdmin):
    ordering = ['-start_date']
    date_hierarchy = 'start_date'
    list_filter = [
        'membership_type',
        'protected',
    ]

    def fam_fmt(self,obj): return obj.family_count
    fam_fmt.admin_order_field = 'family_count'
    fam_fmt.short_description = 'fam'

    def type_fmt(self,obj): return MEMBERSHIP_TYPE_CODE2STR[obj.membership_type]
    type_fmt.admin_order_field = 'membership_type'
    type_fmt.short_description = 'type'

    def src_fmt(self,obj):
        if obj.sale is not None: return "{} sale to {}".format(obj.sale.sale_date,obj.sale.payer_name)
        if obj.redemption is not None: return "Gift card "+obj.redemption.card.redemption_code
        if obj.group is not None: return "Member of {} group".format(obj.group.group_tag)
        else: return None
    src_fmt.short_description = 'source'

    list_display = [
        'pk',
        'member',
        'type_fmt',
        'fam_fmt',
        'start_date',
        'end_date',
        'src_fmt',
    ]

    fields = [
        'member',
        'membership_type',
        'family_count',
        ('start_date', 'end_date'),
        'protected',
        'ctrlid',
    ]

    readonly_fields = ['ctrlid']
    raw_id_fields = ['member']

    search_fields = [
        '^member__auth_user__first_name',
        '^member__auth_user__last_name',
        '^member__auth_user__username',
        'sale__payer_name',
        'sale__payer_email',
    ]


@admin.register(DiscoveryMethod)
class DiscoveryMethodAdmin(VersionAdmin):
    list_display = ['pk', 'order', 'name']
    ordering = ['order']


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# Line-Item Inlines for SaleAdmin in Books app.
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

@Sellable(MembershipGiftCardReference)
class MembershipGiftCardLineItem(admin.StackedInline):
    fields = [
        'sale_price',
        'card',
    ]
    extra = 0
    raw_id_fields = ['card']


@Sellable(Membership)
class MembershipLineItem(admin.StackedInline):
    extra = 0
    fields = [
        'sale_price',
        'member',
        'membership_type',
        'family_count',
        ('start_date', 'end_date'),
    ]
    raw_id_fields = ['member']


@Sellable(GroupMembership)
class GroupMembershipLineItem(admin.StackedInline):
    extra = 0
    fields = [
        'sale_price',
        'group_tag',
        ('start_date', 'end_date'),
        'max_members',
    ]


