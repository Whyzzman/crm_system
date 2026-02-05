from django.contrib import messages
from django.contrib.auth.models import User
from .forms import (
    UserRegisterForm,
    OrderForm,
    RouteOptimizationForm,
    PaymentForm,
    CashPaymentForm,
    PaymentProcessForm,
)
from django.shortcuts import render, redirect, get_object_or_404
from .models import (
    Order,
    Client,
    Courier,
    DeliveryRoute,
    RouteOrder,
    Payment,
)
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .logistics import LogisticsManager, RouteOptimizer, GeoCoder, DeliveryTimeCalculator
from .email_notifications import EmailNotificationService
from django.conf import settings
from django.utils.crypto import constant_time_compare
import json
import logging
import requests
import re

logger = logging.getLogger(__name__)


def _extract_api_key(request):
    """Extract API key from header or query params."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.lower().startswith('bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return request.headers.get('X-API-KEY') or request.GET.get('api_key')


def _is_authorized(request, expected_key):
    """Allow authenticated users or valid API key (optional in DEBUG)."""
    if request.user.is_authenticated:
        return True
    if not expected_key:
        return settings.DEBUG
    provided = _extract_api_key(request)
    return bool(provided) and constant_time_compare(provided, expected_key)


def index(request):
    return render(request, 'crm/index.html')


@login_required
def orders_list(request):
    """Перегляд замовлень з фільтрами та пошуком"""
    if request.user.is_superuser or request.user.is_staff:
        orders = Order.objects.select_related('client', 'courier', 'created_by').all()
    else:
        orders = Order.objects.select_related('client', 'courier', 'created_by').filter(created_by=request.user)

    # Фільтри
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    courier_filter = request.GET.get('courier')
    if courier_filter:
        orders = orders.filter(courier__id=courier_filter)

    couriers = Courier.objects.all()
    return render(request, 'crm/orders_list.html', {
        'orders': orders,
        'status_filter': status_filter,
        'courier_filter': courier_filter,
        'couriers': couriers,
    })


@login_required
@staff_member_required
def order_create(request):
    """Створення нового замовлення"""
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            # Автоматично розрахувати загальну ціну
            order.calculate_total_price()
            order.save()
            
            # Отправляем email уведомления о создании заказа
            try:
                EmailNotificationService.notify_order_created(order)
                logger.info(f"Email уведомления отправлены для заказа #{order.id}")
            except Exception as e:
                logger.error(f"Ошибка отправки email для заказа #{order.id}: {str(e)}")
            
            # Якщо є базова ціна, автоматично створити платіж
            if order.total_price > 0:
                payment = order.create_payment()
                messages.success(request, f'Замовлення #{order.id} успішно створено! Сума до оплати: {order.total_price} грн')
                return redirect('payment_quick', order_id=order.id)
            else:
                messages.success(request, f'Замовлення #{order.id} успішно створено!')
                return redirect('order_update', pk=order.id)
    else:
        form = OrderForm()
    return render(request, 'crm/order_form.html', {'form': form, 'title': 'Створити замовлення'})


@login_required
@staff_member_required
def order_update(request, pk):
    """Редагування замовлення"""
    order = get_object_or_404(Order, pk=pk)
    if not (request.user.is_superuser or request.user.is_staff or order.created_by == request.user):
        messages.error(request, "Ви не маєте прав редагувати це замовлення.")
        return redirect('orders_list')

    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            # Сохраняем старый статус для уведомлений
            old_status = order.status
            old_courier = order.courier
            
            order = form.save(commit=False)
            # Автоматично пересрахувати загальну ціну
            order.calculate_total_price()
            order.save()
            
            # Проверяем изменения и отправляем уведомления
            try:
                status_changed = old_status != order.status
                courier_changed = old_courier != order.courier and order.courier is not None

                # Уведомление об изменении статуса
                if status_changed:
                    EmailNotificationService.notify_order_status_changed(
                        order, old_status, order.get_status_display()
                    )
                    logger.info(f"Email уведомление об изменении статуса отправлено для заказа #{order.id}")

                # Уведомление о назначении курьера
                if courier_changed:
                    EmailNotificationService.notify_delivery_assigned(order, order.courier)
                    logger.info(f"Email уведомление о назначении курьера отправлено для заказа #{order.id}")
                
                # Уведомление о завершении доставки
                if order.status == 'delivered' and old_status != 'delivered':
                    EmailNotificationService.notify_delivery_completed(order)
                    logger.info(f"Email уведомление о завершении доставки отправлено для заказа #{order.id}")
                    
            except Exception as e:
                logger.error(f"Ошибка отправки email уведомлений для заказа #{order.id}: {str(e)}")
            
            # Оновити суму платежу, якщо він існує
            if hasattr(order, 'payment') and order.payment.status == 'pending':
                order.payment.amount = order.total_price
                order.payment.save()
                messages.success(request, f'Замовлення оновлено! Нова сума: {order.total_price} грн')
            else:
                messages.success(request, 'Замовлення оновлено!')
            
            return redirect('orders_list')
    else:
        form = OrderForm(instance=order)
    return render(request, 'crm/order_form.html', {'form': form, 'title': 'Редагувати замовлення'})


@login_required
@staff_member_required
def order_delete(request, pk):
    """Видалення замовлення"""
    order = get_object_or_404(Order, pk=pk)
    if not (request.user.is_superuser or request.user.is_staff or order.created_by == request.user):
        messages.error(request, "Ви не маєте прав видаляти це замовлення.")
        return redirect('orders_list')

    if request.method == 'POST':
        order.delete()
        messages.success(request, 'Замовлення видалено!')
        return redirect('orders_list')

    return render(request, 'crm/order_confirm_delete.html', {'order': order})


@login_required
def clients_list(request):
    """Список клієнтів з пошуком"""
    if request.user.is_superuser or request.user.is_staff:
        clients = Client.objects.all()
    else:
        clients = Client.objects.filter(order__created_by=request.user).distinct()

    search_query = request.GET.get('q')
    if search_query:
        clients = clients.filter(name__icontains=search_query)

    return render(request, 'crm/clients_list.html', {
        'clients': clients,
        'search_query': search_query,
    })


@login_required
def couriers_list(request):
    """Список кур’єрів з пошуком та фільтром"""
    if request.user.is_superuser or request.user.is_staff:
        couriers = Courier.objects.all()
    else:
        couriers = Courier.objects.filter(order__created_by=request.user).distinct()

    search_name = request.GET.get('q')
    if search_name:
        couriers = couriers.filter(name__icontains=search_name)

    availability = request.GET.get('available')
    if availability == '1':
        couriers = couriers.filter(available=True)
    elif availability == '0':
        couriers = couriers.filter(available=False)

    return render(request, 'crm/couriers_list.html', {
        'couriers': couriers,
        'search_name': search_name,
        'availability': availability,
    })


def register(request):
    """Реєстрація користувача"""
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Аккаунт створено для {username}! Ви можете увійти.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'crm/register.html', {'form': form})


@login_required
def profile(request):
    return render(request, 'crm/profile.html')


@login_required
def dashboard(request):
    """Розширений дашборд зі статистикою та KPI"""
    from django.db.models import Sum, Avg, Q
    from decimal import Decimal
    
    if request.user.is_superuser or request.user.is_staff:
        orders = Order.objects.all()
        payments = Payment.objects.all()
    else:
        orders = Order.objects.filter(created_by=request.user)
        payments = Payment.objects.filter(order__created_by=request.user)

    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    
    # KPI метрики
    total_orders = orders.count()
    orders_today = orders.filter(created_at__date=today).count()
    orders_this_month = orders.filter(created_at__date__gte=current_month_start).count()
    orders_last_month = orders.filter(
        created_at__date__gte=last_month_start,
        created_at__date__lt=current_month_start
    ).count()
    
    # Фінансові показники
    total_revenue = payments.filter(status='completed').aggregate(
        total=Sum('amount'))['total'] or Decimal('0.0')
    revenue_today = payments.filter(
        status='completed', 
        processed_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.0')
    revenue_this_month = payments.filter(
        status='completed',
        processed_at__date__gte=current_month_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.0')
    revenue_last_month = payments.filter(
        status='completed',
        processed_at__date__gte=last_month_start,
        processed_at__date__lt=current_month_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.0')
    
    # Середня сума замовлення
    avg_order_value = orders.filter(total_price__gt=0).aggregate(
        avg=Avg('total_price'))['avg'] or Decimal('0.0')
    
    # Округлення фінансових показників до десятих
    total_revenue = round(float(total_revenue), 1)
    revenue_today = round(float(revenue_today), 1)
    revenue_this_month = round(float(revenue_this_month), 1)
    revenue_last_month = round(float(revenue_last_month), 1)
    avg_order_value = round(float(avg_order_value), 1)
    
    # Статуси замовлень
    status_stats = {}
    for status_code, status_name in Order.STATUS_CHOICES:
        status_stats[status_code] = {
            'name': status_name,
            'count': orders.filter(status=status_code).count()
        }
    
    # Статистика оплат
    payment_stats = {}
    for status_code, status_name in Payment.PAYMENT_STATUS_CHOICES:
        payment_stats[status_code] = {
            'name': status_name,
            'count': payments.filter(status=status_code).count()
        }
    
    # Графік замовлень за тиждень
    labels_last_week = []
    orders_last_week = []
    revenue_last_week = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels_last_week.append(day.strftime('%a'))
        orders_last_week.append(orders.filter(created_at__date=day).count())
        day_revenue = payments.filter(
            status='completed',
            processed_at__date=day
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.0')
        revenue_last_week.append(round(float(day_revenue), 1))

    # ТОП кур'єри
    top_couriers_qs = (
        Courier.objects.filter(order__in=orders)
        .annotate(
            order_count=Count('order'),
            completed_orders=Count('order', filter=Q(order__status='delivered')),
            total_revenue=Sum('order__total_price', filter=Q(order__payment__status='completed'))
        )
        .order_by('-order_count')[:5]
    )
    top_couriers = [{
        'name': c.name,
        'order_count': c.order_count,
        'completed_orders': c.completed_orders or 0,
        'total_revenue': round(float(c.total_revenue or 0), 1),
        'success_rate': round((c.completed_orders or 0) / max(c.order_count, 1) * 100, 1)
    } for c in top_couriers_qs]

    # ТОП клієнти
    top_clients_qs = (
        Client.objects.filter(order__in=orders)
        .annotate(
            order_count=Count('order'),
            total_spent=Sum('order__total_price', filter=Q(order__payment__status='completed'))
        )
        .order_by('-total_spent')[:5]
    )
    top_clients = [{
        'name': c.name,
        'order_count': c.order_count,
        'total_spent': round(float(c.total_spent or 0), 1),
        'avg_order_value': round(float((c.total_spent or 0) / max(c.order_count, 1)), 1)
    } for c in top_clients_qs]
    
    # Порівняння з минулим місяцем
    orders_growth = 0
    revenue_growth = 0
    if orders_last_month > 0:
        orders_growth = round((orders_this_month - orders_last_month) / orders_last_month * 100, 1)
    if revenue_last_month > 0:
        revenue_growth = round(float((revenue_this_month - revenue_last_month) / revenue_last_month * 100), 1)

    context = {
        # KPI метрики
        'total_orders': total_orders,
        'orders_today': orders_today,
        'orders_this_month': orders_this_month,
        'orders_growth': orders_growth,
        
        # Фінансові показники
        'total_revenue': total_revenue,
        'revenue_today': revenue_today,
        'revenue_this_month': revenue_this_month,
        'revenue_growth': revenue_growth,
        'avg_order_value': avg_order_value,
        
        # Статистика
        'status_stats': status_stats,
        'payment_stats': payment_stats,
        'top_couriers': top_couriers,
        'top_clients': top_clients,
        
        # Графіки
        'labels_last_week': labels_last_week,
        'orders_last_week': orders_last_week,
        'revenue_last_week': revenue_last_week,
        
        # Додаткова інформація
        'total_clients': Client.objects.count(),
        'total_couriers': Courier.objects.count(),
        'active_couriers': Courier.objects.filter(available=True).count(),
    }
    return render(request, 'crm/dashboard.html', context)


# ===== LOGISTICS VIEWS =====

logistics_manager = LogisticsManager()

@login_required
@staff_member_required
def logistics_dashboard(request):
    """Logistics dashboard with route optimization and GPS tracking"""
    
    # Get active routes
    active_routes = DeliveryRoute.objects.filter(status='active').select_related('courier')
    
    # Get couriers with fresh GPS data
    active_couriers = Courier.objects.filter(
        available=True,
        current_latitude__isnull=False,
        current_longitude__isnull=False
    )
    
    # Get pending orders that need route optimization
    pending_orders = Order.objects.filter(
        status__in=['new', 'assigned']
    ).select_related('client', 'courier')
    
    # Get overdue deliveries
    overdue_orders = Order.objects.filter(
        status__in=['assigned', 'picked_up', 'in_transit'],
        estimated_delivery_time__lt=timezone.now()
    ).select_related('client', 'courier')
    
    context = {
        'active_routes': active_routes,
        'active_couriers': active_couriers,
        'pending_orders': pending_orders,
        'overdue_orders': overdue_orders,
        'total_active_routes': active_routes.count(),
        'total_active_couriers': active_couriers.count(),
        'total_pending_orders': pending_orders.count(),
        'total_overdue_orders': overdue_orders.count(),
    }
    
    return render(request, 'crm/logistics_dashboard.html', context)


@login_required
@staff_member_required
def route_optimization(request):
    """Route optimization interface"""
    
    if request.method == 'POST':
        form = RouteOptimizationForm(request.POST)
        if form.is_valid():
            courier = form.cleaned_data['courier']
            orders = form.cleaned_data['orders']
            route_name = form.cleaned_data['route_name']
            
            # Validate data before processing
            if not orders:
                messages.error(request, 'Будь ласка, оберіть хоча б одне замовлення.')
                return render(request, 'crm/route_optimization.html', {'form': form})
            
            if not courier:
                messages.error(request, 'Будь ласка, оберіть кур\'єра.')
                return render(request, 'crm/route_optimization.html', {'form': form})
            
            try:
                logger.info(f"Creating route for courier {courier.id} with {len(orders)} orders")
                
                route_optimizer = RouteOptimizer()
                route = route_optimizer.create_delivery_route(
                    courier=courier,
                    orders=list(orders),
                    name=route_name
                )
                
                logger.info(f"Route created successfully: {route.id}")
                
                # Update order statuses
                updated_count = 0
                for order in orders:
                    order.courier = courier
                    order.status = 'assigned'
                    order.save()
                    updated_count += 1
                
                logger.info(f"Updated {updated_count} orders with courier {courier.id}")
                
                messages.success(request, f'Маршрут "{route.name}" створено успішно з {len(orders)} замовленнями!')
                return redirect('route_detail', route_id=route.id)
                
            except Exception as e:
                logger.error(f"Route optimization error: {e}", exc_info=True)
                # Provide more user-friendly error message
                if "JSON serializable" in str(e):
                    messages.error(request, 'Помилка створення маршруту: Невірний формат даних. Спробуйте ще раз.')
                elif "database" in str(e).lower():
                    messages.error(request, 'Сталася помилка бази даних. Спробуйте ще раз.')
                else:
                    messages.error(request, f'Помилка створення маршруту: {str(e)[:100]}...')
    else:
        form = RouteOptimizationForm()
    
    return render(request, 'crm/route_optimization.html', {'form': form})


@login_required
def route_detail(request, route_id):
    """Route detail view with map visualization"""
    route = get_object_or_404(DeliveryRoute, id=route_id)
    
    # Check permissions
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Ви не маєте дозволу переглядати цей маршрут.")
        return redirect('logistics_dashboard')
    
    route_orders = RouteOrder.objects.filter(route=route).select_related('order__client').order_by('sequence')
    
    # Prepare map data
    map_data = {
        'route_coordinates': route.route_data.get('coordinates', []) if route.route_data else [],
        'orders': [
            {
                'id': ro.order.id,
                'sequence': ro.sequence,
                'client_name': ro.order.client.name,
                'address': ro.order.address,
                'latitude': ro.order.latitude,
                'longitude': ro.order.longitude,
                'status': ro.order.status,
                'priority': ro.order.priority,
                'estimated_arrival': ro.estimated_arrival.isoformat() if ro.estimated_arrival else None,
            }
            for ro in route_orders if ro.order.latitude and ro.order.longitude
        ]
    }
    
    context = {
        'route': route,
        'route_orders': route_orders,
        'map_data': json.dumps(map_data),
    }
    
    return render(request, 'crm/route_detail.html', context)


@login_required
@staff_member_required
def courier_tracking(request):
    """GPS tracking for all active couriers"""
    
    active_couriers = Courier.objects.filter(
        available=True,
        current_latitude__isnull=False,
        current_longitude__isnull=False
    )
    
    # Prepare tracking data
    tracking_data = []
    for courier in active_couriers:
        # Get recent location history
        recent_locations = logistics_manager.gps_tracker.get_courier_location_history(
            courier.id, hours=2
        )
        
        tracking_data.append({
            'courier': {
                'id': courier.id,
                'name': courier.name,
                'vehicle_type': courier.vehicle_type,
                'phone': courier.phone,
                'current_latitude': courier.current_latitude,
                'current_longitude': courier.current_longitude,
                'is_location_fresh': courier.is_location_fresh,
                'last_update': courier.last_location_update.isoformat() if courier.last_location_update else None,
            },
            'recent_locations': recent_locations[:10],  # Last 10 locations
        })
    
    context = {
        'tracking_data': json.dumps(tracking_data),
        'active_couriers': active_couriers,
    }
    
    return render(request, 'crm/courier_tracking.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def update_courier_location(request):
    """API endpoint for updating courier GPS location"""
    
    try:
        if not _is_authorized(request, getattr(settings, 'COURIER_LOCATION_API_KEY', None)):
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        data = json.loads(request.body)
        courier_id = data.get('courier_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        accuracy = data.get('accuracy')
        speed = data.get('speed')
        bearing = data.get('bearing')
        
        if courier_id is None or latitude is None or longitude is None:
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        # Validate coordinate ranges
        lat_val = float(latitude)
        lon_val = float(longitude)
        if not (-90 <= lat_val <= 90) or not (-180 <= lon_val <= 180):
            return JsonResponse({'error': 'Недійсні координати'}, status=400)
        
        success = logistics_manager.gps_tracker.update_courier_location(
            courier_id=int(courier_id),
            latitude=lat_val,
            longitude=lon_val,
            accuracy=float(accuracy) if accuracy else None,
            speed=float(speed) if speed else None,
            bearing=float(bearing) if bearing else None
        )
        
        if success:
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'error': 'Courier not found'}, status=404)
            
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error': f'Invalid data: {e}'}, status=400)
    except Exception as e:
        logger.error(f"Location update error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@login_required
@staff_member_required
def delivery_analytics(request):
    """Analytics dashboard for delivery performance"""
    
    # Date range filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    orders_query = Order.objects.all()
    
    if date_from:
        orders_query = orders_query.filter(created_at__gte=date_from)
    if date_to:
        orders_query = orders_query.filter(created_at__lte=date_to)
    
    # Delivery performance metrics
    total_orders = orders_query.count()
    delivered_orders = orders_query.filter(status='delivered').count()
    overdue_orders = orders_query.filter(
        status__in=['assigned', 'picked_up', 'in_transit'],
        estimated_delivery_time__lt=timezone.now()
    ).count()
    
    # Delivery time analysis
    completed_orders = orders_query.filter(
        status='delivered',
        estimated_delivery_time__isnull=False,
        actual_delivery_time__isnull=False
    )
    
    on_time_deliveries = 0
    total_delivery_time = timedelta()
    total_delay = timedelta()
    
    for order in completed_orders:
        if order.actual_delivery_time <= order.estimated_delivery_time:
            on_time_deliveries += 1
        else:
            total_delay += order.actual_delivery_time - order.estimated_delivery_time
    
    # Courier performance
    courier_stats = []
    for courier in Courier.objects.all():
        courier_orders = orders_query.filter(courier=courier)
        courier_delivered = courier_orders.filter(status='delivered').count()
        
        courier_stats.append({
            'courier': courier,
            'total_orders': courier_orders.count(),
            'delivered_orders': courier_delivered,
            'delivery_rate': (courier_delivered / courier_orders.count() * 100) if courier_orders.count() > 0 else 0,
        })
    
    # Route efficiency
    routes = DeliveryRoute.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    )
    
    context = {
        'total_orders': total_orders,
        'delivered_orders': delivered_orders,
        'overdue_orders': overdue_orders,
        'delivery_rate': (delivered_orders / total_orders * 100) if total_orders > 0 else 0,
        'on_time_rate': (on_time_deliveries / completed_orders.count() * 100) if completed_orders.count() > 0 else 0,
        'courier_stats': courier_stats,
        'total_routes': routes.count(),
        'active_routes': routes.filter(status='active').count(),
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'crm/delivery_analytics.html', context)


@login_required
@staff_member_required  
def auto_assign_orders(request):
    """Automatically assign optimal couriers to pending orders"""
    
    pending_orders = Order.objects.filter(status='new', courier__isnull=True)
    assigned_count = 0
    
    for order in pending_orders:
        optimal_courier = logistics_manager.assign_optimal_courier(order)
        if optimal_courier:
            order.courier = optimal_courier
            order.status = 'assigned'
            
            # Calculate delivery time
            delivery_calculator = DeliveryTimeCalculator()
            delivery_calculator.update_delivery_estimates(order)
            
            order.save()
            assigned_count += 1
    
    if assigned_count > 0:
        messages.success(request, f'Успішно призначено {assigned_count} замовлень оптимальним кур\'єрам!')
    else:
        messages.info(request, 'Ні одного замовлення не було призначено. Перевірте доступність кур\'єрів та місцезнаходження замовлень.')
    
    return redirect('logistics_dashboard')


@login_required
@staff_member_required
def create_daily_routes(request):
    """Create optimized routes for all pending orders"""
    
    try:
        routes = logistics_manager.create_optimized_routes_for_day()
        
        if routes:
            total_orders = sum(route.order_count for route in routes)
            messages.success(request, 
                f'Створено {len(routes)} оптимізованих маршрутів, що покривають {total_orders} замовлень!')
        else:
            messages.info(request, 'Маршрути не створено. Перевірте наявність доступних кур\'єрів та замовлень в очікуванні.')
            
    except Exception as e:
        logger.error(f"Daily route creation error: {e}")
        messages.error(request, f'Помилка створення маршрутів: {e}')
    
    return redirect('logistics_dashboard')


@login_required
def geocode_address(request):
    """API endpoint for geocoding addresses"""
    
    address = request.GET.get('address')
    if not address:
        return JsonResponse({'error': 'Address parameter required'}, status=400)
    
    try:
        geocoder = GeoCoder()
        latitude, longitude = geocoder.geocode_address(address)
        
        if latitude and longitude:
            return JsonResponse({
                'latitude': latitude,
                'longitude': longitude,
                'status': 'success'
            })
        else:
            return JsonResponse({
                'error': 'Address not found',
                'status': 'not_found'
            }, status=404)
            
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        return JsonResponse({'error': 'Geocoding service error'}, status=500)


# Payment Management Views

@login_required
@staff_member_required
def payment_create(request, order_id):
    """Create payment for an order"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if payment already exists
    if hasattr(order, 'payment'):
        messages.info(request, 'Платіж для цього замовлення вже існує.')
        return redirect('payment_detail', payment_id=order.payment.id)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, order=order)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.order = order
            payment.save()
            messages.success(request, 'Платіж створено успішно!')
            return redirect('payment_detail', payment_id=payment.id)
    else:
        form = PaymentForm(order=order)
    
    return render(request, 'crm/payment_form.html', {
        'form': form,
        'order': order,
        'title': 'Створити платіж'
    })


@login_required
@staff_member_required
def payment_detail(request, payment_id):
    """View payment details"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    return render(request, 'crm/payment_detail.html', {
        'payment': payment,
        'order': payment.order
    })


@login_required
@staff_member_required
def payment_process(request, payment_id):
    """Process payment (mark as completed)"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.status == 'completed':
        messages.info(request, 'Платіж вже оброблено.')
        return redirect('payment_detail', payment_id=payment.id)
    
    if request.method == 'POST':
        form = PaymentProcessForm(request.POST, order=payment.order)
        if form.is_valid():
            # Update payment details
            payment.method = form.cleaned_data['payment_method']
            payment.payment_notes = form.cleaned_data.get('payment_notes', '')
            
            if form.cleaned_data['payment_method'] == 'cash':
                payment.cash_received = form.cleaned_data['cash_received']
                payment.change_amount = payment.calculate_change()
            elif form.cleaned_data.get('transaction_id'):
                payment.transaction_id = form.cleaned_data['transaction_id']
            
            # Process the payment
            payment.process_payment(user=request.user)
            
            # Отправляем email уведомление о получении платежа
            try:
                EmailNotificationService.notify_payment_received(payment)
                logger.info(f"Email уведомление о платеже отправлено для заказа #{payment.order.id}")
            except Exception as e:
                logger.error(f"Ошибка отправки email о платеже для заказа #{payment.order.id}: {str(e)}")
            
            messages.success(request, f'Платіж оброблено успішно! Здача: {payment.change_amount if payment.change_amount else 0} грн')
            return redirect('payment_detail', payment_id=payment.id)
    else:
        form = PaymentProcessForm(order=payment.order)
        form.fields['payment_method'].initial = payment.method
    
    return render(request, 'crm/payment_process.html', {
        'form': form,
        'payment': payment,
        'order': payment.order
    })


@login_required
@staff_member_required
def payment_cash(request, order_id):
    """Quick cash payment processing"""
    order = get_object_or_404(Order, id=order_id)
    
    # Get or create payment
    payment = getattr(order, 'payment', None)
    if not payment:
        payment = order.create_payment(method='cash')
    
    if request.method == 'POST':
        form = CashPaymentForm(request.POST, instance=payment, order=order)
        if form.is_valid():
            payment = form.save()
            payment.method = 'cash'
            payment.change_amount = payment.calculate_change()
            payment.process_payment(user=request.user)
            
            change_msg = f" Здача: {payment.change_amount} грн" if payment.change_amount else ""
            messages.success(request, f'Готівкову оплату оброблено успішно!{change_msg}')
            return redirect('order_update', pk=order.id)
    else:
        form = CashPaymentForm(instance=payment, order=order)
    
    return render(request, 'crm/payment_cash.html', {
        'form': form,
        'payment': payment,
        'order': order
    })


@login_required
def payments_list(request):
    """List all payments with filters"""
    payments = Payment.objects.select_related('order', 'order__client', 'processed_by').all()

    if not (request.user.is_superuser or request.user.is_staff):
        payments = payments.filter(order__created_by=request.user)
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    method_filter = request.GET.get('method')
    if method_filter:
        payments = payments.filter(method=method_filter)
    
    date_from = request.GET.get('date_from')
    if date_from:
        payments = payments.filter(created_at__date__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        payments = payments.filter(created_at__date__lte=date_to)
    
    return render(request, 'crm/payments_list.html', {
        'payments': payments,
        'status_filter': status_filter,
        'method_filter': method_filter,
        'payment_statuses': Payment.PAYMENT_STATUS_CHOICES,
        'payment_methods': Payment.PAYMENT_METHOD_CHOICES,
    })


@login_required
@staff_member_required
def payment_refund(request, payment_id):
    """Refund a payment"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.status != 'completed':
        messages.error(request, 'Можна повернути лише завершені платежі.')
        return redirect('payment_detail', payment_id=payment.id)
    
    if request.method == 'POST':
        refund_reason = request.POST.get('refund_reason', '')
        
        # Create refund record
        payment.status = 'refunded'
        payment.payment_notes += f"\n\nПовернення: {refund_reason}"
        payment.save()
        
        messages.success(request, 'Платіж повернено успішно.')
        return redirect('payment_detail', payment_id=payment.id)
    
    return render(request, 'crm/payment_refund.html', {
        'payment': payment
    })


@csrf_exempt
@require_http_methods(["POST"])
def payment_webhook(request):
    """Webhook for online payment processing (for future integration)"""
    try:
        if not _is_authorized(request, getattr(settings, 'PAYMENT_WEBHOOK_SECRET', None)):
            return JsonResponse({'status': 'unauthorized'}, status=403)

        # This is a placeholder for future online payment integration
        # You would integrate with LiqPay, Monobank, or other payment gateways here
        
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        status = data.get('status')
        
        # Find payment by transaction_id and update status
        if transaction_id:
            try:
                payment = Payment.objects.get(transaction_id=transaction_id)
                if status == 'success':
                    payment.status = 'completed'
                    payment.processed_at = timezone.now()
                    payment.gateway_response = data
                    payment.save()
                    
                    logger.info(f"Payment {payment.id} completed via webhook")
                elif status == 'failed':
                    payment.status = 'failed'
                    payment.gateway_response = data
                    payment.save()
                    
                return JsonResponse({'status': 'ok'})
            except Payment.DoesNotExist:
                logger.warning(f"Payment with transaction_id {transaction_id} not found")
        
        return JsonResponse({'status': 'ignored'})
        
    except Exception as e:
        logger.error(f"Payment webhook error: {e}")
        return JsonResponse({'status': 'error'}, status=500)


@require_http_methods(["POST"])
def support_chat_api(request):
    """AI support chat endpoint (local Ollama)"""
    try:
        data = json.loads(request.body)
        message = (data.get('message') or '').strip()
        if not message:
            return JsonResponse({'error': 'Порожнє повідомлення'}, status=400)

        is_staff_user = request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)
        message_lc = message.lower()
        mentions_phone = any(k in message_lc for k in ['телефон', 'номер', 'контакт', 'phone'])
        id_match = re.search(r'#?(\d{1,10})', message_lc)
        detected_id = int(id_match.group(1)) if id_match else None
        mentions_payment = any(k in message_lc for k in ['платіж', 'платеж', 'оплата', 'транзакц', 'payment'])
        mentions_order = any(k in message_lc for k in ['замовлення', 'order', 'пріоритет', 'статус'])

        if detected_id and (mentions_payment or mentions_order):
            if not is_staff_user:
                return JsonResponse({'reply': 'Для перегляду даних із бази потрібні права персоналу. Увійдіть під staff/superuser.'})
            if mentions_payment and not mentions_order:
                payment = Payment.objects.filter(id=detected_id).select_related('order').first()
                if not payment:
                    return JsonResponse({'reply': f"Платіж #{detected_id} не знайдено. Перевірте номер або напишіть номер замовлення."})
                reply = (
                    f"Платіж #{payment.id}: статус — {payment.get_status_display()}, "
                    f"сума — {payment.amount} грн, метод — {payment.get_method_display()}. "
                    f"Створено: {payment.created_at.strftime('%d.%m.%Y %H:%M')}."
                )
                return JsonResponse({'reply': reply})

            order = Order.objects.filter(id=detected_id).select_related('payment').first()
            if not order:
                return JsonResponse({'reply': f"Замовлення #{detected_id} не знайдено. Перевірте номер."})
            payment_status = order.payment_status_display
            reply = (
                f"Замовлення #{order.id}: статус — {order.get_status_display()}, "
                f"пріоритет — {order.get_priority_display()}, "
                f"сума — {order.total_price} грн, оплата — {payment_status}."
            )
            return JsonResponse({'reply': reply})

        # Current user info requests
        if any(k in message_lc for k in ['мій логін', 'мій логин', 'мій username', 'мій юзернейм', 'мій користувач']):
            if request.user.is_authenticated:
                return JsonResponse({'reply': f"Ваш логін: {request.user.username}."})
            return JsonResponse({'reply': "Ви не увійшли в систему."})

        # Revenue stats for current month
        if any(k in message_lc for k in ['дохід', 'доход', 'виручка', 'revenue']) and any(k in message_lc for k in ['місяць', 'місяця', 'month']):
            payments = Payment.objects.filter(status='completed')
            if not is_staff_user:
                payments = payments.filter(order__created_by=request.user)
            today = timezone.now().date()
            month_start = today.replace(day=1)
            total = payments.filter(processed_at__date__gte=month_start).aggregate(
                total=Sum('amount')
            )['total'] or 0
            return JsonResponse({'reply': f"Дохід за поточний місяць: {float(total):.2f} грн."})

        if detected_id and any(k in message_lc for k in ['клієнт', 'клиент', 'користувач', 'юзер', 'user']):
            if not is_staff_user:
                return JsonResponse({'reply': 'Для доступу до даних потрібні права персоналу. Увійдіть під staff/superuser.'})
            client = Client.objects.filter(id=detected_id).first()
            if client:
                wants_phone = any(k in message_lc for k in ['телефон', 'номер', 'контакт', 'phone'])
                wants_email = 'email' in message_lc or 'емейл' in message_lc or 'e-mail' in message_lc
                wants_address = any(k in message_lc for k in ['адреса', 'адрес', 'address'])
                wants_name = any(k in message_lc for k in ['ім\'я', 'имя', 'name', 'піб', 'прізвище'])

                parts = []
                if wants_name or not (wants_phone or wants_email or wants_address):
                    parts.append(f"ім'я — {client.name}")
                if wants_phone:
                    parts.append(f"телефон — {client.phone or 'не вказано'}")
                if wants_email:
                    parts.append(f"email — {client.email or 'не вказано'}")
                if wants_address:
                    parts.append(f"адреса — {client.address or 'не вказано'}")

                reply = f"Користувач {client.id}: " + ', '.join(parts) + "."
                return JsonResponse({'reply': reply})
            return JsonResponse({'reply': f"Користувача {detected_id} не знайдено."})

        nav_help = [
            {
                'keywords': ['замовлення', 'order', 'створити замовлення', 'нове замовлення'],
                'answer': "Замовлення: список — /orders/, створити — /orders/create/.",
            },
            {
                'keywords': ['клієнт', 'клієнти', 'client'],
                'answer': "Клієнти: список — /clients/.",
            },
            {
                'keywords': ['курʼєр', 'курєр', 'курьер', 'courier'],
                'answer': "Курʼєри: список — /couriers/, трекінг — /logistics/tracking/.",
            },
            {
                'keywords': ['платіж', 'платеж', 'оплата', 'payment'],
                'answer': "Платежі: список — /payments/.",
            },
            {
                'keywords': ['логістика', 'маршрут', 'оптимізація', 'route'],
                'answer': "Логістика: панель — /logistics/, оптимізація — /logistics/route-optimization/.",
            },
        ]

        for item in nav_help:
            if any(keyword in message_lc for keyword in item['keywords']):
                return JsonResponse({'reply': item['answer'], 'source': 'nav'})

        system_prompt = (
            "Ти — навігаційний помічник CRM. "
            "Відповідай українською, коротко й по суті. "
            "Основне завдання — підказати, де в CRM знайти потрібну інформацію (URLs/меню). "
            "Не вигадуй дані. Якщо користувач просить дані з БД — перевіряй через серверні правила. "
            "Якщо незрозуміло — задай коротке уточнення."
        )

        history = data.get('history') or []
        messages = [{'role': 'system', 'content': system_prompt}]
        for item in history[-6:]:
            role = item.get('role')
            content = (item.get('content') or '').strip()
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': content})
        messages.append({'role': 'user', 'content': message})

        payload = {
            'model': settings.OLLAMA_MODEL,
            'stream': False,
            'messages': messages,
        }

        response = requests.post(
            f"{settings.OLLAMA_URL.rstrip('/')}/api/chat",
            json=payload,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        answer = (data.get('message') or {}).get('content') or ''
        if not answer:
            return JsonResponse({'error': 'Порожня відповідь від AI'}, status=502)

        return JsonResponse({'reply': answer})
    except requests.RequestException as e:
        logger.error(f"AI support error: {e}")
        return JsonResponse({'error': 'AI сервіс недоступний'}, status=502)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невірний формат JSON'}, status=400)
    except Exception as e:
        logger.error(f"AI support unexpected error: {e}")
        return JsonResponse({'error': 'Внутрішня помилка сервера'}, status=500)


@login_required
@staff_member_required
def payment_quick(request, order_id):
    """Швидка оплата з вибором методу"""
    order = get_object_or_404(Order, id=order_id)
    
    # Get or create payment
    payment = getattr(order, 'payment', None)
    if not payment:
        payment = order.create_payment()
    
    if request.method == 'POST':
        form = PaymentProcessForm(request.POST, order=order)
        if form.is_valid():
            payment_method = form.cleaned_data['payment_method']
            payment.method = payment_method
            payment.payment_notes = form.cleaned_data.get('payment_notes', '')
            
            if payment_method == 'cash':
                payment.cash_received = form.cleaned_data['cash_received']
                payment.change_amount = payment.calculate_change()
                success_msg = f'Готівкову оплату оброблено! Здача: {payment.change_amount} грн'
            elif payment_method == 'card':
                payment.transaction_id = form.cleaned_data.get('transaction_id', '')
                success_msg = 'Оплату картою оброблено успішно!'
            elif payment_method == 'online':
                payment.transaction_id = form.cleaned_data.get('transaction_id', '')
                success_msg = 'Онлайн оплату оброблено успішно!'
            else:
                success_msg = 'Оплату оброблено успішно!'
            
            payment.process_payment(user=request.user)
            messages.success(request, success_msg)
            return redirect('orders_list')
    else:
        form = PaymentProcessForm(order=order)
    
    return render(request, 'crm/payment_quick.html', {
        'form': form,
        'payment': payment,
        'order': order
    })


@require_http_methods(["POST"])
@login_required
@staff_member_required
def create_client_api(request):
    """API для створення нового клієнта"""
    logger.info(f"Create client API called by user: {request.user}")
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        address = data.get('address', '').strip()
        
        if not name or not phone:
            return JsonResponse({
                'status': 'error',
                'error': 'Ім\'я та телефон є обов\'язковими полями'
            }, status=400)
        
        # Перевірити, чи не існує клієнт з таким телефоном
        if Client.objects.filter(phone=phone).exists():
            return JsonResponse({
                'status': 'error',
                'error': 'Клієнт з таким номером телефону вже існує'
            }, status=400)
        
        # Створити нового клієнта
        client = Client.objects.create(
            name=name,
            phone=phone,
            email=email or None,
            address=address or ''
        )
        
        return JsonResponse({
            'status': 'success',
            'client': {
                'id': client.id,
                'name': client.name,
                'phone': client.phone,
                'email': client.email,
                'address': client.address
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'error': 'Невірний формат JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Client creation error: {e}")
        return JsonResponse({
            'status': 'error',
            'error': 'Внутрішня помилка сервера'
        }, status=500)
        if mentions_phone:
            if not is_staff_user:
                return JsonResponse({'reply': 'Для доступу до контактів клієнтів потрібні права персоналу. Увійдіть під службовим акаунтом.'})

            # Extract probable name tokens (Cyrillic/Latin words)
            tokens = re.findall(r"[A-Za-zА-Яа-яІіЇїЄєҐґ'’\-]+", message)
            stop = {
                'підкажи', 'підкажіть', 'номер', 'телефону', 'телефон', 'контакт', 'контакти',
                'клієнта', 'клієнт', 'будь', 'ласка', 'будь-ласка', 'дай', 'дати', 'потрібен',
                'потрібно', 'мені', 'нам', 'про', 'для', 'це', 'цей', 'ця'
            }
            name_parts = [t for t in tokens if t.lower() not in stop]
            if name_parts:
                # Build a tolerant query for Ukrainian/Russian name cases (e.g., Олександра -> Олександр)
                variants = set()
                for part in name_parts:
                    variants.add(part)
                    if len(part) > 3 and part[-1].lower() in ('а', 'я', 'і', 'у'):
                        variants.add(part[:-1])

                from django.db.models import Q
                query = Q()
                for part in variants:
                    query &= Q(name__icontains=part)

                client = Client.objects.filter(query).first()
                if client and client.phone:
                    return JsonResponse({'reply': f"Контакт клієнта {client.name}: {client.phone}."})
                if client and not client.phone:
                    return JsonResponse({'reply': f"У клієнта {client.name} немає телефону в системі."})
            if detected_id:
                client = Client.objects.filter(id=detected_id).first()
                if client and client.phone:
                    return JsonResponse({'reply': f"Контакт клієнта {client.name}: {client.phone}."})
                if client and not client.phone:
                    return JsonResponse({'reply': f"У клієнта {client.name} немає телефону в системі."})
            return JsonResponse({'reply': "Не знайшов клієнта за таким ім'ям. Спробуйте повне ПІБ або уточніть написання."})
