from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Order, Courier, Client, DeliveryRoute, DeliveryZone, Payment
from decimal import Decimal

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


# Form for creating and updating orders
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'client', 'product', 'quantity', 'address', 
            'courier', 'status', 'priority', 'delivery_notes',
            'latitude', 'longitude', 'base_price', 'additional_fees', 'discount'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'product': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введіть назву товару', 'required': True}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '1', 'required': True}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Введіть повну адресу доставки', 'required': True}),
            'courier': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'delivery_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Особливі інструкції для кур\'єра...'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '49.842957'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '24.031111'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00', 'required': True}),
            'additional_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00', 'value': '0'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00', 'value': '0'}),
        }


class CourierForm(forms.ModelForm):
    class Meta:
        model = Courier
        fields = [
            'name', 'phone', 'email', 'vehicle_type', 'available',
            'current_latitude', 'current_longitude'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'Email кур\'єра'}),
            'current_latitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Поточна Широта'}),
            'current_longitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Поточна Довгота'}),
        }


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'phone', 'email', 'address', 'latitude', 'longitude']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'Email клієнта'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'latitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Широта'}),
            'longitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Довгота'}),
        }


class RouteOptimizationForm(forms.Form):
    courier = forms.ModelChoiceField(
        queryset=Courier.objects.filter(available=True),
        empty_label="Оберіть кур'єра",
        required=True,
        error_messages={
            'required': 'Будь ласка, оберіть кур\'єра.',
            'invalid_choice': 'Будь ласка, оберіть дісного кур\'єра.'
        }
    )
    orders = forms.ModelMultipleChoiceField(
        queryset=Order.objects.filter(status__in=['new', 'assigned']),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        error_messages={
            'required': 'Будь ласка, оберіть хоча б одне замовлення.',
            'list': 'Будь ласка, оберіть хоча б одне замовлення.'
        }
    )
    route_name = forms.CharField(
        max_length=100,
        required=False,
        help_text="Залиште порожнім для автогенерації назви",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть назву маршруту або залиште порожнім для автогенерації'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        courier = cleaned_data.get('courier')
        orders = cleaned_data.get('orders')
        
        if not courier:
            raise forms.ValidationError("Будь ласка, оберіть кур'єра.")
        
        if not orders or len(orders) == 0:
            raise forms.ValidationError("Будь ласка, оберіть хоча б одне замовлення.")
        
        # Check if courier is available
        if not courier.available:
            raise forms.ValidationError("Обраний кур'єр недоступний.")
        
        # Check if orders are valid for assignment
        for order in orders:
            if order.status not in ['new', 'assigned']:
                raise forms.ValidationError(f"Замовлення №{order.id} не може бути призначено (статус: {order.get_status_display()})")
        
        return cleaned_data


class GPSLocationUpdateForm(forms.Form):
    courier_id = forms.IntegerField(widget=forms.HiddenInput())
    latitude = forms.FloatField()
    longitude = forms.FloatField()
    accuracy = forms.FloatField(required=False)
    speed = forms.FloatField(required=False, help_text="Швидкість в км/г")
    bearing = forms.FloatField(required=False, help_text="Напрямок в градусах")


class DeliveryZoneForm(forms.ModelForm):
    class Meta:
        model = DeliveryZone
        fields = ['name', 'base_delivery_time', 'traffic_multiplier', 'is_active']
        widgets = {
            'base_delivery_time': forms.TimeInput(attrs={'placeholder': 'ГГ:ММ:СС'}),
        }


class OrderFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'Всі')] + Order.STATUS_CHOICES,
        required=False
    )
    priority = forms.ChoiceField(
        choices=[('', 'Всі')] + Order.PRIORITY_CHOICES,
        required=False
    )
    courier = forms.ModelChoiceField(
        queryset=Courier.objects.all(),
        empty_label="Всі кур'єри",
        required=False
    )
    date_from = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    is_overdue = forms.BooleanField(required=False, label="Показати лише прострочені замовлення")


class PaymentForm(forms.ModelForm):
    """Form for creating and updating payments"""
    class Meta:
        model = Payment
        fields = ['method', 'amount', 'payment_notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'payment_notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Додаткові примітки щодо оплати...'}),
        }
    
    def __init__(self, *args, **kwargs):
        order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        if order:
            # Set default amount to order's total price
            self.fields['amount'].initial = order.total_price or order.calculate_total_price()


class CashPaymentForm(forms.ModelForm):
    """Specific form for cash payments with change calculation"""
    class Meta:
        model = Payment
        fields = ['amount', 'cash_received', 'payment_notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'readonly': True}),
            'cash_received': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'placeholder': 'Отримано готівки'}),
            'payment_notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Примітки...'}),
        }
    
    def __init__(self, *args, **kwargs):
        order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        if order:
            self.fields['amount'].initial = order.total_price or order.calculate_total_price()
        
        # Add change calculation field
        self.fields['calculated_change'] = forms.DecimalField(
            required=False,
            widget=forms.NumberInput(attrs={'readonly': True, 'placeholder': 'Здача буде розрахована'}),
            label='Здача'
        )
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        cash_received = cleaned_data.get('cash_received')
        
        if cash_received and amount:
            if cash_received < amount:
                raise forms.ValidationError('Отримана сума не може бути меншою за суму до оплати')
            
            # Calculate change
            cleaned_data['calculated_change'] = cash_received - amount
        
        return cleaned_data


class PaymentProcessForm(forms.Form):
    """Form for processing payments (marking as completed)"""
    payment_method = forms.ChoiceField(
        choices=Payment.PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect,
        label='Спосіб оплати'
    )
    
    # Cash payment fields
    cash_received = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
        label='Отримано готівки'
    )
    
    # Card/Online payment fields
    transaction_id = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'ID транзакції'}),
        label='ID транзакції'
    )
    
    payment_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Додаткові примітки...'}),
        label='Примітки'
    )
    
    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        if self.order:
            # Add order amount as context
            self.order_amount = self.order.total_price or self.order.calculate_total_price()
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        cash_received = cleaned_data.get('cash_received')
        
        if payment_method == 'cash':
            if not cash_received:
                raise forms.ValidationError('Для готівкової оплати необхідно вказати отриману суму')
            
            if self.order and cash_received < self.order_amount:
                raise forms.ValidationError(f'Отримана сума ({cash_received}) менша за суму замовлення ({self.order_amount})')
        
        return cleaned_data
