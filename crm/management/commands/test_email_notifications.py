"""
Команда для тестирования email уведомлений
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from crm.models import Client, Order, Courier, Payment
from crm.email_notifications import EmailNotificationService
from decimal import Decimal


class Command(BaseCommand):
    help = 'Тестирование email уведомлений'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email для отправки тестовых уведомлений',
            required=True
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['all', 'order_created', 'order_status', 'payment', 'delivery_assigned', 'delivery_completed'],
            default='all',
            help='Тип уведомления для тестирования'
        )
    
    def handle(self, *args, **options):
        email = options['email']
        notification_type = options['type']
        
        self.stdout.write(f"Тестируем email уведомления для: {email}")
        
        # Создаем тестового пользователя если не существует
        user, created = User.objects.get_or_create(
            username='test_user',
            defaults={'email': email, 'first_name': 'Тест', 'last_name': 'Пользователь'}
        )
        
        # Создаем тестового клиента
        client, created = Client.objects.get_or_create(
            name='Тестовый Клиент',
            defaults={
                'phone': '+380501234567',
                'address': 'ул. Тестовая, 123',
                'email': email
            }
        )
        
        # Создаем тестового курьера
        courier, created = Courier.objects.get_or_create(
            name='Тестовый Курьер',
            defaults={
                'phone': '+380509876543',
                'email': email
            }
        )
        
        # Создаем тестовый заказ
        order = Order.objects.create(
            client=client,
            product='Тестовый товар',
            address='ул. Доставки, 456',
            delivery_notes='Описание тестового заказа',
            created_by=user,
            status='new',
            base_price=Decimal('150.00'),
            additional_fees=Decimal('25.00')
        )
        order.calculate_total_price()
        order.save()
        
        try:
            if notification_type in ['all', 'order_created']:
                self.stdout.write("Отправляем уведомление о создании заказа...")
                EmailNotificationService.notify_order_created(order)
                
            if notification_type in ['all', 'order_status']:
                self.stdout.write("Отправляем уведомление об изменении статуса...")
                order.status = 'confirmed'
                order.save()
                EmailNotificationService.notify_order_status_changed(order, 'new', 'confirmed')
                
            if notification_type in ['all', 'delivery_assigned']:
                self.stdout.write("Отправляем уведомление о назначении курьера...")
                order.courier = courier
                order.save()
                EmailNotificationService.notify_delivery_assigned(order, courier)
                
            if notification_type in ['all', 'payment']:
                self.stdout.write("Отправляем уведомление о платеже...")
                payment = Payment.objects.create(
                    order=order,
                    amount=order.total_price,
                    method='card',
                    status='completed'
                )
                EmailNotificationService.notify_payment_received(payment)
                
            if notification_type in ['all', 'delivery_completed']:
                self.stdout.write("Отправляем уведомление о завершении доставки...")
                order.status = 'delivered'
                order.save()
                EmailNotificationService.notify_delivery_completed(order)
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Тестовые email уведомления отправлены на {email}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка отправки email: {str(e)}')
            )
        
        finally:
            # Очищаем тестовые данные
            self.stdout.write("Очищаем тестовые данные...")
            order.delete()
            if created:
                client.delete()
                courier.delete()
                user.delete()
                
        self.stdout.write("Тестирование завершено!")
