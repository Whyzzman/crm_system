from django.core.management.base import BaseCommand
from crm.logistics import RouteService
from crm.models import Courier, Order, DeliveryRoute
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Test real road route generation'

    def handle(self, *args, **options):
        self.stdout.write('Testing real road route generation...')
        
        # Get or create test data
        courier, created = Courier.objects.get_or_create(
            name='Test Courier',
            defaults={
                'phone': '+380991234567',
                'vehicle_type': 'car',
                'current_latitude': 50.4501,
                'current_longitude': 30.5234,
                'available': True
            }
        )
        
        if created:
            self.stdout.write(f'Created test courier: {courier.name}')
        
        # Get or create test orders
        orders = []
        test_coordinates = [
            (50.4545, 30.5238, 'Test Address 1'),
            (50.4589, 30.5203, 'Test Address 2'),
            (50.4520, 30.5260, 'Test Address 3'),
        ]
        
        # Get or create a test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={
                'email': 'test@example.com',
                'first_name': 'Test',
                'last_name': 'User',
                'is_staff': True
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'Created test user: {user.username}')
        
        # Get or create a test client
        from crm.models import Client
        client, created = Client.objects.get_or_create(
            name='Test Client',
            defaults={
                'phone': '+380991234567',
                'address': 'Test Address, Kyiv'
            }
        )
        if created:
            self.stdout.write(f'Created test client: {client.name}')
        
        for i, (lat, lon, address) in enumerate(test_coordinates):
            order, created = Order.objects.get_or_create(
                id=1000 + i,  # Use high ID to avoid conflicts
                defaults={
                    'client': client,
                    'created_by': user,
                    'address': address,
                    'latitude': lat,
                    'longitude': lon,
                    'status': 'new',
                    'priority': 'normal'
                }
            )
            
            if created:
                self.stdout.write(f'Created test order: {order.id} at {address}')
            
            orders.append(order)
        
        # Test route service
        route_service = RouteService()
        
        # Create waypoints (courier location + order locations)
        waypoints = [(courier.current_latitude, courier.current_longitude)]
        for order in orders:
            waypoints.append((order.latitude, order.longitude))
        
        self.stdout.write(f'\nTesting route with {len(waypoints)} waypoints...')
        
        try:
            # Get route coordinates
            coordinates = route_service.get_route_coordinates(waypoints)
            self.stdout.write(f'✓ Generated {len(coordinates)} coordinate points')
            
            if len(coordinates) > len(waypoints):
                self.stdout.write('✓ Real road route generated!')
            else:
                self.stdout.write('⚠ Using straight line route (fallback mode)')
            
            # Get route summary
            summary = route_service.get_route_summary(waypoints)
            self.stdout.write(f'✓ Distance: {summary["distance"]:.2f} km')
            self.stdout.write(f'✓ Duration: {summary["duration"]:.1f} minutes')
            
            # Create actual route in database
            route_data = {
                'coordinates': summary['coordinates'],
                'total_distance': summary['distance'],
                'estimated_duration_minutes': summary['duration'],
                'order_count': len(orders),
                'created_at': '2024-01-01T10:00:00Z',
                'courier_id': courier.id,
                'courier_name': courier.name
            }
            
            # Convert duration from minutes to timedelta
            from datetime import timedelta
            estimated_duration = timedelta(minutes=summary['duration'])
            
            route = DeliveryRoute.objects.create(
                courier=courier,
                name=f'Test Route - {len(orders)} orders',
                total_distance=summary['distance'],
                estimated_duration=estimated_duration,
                route_data=route_data
            )
            
            self.stdout.write(f'✓ Created test route: {route.name}')
            self.stdout.write(f'✓ Route ID: {route.id}')
            self.stdout.write(f'✓ Route data saved with {len(summary["coordinates"])} coordinates')
            
        except Exception as e:
            self.stdout.write(f'✗ Error: {e}')
        
        self.stdout.write('\nTest completed!')
        self.stdout.write('You can now view the route at: /logistics/routes/{route.id}/')
