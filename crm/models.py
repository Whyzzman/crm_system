from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json
import math
from decimal import Decimal

class Client(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True, help_text="Email клиента для уведомлений")
    address = models.TextField()
    latitude = models.FloatField(null=True, blank=True, help_text="Широта клієнта")
    longitude = models.FloatField(null=True, blank=True, help_text="Довгота клієнта")

    def __str__(self):
        return self.name

class Courier(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True, help_text="Email курьера для уведомлений")
    available = models.BooleanField(default=True)
    vehicle_type = models.CharField(max_length=50, choices=[
        ('bike', 'Велосипед'),
        ('motorcycle', 'Мотоцикл'),
        ('car', 'Автомобіль'),
        ('van', 'Фургон')
    ], default='bike')
    current_latitude = models.FloatField(null=True, blank=True, help_text="Поточна широта")
    current_longitude = models.FloatField(null=True, blank=True, help_text="Поточна довгота")
    last_location_update = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def is_location_fresh(self):
        """Check if courier's location is updated within last 5 minutes"""
        if not self.last_location_update:
            return False
        return timezone.now() - self.last_location_update < timedelta(minutes=5)

class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Нове'),
        ('assigned', 'Призначено'),
        ('picked_up', 'Забрано'),
        ('in_transit', 'В дорозі'),
        ('delivered', 'Доставлено'),
        ('cancelled', 'Скасовано')
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Низький'),
        ('normal', 'Звичайний'),
        ('high', 'Високий'),
        ('urgent', 'Терміновий')
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    courier = models.ForeignKey(Courier, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    address = models.CharField(max_length=255, default="Невідома адреса")
    latitude = models.FloatField(null=True, blank=True, help_text="Широта доставки")
    longitude = models.FloatField(null=True, blank=True, help_text="Довгота доставки")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    actual_delivery_time = models.DateTimeField(null=True, blank=True)
    delivery_notes = models.TextField(blank=True, help_text="Особливі інструкції доставки")
    
    # Pricing fields
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Базова ціна доставки")
    additional_fees = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Додаткові платежі (терміново, вага тощо)")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Сума знижки")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Кінцева ціна")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} - {self.client.name}"

    @property
    def is_overdue(self):
        """Check if delivery is overdue"""
        if not self.estimated_delivery_time:
            return False
        return timezone.now() > self.estimated_delivery_time and self.status != 'delivered'
    
    @property
    def is_paid(self):
        """Check if order is paid"""
        try:
            return self.payment.status == 'completed'
        except (Payment.DoesNotExist, AttributeError):
            return False
    
    @property
    def payment_status_display(self):
        """Get human-readable payment status"""
        try:
            return self.payment.get_status_display()
        except (Payment.DoesNotExist, AttributeError):
            return "Не створено"
    
    def calculate_total_price(self):
        """Calculate total order price"""
        total = self.base_price + self.additional_fees - self.discount
        self.total_price = max(total, Decimal('0.00'))
        return self.total_price
    
    def create_payment(self, method='cash'):
        """Create payment for this order"""
        if hasattr(self, 'payment'):
            return self.payment
        
        # Calculate total price if not set
        if self.total_price == Decimal('0.00'):
            self.calculate_total_price()
            self.save()
        
        payment = Payment.objects.create(
            order=self,
            method=method,
            amount=self.total_price
        )
        return payment

class CourierLocation(models.Model):
    """Track courier's location history for GPS tracking"""
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='location_history')
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy = models.FloatField(null=True, blank=True, help_text="Точність GPS в метрах")
    speed = models.FloatField(null=True, blank=True, help_text="Швидкість в км/г")
    bearing = models.FloatField(null=True, blank=True, help_text="Напрямок в градусах")
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['courier', '-timestamp']),
        ]

class DeliveryRoute(models.Model):
    """Optimized delivery routes for couriers"""
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, help_text="Назва маршруту або ідентифікатор")
    orders = models.ManyToManyField(Order, through='RouteOrder')
    status = models.CharField(max_length=20, choices=[
        ('planned', 'Заплановано'),
        ('active', 'Активний'),
        ('completed', 'Завершено'),
        ('cancelled', 'Скасовано')
    ], default='planned')
    total_distance = models.FloatField(null=True, blank=True, help_text="Загальна відстань маршруту в км")
    estimated_duration = models.DurationField(null=True, blank=True)
    actual_duration = models.DurationField(null=True, blank=True)
    route_data = models.JSONField(null=True, blank=True, help_text="Оптимізовані координати маршруту")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Route {self.name} - {self.courier.name}"

    @property
    def order_count(self):
        return self.orders.count()
    
    @property
    def estimated_duration_formatted(self):
        """Форматує estimated_duration до години:хвилини без секунд"""
        if not self.estimated_duration:
            return "N/A"
        
        total_seconds = int(self.estimated_duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}"
        else:
            return f"0:{minutes:02d}"

class RouteOrder(models.Model):
    """Through model for order sequence in delivery route"""
    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField(help_text="Порядок доставки в маршруті")
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['sequence']
        unique_together = ['route', 'sequence']

class DeliveryZone(models.Model):
    """Delivery zones for better route planning"""
    name = models.CharField(max_length=100)
    polygon_data = models.JSONField(help_text="Дані полігону GeoJSON для зони")
    base_delivery_time = models.DurationField(default=timedelta(minutes=30))
    traffic_multiplier = models.FloatField(default=1.0, help_text="Множник затримки через трафік")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class TrafficData(models.Model):
    """Store traffic data for delivery time calculations"""
    zone = models.ForeignKey(DeliveryZone, on_delete=models.CASCADE)
    hour = models.IntegerField(help_text="Година дня (0-23)")
    day_of_week = models.IntegerField(help_text="День тижня (0=Понеділок, 6=Неділя)")
    average_delay_factor = models.FloatField(default=1.0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['zone', 'hour', 'day_of_week']

class Payment(models.Model):
    """Payment tracking for orders"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Готівка'),
        ('card', 'Банківська картка'),
        ('online', 'Онлайн оплата'),
        ('bank_transfer', 'Банківський переказ'),
        ('postpaid', 'Післяплата'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Очікується'),
        ('processing', 'В обробці'),
        ('completed', 'Завершено'),
        ('failed', 'Помилка'),
        ('refunded', 'Повернено'),
        ('cancelled', 'Скасовано'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    status = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Cash payment fields
    cash_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Сума отримана готівкою")
    change_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Здача до повернення")
    
    # Online payment fields
    transaction_id = models.CharField(max_length=100, null=True, blank=True, help_text="Зовнішній ID транзакції платежу")
    gateway_response = models.JSONField(null=True, blank=True, help_text="Дані відповіді платіжного шлюзу")
    
    # Metadata
    payment_notes = models.TextField(blank=True, help_text="Додаткові примітки платежу")
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="Користувач, який обробив платіж")
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.id} - Order {self.order.id} ({self.get_method_display()})"
    
    @property
    def is_cash_payment(self):
        return self.method == 'cash'
    
    @property
    def needs_change(self):
        """Check if change is needed for cash payment"""
        if not self.is_cash_payment or not self.cash_received:
            return False
        return self.cash_received > self.amount
    
    def calculate_change(self):
        """Calculate change amount for cash payment"""
        if not self.is_cash_payment or not self.cash_received:
            return Decimal('0.00')
        return max(self.cash_received - self.amount, Decimal('0.00'))
    
    def process_payment(self, user=None):
        """Mark payment as processed"""
        self.status = 'completed'
        self.processed_at = timezone.now()
        if user:
            self.processed_by = user
        if self.is_cash_payment and self.cash_received:
            self.change_amount = self.calculate_change()
        self.save()
    
    class Meta:
        ordering = ['-created_at']


class EmailNotificationSettings(models.Model):
    """Настройки email уведомлений"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_settings')
    
    # Настройки уведомлений для клиентов
    notify_order_created = models.BooleanField(default=True, verbose_name="Уведомления о создании заказа")
    notify_order_status_changed = models.BooleanField(default=True, verbose_name="Уведомления об изменении статуса")
    notify_payment_received = models.BooleanField(default=True, verbose_name="Уведомления о получении платежа")
    notify_delivery_assigned = models.BooleanField(default=True, verbose_name="Уведомления о назначении курьера")
    notify_delivery_completed = models.BooleanField(default=True, verbose_name="Уведомления о завершении доставки")
    
    # Настройки для менеджеров
    receive_new_order_notifications = models.BooleanField(default=True, verbose_name="Получать уведомления о новых заказах")
    receive_payment_notifications = models.BooleanField(default=True, verbose_name="Получать уведомления о платежах")
    
    # Настройки для курьеров
    receive_delivery_assignments = models.BooleanField(default=True, verbose_name="Получать уведомления о назначениях")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Настройки email уведомлений"
        verbose_name_plural = "Настройки email уведомлений"
    
    def __str__(self):
        return f"Email настройки для {self.user.username}"
