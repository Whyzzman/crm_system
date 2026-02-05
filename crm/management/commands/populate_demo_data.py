from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from crm.models import Client, Courier, Order, Payment
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import random


class Command(BaseCommand):
    help = 'Заповнює базу даних демонстраційними даними для дипломної роботи'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Починаємо заповнення демонстраційними даними...'))
        
        # Створюємо користувачів
        self.create_users()
        
        # Створюємо клієнтів
        self.create_clients()
        
        # Створюємо кур'єрів
        self.create_couriers()
        
        # Створюємо замовлення
        self.create_orders()
        
        self.stdout.write(self.style.SUCCESS('Демонстраційні дані успішно створено!'))

    def create_users(self):
        """Створює користувачів системи"""
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@crm.com', 'admin123')
            self.stdout.write('Створено адміністратора: admin/admin123')
        
        if not User.objects.filter(username='manager').exists():
            manager = User.objects.create_user('manager', 'manager@crm.com', 'manager123')
            manager.is_staff = True
            manager.save()
            self.stdout.write('Створено менеджера: manager/manager123')

    def create_clients(self):
        """Створює клієнтів з українськими іменами та адресами"""
        clients_data = [
            {
                'name': 'Олександр Петренко',
                'phone': '+380671234567',
                'email': 'petrenko@gmail.com',
                'address': 'вул. Хрещатик, 15, Київ',
                'latitude': 50.4501,
                'longitude': 30.5234
            },
            {
                'name': 'Марія Іваненко',
                'phone': '+380672345678',
                'email': 'ivanenko.maria@ukr.net',
                'address': 'вул. Дерибасівська, 25, Одеса',
                'latitude': 46.4825,
                'longitude': 30.7233
            },
            {
                'name': 'Віктор Коваленко',
                'phone': '+380673456789',
                'email': 'kovalenko.viktor@gmail.com',
                'address': 'проспект Свободи, 8, Львів',
                'latitude': 49.8397,
                'longitude': 24.0297
            },
            {
                'name': 'Анна Шевченко',
                'phone': '+380674567890',
                'email': 'shevchenko.anna@yahoo.com',
                'address': 'вул. Сумська, 45, Харків',
                'latitude': 49.9935,
                'longitude': 36.2304
            },
            {
                'name': 'Дмитро Мельник',
                'phone': '+380675678901',
                'email': 'melnyk.dmytro@outlook.com',
                'address': 'вул. Соборна, 12, Дніпро',
                'latitude': 48.4647,
                'longitude': 35.0462
            },
            {
                'name': 'Оксана Бондаренко',
                'phone': '+380676789012',
                'email': 'bondarenko.oksana@gmail.com',
                'address': 'вул. Грушевського, 33, Запоріжжя',
                'latitude': 47.8388,
                'longitude': 35.1396
            },
            {
                'name': 'Сергій Литвиненко',
                'phone': '+380677890123',
                'email': 'lytvynenko@gmail.com',
                'address': 'вул. Миколаївська, 18, Полтава',
                'latitude': 49.5937,
                'longitude': 34.5407
            },
            {
                'name': 'Тетяна Гриценко',
                'phone': '+380678901234',
                'email': 'hrytsenko.tetiana@ukr.net',
                'address': 'вул. Героїв Майдану, 7, Вінниця',
                'latitude': 49.2331,
                'longitude': 28.4682
            },
            {
                'name': 'Ігор Савченко',
                'phone': '+380679012345',
                'email': 'savchenko.igor@gmail.com',
                'address': 'вул. Шевченка, 22, Чернігів',
                'latitude': 51.4982,
                'longitude': 31.2893
            },
            {
                'name': 'Юлія Кравченко',
                'phone': '+380670123456',
                'email': 'kravchenko.yulia@yahoo.com',
                'address': 'вул. Центральна, 11, Житомир',
                'latitude': 50.2547,
                'longitude': 28.6587
            }
        ]
        
        for client_data in clients_data:
            client, created = Client.objects.get_or_create(
                phone=client_data['phone'],
                defaults=client_data
            )
            if created:
                self.stdout.write(f'Створено клієнта: {client.name}')

    def create_couriers(self):
        """Створює кур'єрів"""
        couriers_data = [
            {
                'name': 'Андрій Коваль',
                'phone': '+380501234567',
                'email': 'koval.courier@gmail.com',
                'vehicle_type': 'motorcycle',
                'available': True,
                'current_latitude': 50.4501,
                'current_longitude': 30.5234
            },
            {
                'name': 'Максим Дорошенко',
                'phone': '+380502345678',
                'email': 'doroshenko.courier@ukr.net',
                'vehicle_type': 'car',
                'available': True,
                'current_latitude': 46.4825,
                'current_longitude': 30.7233
            },
            {
                'name': 'Володимир Стеценко',
                'phone': '+380503456789',
                'email': 'stetsenko.courier@gmail.com',
                'vehicle_type': 'bike',
                'available': True,
                'current_latitude': 49.8397,
                'current_longitude': 24.0297
            },
            {
                'name': 'Роман Гончаренко',
                'phone': '+380504567890',
                'email': 'honcharenko.courier@yahoo.com',
                'vehicle_type': 'motorcycle',
                'available': False,
                'current_latitude': 49.9935,
                'current_longitude': 36.2304
            },
            {
                'name': 'Олег Павленко',
                'phone': '+380505678901',
                'email': 'pavlenko.courier@outlook.com',
                'vehicle_type': 'car',
                'available': True,
                'current_latitude': 48.4647,
                'current_longitude': 35.0462
            }
        ]
        
        for courier_data in couriers_data:
            courier, created = Courier.objects.get_or_create(
                phone=courier_data['phone'],
                defaults=courier_data
            )
            if created:
                self.stdout.write(f'Створено кур\'єра: {courier.name}')

    def create_orders(self):
        """Створює замовлення з різними статусами"""
        clients = list(Client.objects.all())
        couriers = list(Courier.objects.all())
        manager = User.objects.filter(is_staff=True).first()
        
        if not clients or not couriers or not manager:
            self.stdout.write(self.style.ERROR('Спочатку потрібно створити клієнтів, кур\'єрів та менеджерів'))
            return
        
        orders_data = [
            {
                'product': 'Піца "Маргарита" (2 шт.) + Кока-кола (1.5л)',
                'quantity': 3,
                'base_price': Decimal('320.00'),
                'additional_fees': Decimal('25.00'),
                'status': 'delivered',
                'priority': 'normal',
                'days_ago': 5
            },
            {
                'product': 'Борщ, котлети по-київськи, салат Олів\'є',
                'quantity': 1,
                'base_price': Decimal('450.00'),
                'additional_fees': Decimal('30.00'),
                'status': 'delivered',
                'priority': 'high',
                'days_ago': 3
            },
            {
                'product': 'Суші сет "Філадельфія" + імбирний чай',
                'quantity': 1,
                'base_price': Decimal('580.00'),
                'additional_fees': Decimal('40.00'),
                'status': 'in_transit',
                'priority': 'normal',
                'days_ago': 0
            },
            {
                'product': 'Букет троянд (25 шт.) + листівка',
                'quantity': 1,
                'base_price': Decimal('1250.00'),
                'additional_fees': Decimal('50.00'),
                'status': 'assigned',
                'priority': 'urgent',
                'days_ago': 0
            },
            {
                'product': 'Медикаменти: анальгін, йод, бинти',
                'quantity': 1,
                'base_price': Decimal('180.00'),
                'additional_fees': Decimal('15.00'),
                'status': 'picked_up',
                'priority': 'urgent',
                'days_ago': 0
            },
            {
                'product': 'Продукти: хліб, молоко, яйця, масло',
                'quantity': 1,
                'base_price': Decimal('275.00'),
                'additional_fees': Decimal('20.00'),
                'status': 'new',
                'priority': 'normal',
                'days_ago': 0
            },
            {
                'product': 'Торт "Наполеон" (2 кг)',
                'quantity': 1,
                'base_price': Decimal('650.00'),
                'additional_fees': Decimal('35.00'),
                'status': 'delivered',
                'priority': 'high',
                'days_ago': 7
            },
            {
                'product': 'Документи з нотаріуса (термінові)',
                'quantity': 1,
                'base_price': Decimal('150.00'),
                'additional_fees': Decimal('100.00'),
                'status': 'delivered',
                'priority': 'urgent',
                'days_ago': 2
            },
            {
                'product': 'Навушники Apple AirPods',
                'quantity': 1,
                'base_price': Decimal('200.00'),
                'additional_fees': Decimal('25.00'),
                'status': 'assigned',
                'priority': 'normal',
                'days_ago': 1
            },
            {
                'product': 'Бізнес-ланч на 5 осіб',
                'quantity': 5,
                'base_price': Decimal('850.00'),
                'additional_fees': Decimal('45.00'),
                'status': 'in_transit',
                'priority': 'high',
                'days_ago': 0
            }
        ]
        
        for i, order_data in enumerate(orders_data):
            client = clients[i % len(clients)]
            courier = couriers[i % len(couriers)] if order_data['status'] != 'new' else None
            
            # Розрахувати дати
            created_at = timezone.now() - timedelta(days=order_data['days_ago'])
            estimated_delivery = created_at + timedelta(hours=random.randint(1, 4))
            
            order = Order.objects.create(
                client=client,
                courier=courier,
                created_by=manager,
                product=order_data['product'],
                quantity=order_data['quantity'],
                address=client.address,
                latitude=client.latitude,
                longitude=client.longitude,
                base_price=order_data['base_price'],
                additional_fees=order_data['additional_fees'],
                total_price=order_data['base_price'] + order_data['additional_fees'],
                status=order_data['status'],
                priority=order_data['priority'],
                created_at=created_at,
                estimated_delivery_time=estimated_delivery
            )
            
            # Створити платіж для завершених замовлень
            if order_data['status'] in ['delivered', 'in_transit', 'picked_up']:
                payment_status = 'completed' if order_data['status'] == 'delivered' else 'pending'
                payment_method = random.choice(['cash', 'card', 'online'])
                
                payment = Payment.objects.create(
                    order=order,
                    amount=order.total_price,
                    method=payment_method,
                    status=payment_status,
                    created_at=created_at
                )
                
                if payment_status == 'completed':
                    payment.processed_at = created_at + timedelta(minutes=random.randint(30, 120))
                    payment.processed_by = manager
                    if payment_method == 'cash':
                        payment.cash_received = order.total_price + Decimal(random.randint(0, 100))
                        payment.change_amount = payment.cash_received - order.total_price
                    payment.save()
            
            self.stdout.write(f'Створено замовлення: {order.product[:50]}...')
        
        self.stdout.write(self.style.SUCCESS(f'Створено {len(orders_data)} замовлень'))
