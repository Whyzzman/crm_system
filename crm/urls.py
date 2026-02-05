from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Main pages
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='crm/login.html'), name='login'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    
    # Orders
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/create/', views.order_create, name='order_create'),
    path('orders/<int:pk>/edit/', views.order_update, name='order_update'),
    path('orders/<int:pk>/delete/', views.order_delete, name='order_delete'),
    
    # Clients and Couriers
    path('clients/', views.clients_list, name='clients_list'),
    path('couriers/', views.couriers_list, name='couriers_list'),
    
    # Logistics Features
    path('logistics/', views.logistics_dashboard, name='logistics_dashboard'),
    path('logistics/route-optimization/', views.route_optimization, name='route_optimization'),
    path('logistics/routes/<int:route_id>/', views.route_detail, name='route_detail'),
    path('logistics/tracking/', views.courier_tracking, name='courier_tracking'),
    path('logistics/analytics/', views.delivery_analytics, name='delivery_analytics'),
    path('logistics/auto-assign/', views.auto_assign_orders, name='auto_assign_orders'),
    path('logistics/create-routes/', views.create_daily_routes, name='create_daily_routes'),
    
    # Payment Management
    path('payments/', views.payments_list, name='payments_list'),
    path('orders/<int:order_id>/payment/create/', views.payment_create, name='payment_create'),
    path('orders/<int:order_id>/payment/cash/', views.payment_cash, name='payment_cash'),
    path('orders/<int:order_id>/payment/quick/', views.payment_quick, name='payment_quick'),
    path('payments/<int:payment_id>/', views.payment_detail, name='payment_detail'),
    path('payments/<int:payment_id>/process/', views.payment_process, name='payment_process'),
    path('payments/<int:payment_id>/refund/', views.payment_refund, name='payment_refund'),
    
    # API endpoints
    path('api/courier-location/', views.update_courier_location, name='update_courier_location'),
    path('api/geocode/', views.geocode_address, name='geocode_address'),
    path('api/create-client/', views.create_client_api, name='create_client_api'),
    path('api/payment-webhook/', views.payment_webhook, name='payment_webhook'),
    path('api/support-chat/', views.support_chat_api, name='support_chat_api'),
]
