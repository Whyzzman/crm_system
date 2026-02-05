from django.test import TestCase, Client as DjangoClient
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Client, Courier, Order, DeliveryRoute
from .logistics import RouteOptimizer
from decimal import Decimal


class RouteOptimizationTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        
        # Create test client
        self.client_obj = Client.objects.create(
            name='Test Client',
            phone='+380123456789',
            address='Test Address, Kyiv',
            latitude=50.4501,
            longitude=30.5234
        )
        
        # Create test courier
        self.courier = Courier.objects.create(
            name='Test Courier',
            phone='+380987654321',
            available=True,
            vehicle_type='car',
            current_latitude=50.4501,
            current_longitude=30.5234
        )
        
        # Create test orders
        self.order1 = Order.objects.create(
            client=self.client_obj,
            created_by=self.user,
            product='Test Product 1',
            quantity=1,
            address='Test Address 1, Kyiv',
            latitude=50.4501,
            longitude=30.5234,
            status='new',
            priority='normal',
            base_price=Decimal('100.00'),
            total_price=Decimal('100.00')
        )
        
        self.order2 = Order.objects.create(
            client=self.client_obj,
            created_by=self.user,
            product='Test Product 2',
            quantity=2,
            address='Test Address 2, Kyiv',
            latitude=50.4501,
            longitude=30.5234,
            status='new',
            priority='high',
            base_price=Decimal('200.00'),
            total_price=Decimal('200.00')
        )

    def test_route_optimizer_creation(self):
        """Test that RouteOptimizer can be created"""
        optimizer = RouteOptimizer()
        self.assertIsNotNone(optimizer)

    def test_route_optimization(self):
        """Test route optimization functionality"""
        optimizer = RouteOptimizer()
        orders = [self.order1, self.order2]
        
        # Test optimization
        result = optimizer.optimize_route(self.courier, orders)
        
        # Check that result contains expected keys
        self.assertIn('route', result)
        self.assertIn('total_distance', result)
        self.assertIn('estimated_duration', result)
        self.assertIn('route_coordinates', result)
        
        # Check that route contains orders
        self.assertEqual(len(result['route']), 2)
        
        # Check that total_distance is a number
        self.assertIsInstance(result['total_distance'], (int, float))
        
        # Check that estimated_duration is a timedelta
        from datetime import timedelta
        self.assertIsInstance(result['estimated_duration'], timedelta)

    def test_create_delivery_route(self):
        """Test creating a delivery route"""
        optimizer = RouteOptimizer()
        orders = [self.order1, self.order2]
        
        # Create route
        route = optimizer.create_delivery_route(
            courier=self.courier,
            orders=orders,
            name='Test Route'
        )
        
        # Check that route was created
        self.assertIsInstance(route, DeliveryRoute)
        self.assertEqual(route.courier, self.courier)
        self.assertEqual(route.name, 'Test Route')
        self.assertEqual(route.orders.count(), 2)
        
        # Check that route_data is serializable
        self.assertIsInstance(route.route_data, dict)
        self.assertIn('coordinates', route.route_data)
        self.assertIn('total_distance', route.route_data)
        self.assertIn('estimated_duration_minutes', route.route_data)

    def test_route_optimization_view_access(self):
        """Test that route optimization view is accessible"""
        client = DjangoClient()
        client.login(username='testuser', password='testpass123')
        
        response = client.get(reverse('route_optimization'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Route Optimization')

    def test_route_optimization_form_submission(self):
        """Test route optimization form submission"""
        client = DjangoClient()
        client.login(username='testuser', password='testpass123')
        
        # Submit form with valid data
        response = client.post(reverse('route_optimization'), {
            'courier': self.courier.id,
            'orders': [self.order1.id, self.order2.id],
            'route_name': 'Test Route'
        })
        
        # Check that route was created
        self.assertEqual(DeliveryRoute.objects.count(), 1)
        
        # Check that orders were updated
        self.order1.refresh_from_db()
        self.order2.refresh_from_db()
        self.assertEqual(self.order1.courier, self.courier)
        self.assertEqual(self.order2.status, 'assigned')

    def test_route_optimization_without_orders(self):
        """Test route optimization without orders"""
        client = DjangoClient()
        client.login(username='testuser', password='testpass123')
        
        # Submit form without orders
        response = client.post(reverse('route_optimization'), {
            'courier': self.courier.id,
            'orders': [],
            'route_name': 'Test Route'
        })
        
        # Check that no route was created
        self.assertEqual(DeliveryRoute.objects.count(), 0)
        
        # Check that form errors are displayed
        self.assertEqual(response.status_code, 200)

    def test_route_optimization_without_courier(self):
        """Test route optimization without courier"""
        client = DjangoClient()
        client.login(username='testuser', password='testpass123')
        
        # Submit form without courier
        response = client.post(reverse('route_optimization'), {
            'courier': '',
            'orders': [self.order1.id, self.order2.id],
            'route_name': 'Test Route'
        })
        
        # Check that no route was created
        self.assertEqual(DeliveryRoute.objects.count(), 0)
        
        # Check that form errors are displayed
        self.assertEqual(response.status_code, 200)
