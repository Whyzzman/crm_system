"""
Management command to populate sample logistics data
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from crm.models import Client, Courier, Order, DeliveryZone
from crm.logistics import GeoCoder
import random
from datetime import timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = 'Populate the database with sample logistics data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clients',
            type=int,
            default=10,
            help='Number of clients to create'
        )
        parser.add_argument(
            '--couriers',
            type=int,
            default=5,
            help='Number of couriers to create'
        )
        parser.add_argument(
            '--orders',
            type=int,
            default=20,
            help='Number of orders to create'
        )

    def handle(self, *args, **options):
        self.stdout.write('Populating logistics data...')

        # Create admin user if not exists
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(self.style.SUCCESS('Created admin user: admin/admin123'))

        # Sample addresses in Kyiv, Ukraine
        addresses = [
            "Майдан Незалежності, Київ",
            "вул. Хрещатик, 15, Київ",
            "просп. Перемоги, 37, Київ",
            "вул. Саксаганського, 121, Київ",
            "просп. Лесі Українки, 26, Київ",
            "вул. Велика Васильківська, 55, Київ",
            "вул. Антоновича, 72, Київ",
            "просп. Голосіївський, 88, Київ",
            "вул. Жилянська, 45, Київ",
            "вул. Володимирська, 18, Київ"
        ]

        # Kyiv coordinates for fallback
        kyiv_coords = [(50.4501, 30.5234), (50.4421, 30.5367), (50.4547, 30.5238)]

        # Create clients
        geocoder = GeoCoder()
        for i in range(options['clients']):
            address = random.choice(addresses)
            
            # Try to geocode address
            lat, lon = geocoder.geocode_address(address)
            if not lat or not lon:
                # Use random Kyiv coordinates
                lat, lon = random.choice(kyiv_coords)
                lat += random.uniform(-0.01, 0.01)
                lon += random.uniform(-0.01, 0.01)

            client = Client.objects.create(
                name=f'Клієнт {i+1}',
                phone=f'+380{random.randint(500000000, 999999999)}',
                address=address,
                latitude=lat,
                longitude=lon
            )

        self.stdout.write(self.style.SUCCESS(f'Created {options["clients"]} clients'))

        # Create couriers
        vehicle_types = ['bike', 'motorcycle', 'car', 'van']
        for i in range(options['couriers']):
            # Random location in Kyiv
            lat, lon = random.choice(kyiv_coords)
            lat += random.uniform(-0.02, 0.02)
            lon += random.uniform(-0.02, 0.02)

            courier = Courier.objects.create(
                name=f"Кур'єр {i+1}",
                phone=f'+380{random.randint(500000000, 999999999)}',
                vehicle_type=random.choice(vehicle_types),
                available=random.choice([True, True, True, False]),  # 75% available
                current_latitude=lat,
                current_longitude=lon,
                last_location_update=timezone.now() - timedelta(minutes=random.randint(1, 30))
            )

        self.stdout.write(self.style.SUCCESS(f'Created {options["couriers"]} couriers'))

        # Create orders
        clients = list(Client.objects.all())
        couriers = list(Courier.objects.all())
        statuses = ['new', 'assigned', 'picked_up', 'in_transit', 'delivered']
        priorities = ['low', 'normal', 'high', 'urgent']
        products = [
            'Піца Маргарита',
            'Бургер з картоплею',
            'Суші сет',
            'Китайська локшина',
            'Курячі крила',
            'Салат Цезар',
            'Стейк з овочами',
            'Паста Карбонара'
        ]

        for i in range(options['orders']):
            client = random.choice(clients)
            courier = random.choice(couriers) if random.random() > 0.3 else None  # 70% have courier

            order = Order.objects.create(
                client=client,
                courier=courier,
                created_by=user,
                product=random.choice(products),
                quantity=random.randint(1, 3),
                address=client.address,
                latitude=client.latitude,
                longitude=client.longitude,
                status=random.choice(statuses),
                priority=random.choice(priorities),
                delivery_notes=f'Примітка до замовлення {i+1}',
                created_at=timezone.now() - timedelta(
                    hours=random.randint(0, 72)
                )
            )

            # Set estimated delivery time
            if order.courier:
                order.estimated_delivery_time = order.created_at + timedelta(
                    minutes=random.randint(30, 120)
                )
                order.save()

        self.stdout.write(self.style.SUCCESS(f'Created {options["orders"]} orders'))

        # Create delivery zones
        zones = [
            {
                'name': 'Центр',
                'base_time': timedelta(minutes=30),
                'traffic_multiplier': 1.5
            },
            {
                'name': 'Лівий берег',
                'base_time': timedelta(minutes=45),
                'traffic_multiplier': 1.2
            },
            {
                'name': 'Оболонь',
                'base_time': timedelta(minutes=40),
                'traffic_multiplier': 1.1
            },
            {
                'name': 'Троєщина',
                'base_time': timedelta(minutes=50),
                'traffic_multiplier': 1.0
            }
        ]

        for zone_data in zones:
            DeliveryZone.objects.create(
                name=zone_data['name'],
                polygon_data={'type': 'Polygon', 'coordinates': []},  # Simplified
                base_delivery_time=zone_data['base_time'],
                traffic_multiplier=zone_data['traffic_multiplier']
            )

        self.stdout.write(self.style.SUCCESS('Created delivery zones'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSample data created successfully!\n'
                f'- {options["clients"]} clients\n'
                f'- {options["couriers"]} couriers\n'
                f'- {options["orders"]} orders\n'
                f'- 4 delivery zones\n\n'
                f'Admin credentials: admin / admin123\n'
                f'Visit: http://localhost:8000/logistics/ to see the logistics dashboard'
            )
        )
