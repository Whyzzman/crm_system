from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from crm.models import Client, Courier, Order, Payment
from decimal import Decimal
import random
from datetime import datetime, timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = 'Створює демонстраційні замовлення та платежі для захисту диплому'

    def add_arguments(self, parser):
        parser.add_argument(
            '--orders',
            type=int,
            default=15,
            help='Кількість замовлень для створення'
        )

    def handle(self, *args, **options):
        orders_count = options['orders']
        
        self.stdout.write(self.style.SUCCESS('🎓 Створення демонстраційних даних для дипломного проекту...'))
        
        # Отримуємо або створюємо користувача-менеджера
        manager_user, created = User.objects.get_or_create(
            username='diploma_manager',
            defaults={
                'email': 'manager@diploma.ua',
                'first_name': 'Менеджер',
                'last_name': 'Дипломний',
                'is_staff': True
            }
        )
        
        if created:
            manager_user.set_password('diploma2024')
            manager_user.save()
            self.stdout.write(f'✅ Створено менеджера: {manager_user.username}')
        
        # Перевіряємо наявність клієнтів та кур'єрів
        clients = list(Client.objects.all())
        couriers = list(Courier.objects.all())
        
        if not clients:
            self.stdout.write(self.style.ERROR('❌ Не знайдено клієнтів! Спочатку створіть клієнтів.'))
            return
            
        if not couriers:
            self.stdout.write(self.style.ERROR('❌ Не знайдено кур\'єрів! Спочатку створіть кур\'єрів.'))
            return
        
        # Список реалістичних товарів для доставки
        products = [
            'Піца "Маргарита" (30см)', 'Суші сет "Філадельфія"', 'Бургер з картоплею фрі',
            'Борщ з пампушками', 'Салат "Цезар" з куркою', 'Паста "Карбонара"',
            'Торт "Наполеон" (1кг)', 'Роли "Каліфорнія" (8шт)', 'Стейк з овочами',
            'Вареники з картоплею (20шт)', 'Шашлик зі свинини (500г)', 'Лазанья м\'ясна',
            'Салат "Олів\'є" (500г)', 'Котлети по-київськи (2шт)', 'Плов узбецький (400г)',
            'Суп-пюре з грибів', 'Рибні палички з рисом', 'Млинці з м\'ясом (6шт)',
            'Хінкалі з яловичиною (10шт)', 'Піца "Пепероні" (25см)'
        ]
        
        # Адреси доставки у Львові
        addresses = [
            'вул. Городоцька, 15, кв. 23, Львів',
            'вул. Стрийська, 202, кв. 45, Львів', 
            'вул. Пекарська, 8, кв. 12, Львів',
            'вул. Личаківська, 134, кв. 67, Львів',
            'вул. Зелена, 45, кв. 89, Львів',
            'вул. Наукова, 23, кв. 34, Львів',
            'вул. Замарстинівська, 178, кв. 56, Львів',
            'вул. Сихівська, 89, кв. 78, Львів',
            'вул. Шевченка, 12, кв. 90, Львів',
            'вул. Франка, 67, кв. 23, Львів',
            'вул. Коперника, 34, кв. 45, Львів',
            'вул. Дорошенка, 56, кв. 12, Львів',
            'вул. Підвальна, 23, кв. 67, Львів',
            'вул. Руська, 78, кв. 34, Львів',
            'вул. Театральна, 12, кв. 56, Львів'
        ]
        
        # Координати районів Львова
        coordinates = [
            (49.8397, 24.0297), (49.8083, 24.0657), (49.8419, 24.0315),
            (49.8356, 24.0222), (49.8234, 24.0534), (49.8456, 24.0123),
            (49.8167, 24.0789), (49.8012, 24.0445), (49.8523, 24.0098),
            (49.8289, 24.0612), (49.8445, 24.0334), (49.8178, 24.0567),
            (49.8356, 24.0289), (49.8234, 24.0445), (49.8123, 24.0678)
        ]
        
        # Статуси замовлень для різноманітності
        statuses = ['new', 'assigned', 'picked_up', 'in_transit', 'delivered', 'cancelled']
        status_weights = [10, 15, 10, 15, 45, 5]  # більше доставлених для демонстрації
        
        priorities = ['low', 'normal', 'high', 'urgent']
        priority_weights = [20, 50, 25, 5]
        
        created_orders = 0
        created_payments = 0
        
        self.stdout.write(f'📦 Створення {orders_count} замовлень...')
        
        for i in range(orders_count):
            # Випадкова дата створення (останні 30 днів)
            created_date = timezone.now() - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            # Вибираємо випадкові дані
            client = random.choice(clients)
            product = random.choice(products)
            address = random.choice(addresses)
            coords = random.choice(coordinates)
            status = random.choices(statuses, weights=status_weights)[0]
            priority = random.choices(priorities, weights=priority_weights)[0]
            quantity = random.randint(1, 3)
            
            # Ціноутворення
            base_price = Decimal(str(round(random.uniform(50, 500), 2)))
            additional_fees = Decimal('0.00')
            discount = Decimal('0.00')
            
            # Додаткові збори для термінових замовлень
            if priority == 'urgent':
                additional_fees = Decimal(str(round(float(base_price) * 0.2, 2)))  # 20% за терміновість
            elif priority == 'high':
                additional_fees = Decimal(str(round(float(base_price) * 0.1, 2)))  # 10% за високий пріоритет
            
            # Знижка для постійних клієнтів (випадково)
            if random.random() < 0.3:  # 30% шанс знижки
                discount = Decimal(str(round(float(base_price) * random.uniform(0.05, 0.15), 2)))
            
            # Створюємо замовлення
            order = Order.objects.create(
                client=client,
                product=product,
                quantity=quantity,
                address=address,
                latitude=coords[0],
                longitude=coords[1],
                status=status,
                priority=priority,
                base_price=base_price,
                additional_fees=additional_fees,
                discount=discount,
                created_by=manager_user,
                created_at=created_date
            )
            
            # Розраховуємо загальну ціну
            order.calculate_total_price()
            
            # Призначаємо кур'єра для непочаткових статусів
            if status != 'new':
                order.courier = random.choice(couriers)
            
            # Встановлюємо час доставки
            if status in ['assigned', 'picked_up', 'in_transit']:
                order.estimated_delivery_time = created_date + timedelta(
                    hours=random.randint(1, 4)
                )
            elif status == 'delivered':
                order.estimated_delivery_time = created_date + timedelta(
                    hours=random.randint(1, 3)
                )
                order.actual_delivery_time = created_date + timedelta(
                    hours=random.randint(1, 4)
                )
            
            order.save()
            created_orders += 1
            
            # Створюємо платіж (80% замовлень мають платежі)
            if random.random() < 0.8:
                payment_methods = ['cash', 'card', 'online', 'bank_transfer']
                payment_method = random.choice(payment_methods)
                
                # Статус платежу залежить від статусу замовлення
                if status == 'new':
                    payment_status = 'pending'
                elif status in ['assigned', 'picked_up']:
                    payment_status = random.choice(['pending', 'processing'])
                elif status == 'delivered':
                    payment_status = 'completed'
                elif status == 'cancelled':
                    payment_status = random.choice(['cancelled', 'refunded'])
                else:
                    payment_status = random.choice(['pending', 'processing', 'completed'])
                
                payment = Payment.objects.create(
                    order=order,
                    method=payment_method,
                    status=payment_status,
                    amount=order.total_price,
                    created_at=created_date
                )
                
                # Додаємо специфічні дані залежно від методу оплати
                if payment_method == 'cash' and payment_status == 'completed':
                    cash_received = order.total_price + Decimal(str(round(random.uniform(0, 50), 2)))
                    payment.cash_received = cash_received
                    payment.change_amount = cash_received - order.total_price
                    payment.processed_at = created_date + timedelta(hours=random.randint(1, 2))
                    payment.processed_by = manager_user
                
                elif payment_method in ['card', 'online'] and payment_status == 'completed':
                    payment.transaction_id = f"TXN{random.randint(100000, 999999)}"
                    payment.processed_at = created_date + timedelta(minutes=random.randint(5, 30))
                    payment.processed_by = manager_user
                
                elif payment_method == 'bank_transfer' and payment_status == 'completed':
                    payment.transaction_id = f"BANK{random.randint(1000000, 9999999)}"
                    payment.processed_at = created_date + timedelta(hours=random.randint(1, 24))
                    payment.processed_by = manager_user
                
                # Додаємо примітки
                notes = [
                    "Стандартна оплата", "Клієнт попросив здачу дрібними",
                    "Оплата при отриманні", "Переказ від корпоративного клієнта",
                    "Швидка оплата", "Постійний клієнт", "Оплата з бонусного рахунку"
                ]
                if random.random() < 0.4:  # 40% платежів мають примітки
                    payment.payment_notes = random.choice(notes)
                
                payment.save()
                created_payments += 1
            
            # Прогрес
            if (i + 1) % 5 == 0:
                self.stdout.write(f'  ✓ Створено {i + 1}/{orders_count} замовлень')
        
        self.stdout.write(self.style.SUCCESS(f'\n🎉 Демонстраційні дані успішно створені!'))
        self.stdout.write(f'📦 Замовлень створено: {created_orders}')
        self.stdout.write(f'💳 Платежів створено: {created_payments}')
        self.stdout.write(f'👤 Менеджер: {manager_user.username} (пароль: diploma2024)')
        
        # Статистика по статусах
        self.stdout.write('\n📊 Статистика замовлень:')
        for status_code, status_name in Order.STATUS_CHOICES:
            count = Order.objects.filter(status=status_code).count()
            if count > 0:
                self.stdout.write(f'  • {status_name}: {count}')
        
        # Статистика по платежах
        self.stdout.write('\n💰 Статистика платежів:')
        for status_code, status_name in Payment.PAYMENT_STATUS_CHOICES:
            count = Payment.objects.filter(status=status_code).count()
            if count > 0:
                self.stdout.write(f'  • {status_name}: {count}')
        
        # Загальна сума
        from django.db import models
        total_revenue = Payment.objects.filter(status='completed').aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        self.stdout.write(f'\n💵 Загальний дохід: {total_revenue} грн')
        
        self.stdout.write(self.style.SUCCESS('\n🚀 Готово! Тепер ви можете продемонструвати роботу системи на захисті диплому.'))
