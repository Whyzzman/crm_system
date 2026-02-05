from django.contrib import admin
from .models import (
    Client, Courier, Order, CourierLocation, DeliveryRoute, 
    RouteOrder, DeliveryZone, TrafficData, Payment, EmailNotificationSettings
)

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'latitude', 'longitude']
    search_fields = ['name', 'phone', 'email']
    list_filter = ['latitude', 'longitude']

@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'vehicle_type', 'available', 'is_location_fresh']
    list_filter = ['vehicle_type', 'available']
    search_fields = ['name', 'phone', 'email']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'courier', 'status', 'priority', 'total_price', 'is_paid', 'created_at']
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['client__name', 'courier__name', 'product']
    date_hierarchy = 'created_at'

@admin.register(CourierLocation)
class CourierLocationAdmin(admin.ModelAdmin):
    list_display = ['courier', 'latitude', 'longitude', 'speed', 'timestamp']
    list_filter = ['courier', 'timestamp']
    date_hierarchy = 'timestamp'

class RouteOrderInline(admin.TabularInline):
    model = RouteOrder
    extra = 0

@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ['name', 'courier', 'status', 'order_count', 'total_distance', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'courier__name']
    inlines = [RouteOrderInline]

@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_delivery_time', 'traffic_multiplier', 'is_active']
    list_filter = ['is_active']

@admin.register(TrafficData)
class TrafficDataAdmin(admin.ModelAdmin):
    list_display = ['zone', 'hour', 'day_of_week', 'average_delay_factor', 'last_updated']
    list_filter = ['zone', 'hour', 'day_of_week']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'method', 'status', 'amount', 'created_at', 'processed_by']
    list_filter = ['method', 'status', 'created_at']
    search_fields = ['order__id', 'order__client__name', 'transaction_id']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at', 'processed_at']
    
    fieldsets = (
        ('Основна інформація', {
            'fields': ('order', 'method', 'status', 'amount')
        }),
        ('Готівкова оплата', {
            'fields': ('cash_received', 'change_amount'),
            'classes': ('collapse',)
        }),
        ('Безготівкова оплата', {
            'fields': ('transaction_id', 'gateway_response'),
            'classes': ('collapse',)
        }),
        ('Метадані', {
            'fields': ('payment_notes', 'processed_by', 'processed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmailNotificationSettings)
class EmailNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'notify_order_created', 'notify_order_status_changed', 
        'receive_new_order_notifications', 'updated_at'
    ]
    list_filter = [
        'notify_order_created', 'notify_order_status_changed', 
        'notify_payment_received', 'receive_new_order_notifications'
    ]
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Уведомления для клиентов', {
            'fields': (
                'notify_order_created', 'notify_order_status_changed',
                'notify_payment_received', 'notify_delivery_assigned',
                'notify_delivery_completed'
            )
        }),
        ('Уведомления для персонала', {
            'fields': (
                'receive_new_order_notifications', 'receive_payment_notifications',
                'receive_delivery_assignments'
            )
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )