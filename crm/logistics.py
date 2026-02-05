"""
Logistics services for CRM system
Includes route optimization, GPS tracking, and delivery time calculations
"""

import math
import requests
import json
from datetime import timedelta, datetime
from typing import List, Tuple, Dict, Optional
from django.utils import timezone
from django.conf import settings
from .models import Order, Courier, CourierLocation, DeliveryRoute, RouteOrder, DeliveryZone, TrafficData
import logging

logger = logging.getLogger(__name__)

class GPSTracker:
    """Handle GPS tracking for couriers"""
    
    @staticmethod
    def update_courier_location(courier_id: int, latitude: float, longitude: float, 
                              accuracy: float = None, speed: float = None, bearing: float = None) -> bool:
        """Update courier's current location"""
        try:
            courier = Courier.objects.get(id=courier_id)
            
            # Update courier's current location
            courier.current_latitude = latitude
            courier.current_longitude = longitude
            courier.last_location_update = timezone.now()
            courier.save()
            
            # Store location history
            CourierLocation.objects.create(
                courier=courier,
                latitude=latitude,
                longitude=longitude,
                accuracy=accuracy,
                speed=speed,
                bearing=bearing
            )
            
            return True
        except Courier.DoesNotExist:
            logger.error(f"Courier with id {courier_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error updating courier location: {e}")
            return False
    
    @staticmethod
    def get_courier_location_history(courier_id: int, hours: int = 24) -> List[Dict]:
        """Get courier's location history for the last N hours"""
        try:
            courier = Courier.objects.get(id=courier_id)
            since = timezone.now() - timedelta(hours=hours)
            
            locations = CourierLocation.objects.filter(
                courier=courier,
                timestamp__gte=since
            ).order_by('-timestamp')
            
            return [
                {
                    'latitude': loc.latitude,
                    'longitude': loc.longitude,
                    'timestamp': loc.timestamp.isoformat(),
                    'speed': loc.speed,
                    'bearing': loc.bearing,
                    'accuracy': loc.accuracy
                }
                for loc in locations
            ]
        except Courier.DoesNotExist:
            return []
    
    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates using Haversine formula (in km)"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

class RouteOptimizer:
    """Handle route optimization for delivery routes"""
    
    def __init__(self):
        self.vehicle_speeds = {
            'bike': 15,      # km/h
            'motorcycle': 35, # km/h
            'car': 40,       # km/h
            'van': 35        # km/h
        }
    
    def optimize_route(self, courier: Courier, orders: List[Order]) -> Dict:
        """
        Optimize delivery route using nearest neighbor algorithm with real road routes
        """
        if not orders:
            return {'route': [], 'total_distance': 0, 'estimated_duration': timedelta()}
        
        # Starting point (courier's current location or default depot)
        start_lat = courier.current_latitude or 50.4501  # Default to Kyiv
        start_lon = courier.current_longitude or 30.5234
        
        # Create distance matrix
        locations = [(start_lat, start_lon)]  # Start with courier location
        for order in orders:
            lat = order.latitude or order.client.latitude or start_lat
            lon = order.longitude or order.client.longitude or start_lon
            locations.append((lat, lon))
        
        # Nearest neighbor algorithm
        unvisited = list(range(1, len(locations)))  # Skip starting point
        route = [0]  # Start at courier location
        
        while unvisited:
            current_idx = route[-1]
            current_lat, current_lon = locations[current_idx]
            
            # Find nearest unvisited location
            nearest_idx = min(unvisited, key=lambda idx: GPSTracker.calculate_distance(
                current_lat, current_lon, locations[idx][0], locations[idx][1]
            ))
            
            route.append(nearest_idx)
            unvisited.remove(nearest_idx)
        
        # Get real road route coordinates
        route_service = RouteService()
        
        # Determine routing profile based on vehicle type
        profile_map = {
            'car': 'driving-car',
            'van': 'driving-hgv',  # Heavy goods vehicle
            'motorcycle': 'driving-car',  # Motorcycle uses car profile
            'bike': 'cycling-regular',
            'bicycle': 'cycling-regular',
            'foot': 'foot-walking'
        }
        profile = profile_map.get(courier.vehicle_type, 'driving-car')
        
        # Get real route data
        route_summary = route_service.get_route_summary(
            [locations[idx] for idx in route], 
            profile
        )
        
        # Calculate estimated duration including service time
        travel_time = route_summary['duration']  # Already in minutes
        service_time = len(orders) * 15  # 15 minutes per delivery
        total_duration_minutes = travel_time + service_time
        estimated_duration = timedelta(minutes=total_duration_minutes)
        
        # Create optimized order sequence
        optimized_orders = []
        for i, route_idx in enumerate(route[1:], 1):  # Skip starting point
            order_idx = route_idx - 1  # Adjust for starting point
            optimized_orders.append({
                'order': orders[order_idx],
                'sequence': i,
                'location': locations[route_idx]
            })
        
        return {
            'route': optimized_orders,
            'total_distance': route_summary['distance'],
            'estimated_duration': estimated_duration,
            'route_coordinates': route_summary['coordinates']
        }
    
    def create_delivery_route(self, courier: Courier, orders: List[Order], name: str = None) -> DeliveryRoute:
        """Create an optimized delivery route"""
        optimization_result = self.optimize_route(courier, orders)
        
        # Create route name if not provided
        if not name:
            name = f"Route {timezone.now().strftime('%Y%m%d_%H%M')} - {courier.name}"
        
        # Create delivery route
        # Prepare serializable route data
        serializable_route_data = {
            'coordinates': optimization_result['route_coordinates'],
            'total_distance': optimization_result['total_distance'],
            'estimated_duration_minutes': int(optimization_result['estimated_duration'].total_seconds() / 60),
            'order_count': len(optimization_result['route']),
            'created_at': timezone.now().isoformat(),
            'courier_id': courier.id,
            'courier_name': courier.name
        }
        
        route = DeliveryRoute.objects.create(
            courier=courier,
            name=name,
            total_distance=optimization_result['total_distance'],
            estimated_duration=optimization_result['estimated_duration'],
            route_data=serializable_route_data
        )
        
        # Add orders to route
        for route_order in optimization_result['route']:
            RouteOrder.objects.create(
                route=route,
                order=route_order['order'],
                sequence=route_order['sequence']
            )
        
        return route

class GeoCoder:
    """Handle geocoding services"""
    
    @staticmethod
    def geocode_address(address: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Geocode address to coordinates using OpenStreetMap Nominatim
        For production, consider using Google Maps API with rate limiting
        """
        try:
            base_url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'CRM-Logistics-System/1.0'
            }
            
            response = requests.get(base_url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
            
            return None, None
            
        except Exception as e:
            logger.error(f"Geocoding error for address '{address}': {e}")
            return None, None
    
    @staticmethod
    def reverse_geocode(latitude: float, longitude: float) -> Optional[str]:
        """Reverse geocode coordinates to address"""
        try:
            base_url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'CRM-Logistics-System/1.0'
            }
            
            response = requests.get(base_url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            return data.get('display_name', '')
            
        except Exception as e:
            logger.error(f"Reverse geocoding error for {latitude}, {longitude}: {e}")
            return None

class DeliveryTimeCalculator:
    """Calculate delivery times based on various factors"""
    
    def __init__(self):
        self.base_preparation_time = timedelta(minutes=30)  # Order preparation time
        self.vehicle_speeds = {
            'bike': 15,      # km/h in city traffic
            'motorcycle': 35,
            'car': 40,
            'van': 35
        }
    
    def calculate_delivery_time(self, order: Order, courier: Courier = None) -> timedelta:
        """Calculate estimated delivery time for an order"""
        if not courier:
            courier = order.courier
        
        if not courier:
            # Default estimation without specific courier
            return self.base_preparation_time + timedelta(hours=1)
        
        # Get current time factors
        now = timezone.now()
        hour = now.hour
        day_of_week = now.weekday()
        
        # Calculate distance
        courier_lat = courier.current_latitude or 50.4501  # Default to Kyiv
        courier_lon = courier.current_longitude or 30.5234
        order_lat = order.latitude or order.client.latitude or courier_lat
        order_lon = order.longitude or order.client.longitude or courier_lon
        
        distance = GPSTracker.calculate_distance(courier_lat, courier_lon, order_lat, order_lon)
        
        # Calculate base travel time
        vehicle_speed = self.vehicle_speeds.get(courier.vehicle_type, 25)
        base_travel_time = (distance / vehicle_speed) * 60  # minutes
        
        # Apply traffic factor
        traffic_factor = self._get_traffic_factor(order_lat, order_lon, hour, day_of_week)
        adjusted_travel_time = base_travel_time * traffic_factor
        
        # Apply priority factor
        priority_factors = {
            'low': 1.0,
            'normal': 1.0,
            'high': 0.8,     # 20% faster
            'urgent': 0.6    # 40% faster
        }
        priority_factor = priority_factors.get(order.priority, 1.0)
        final_travel_time = adjusted_travel_time * priority_factor
        
        # Total delivery time
        total_time = self.base_preparation_time + timedelta(minutes=final_travel_time)
        
        return total_time
    
    def _get_traffic_factor(self, latitude: float, longitude: float, hour: int, day_of_week: int) -> float:
        """Get traffic delay factor based on location and time"""
        try:
            # Try to find delivery zone for this location
            # For simplicity, we'll use a basic time-based factor
            
            # Rush hour factors
            if day_of_week < 5:  # Weekday
                if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
                    return 1.5
                elif 10 <= hour <= 16:  # Business hours
                    return 1.2
                else:  # Off-peak
                    return 1.0
            else:  # Weekend
                if 12 <= hour <= 18:  # Weekend busy hours
                    return 1.3
                else:
                    return 1.0
                    
        except Exception as e:
            logger.error(f"Error calculating traffic factor: {e}")
            return 1.0
    
    def update_delivery_estimates(self, order: Order):
        """Update delivery time estimates for an order"""
        if order.courier:
            estimated_time = self.calculate_delivery_time(order)
            order.estimated_delivery_time = timezone.now() + estimated_time
            order.save()

class RouteService:
    """Service for getting real road routes instead of straight lines"""
    
    def __init__(self):
        # OpenRouteService API endpoint (free tier)
        self.api_base = "https://api.openrouteservice.org/v2/directions"
        # You can get a free API key from https://openrouteservice.org/
        self.api_key = getattr(settings, 'OPENROUTE_API_KEY', None)
        
        # Fallback to OSRM (Open Source Routing Machine) if no API key
        self.fallback_api = "https://router.project-osrm.org/route/v1"
        self.osrm_profile_map = {
            'driving-car': 'driving',
            'driving-hgv': 'driving',
            'cycling-regular': 'cycling',
            'foot-walking': 'walking'
        }

    def _translate_profile_for_osrm(self, profile: str) -> str:
        """Translate OpenRouteService-style profile to OSRM profile."""
        return self.osrm_profile_map.get(profile, 'driving')
    
    def get_route_coordinates(self, waypoints: List[Tuple[float, float]], 
                            profile: str = 'driving-car') -> List[Tuple[float, float]]:
        """
        Get real road route coordinates between waypoints
        
        Args:
            waypoints: List of (lat, lon) tuples
            profile: Routing profile (driving-car, driving-hgv, cycling-regular, etc.)
        
        Returns:
            List of coordinates forming the actual road route
        """
        if len(waypoints) < 2:
            return waypoints
        
        try:
            if not getattr(settings, 'EXTERNAL_ROUTING_ENABLED', True):
                return waypoints
            if self.api_key:
                return self._get_openroute_route(waypoints, profile)
            else:
                return self._get_osrm_route(waypoints, profile)
        except Exception as e:
            logger.warning(f"Failed to get real route, falling back to straight lines: {e}")
            return waypoints
    
    def _get_openroute_route(self, waypoints: List[Tuple[float, float]], 
                            profile: str) -> List[Tuple[float, float]]:
        """Get route using OpenRouteService API"""
        try:
            # Format coordinates for OpenRouteService
            coordinates = [[lon, lat] for lat, lon in waypoints]  # Note: OpenRouteService uses [lon, lat]
            
            url = f"{self.api_base}/{profile}"
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8'
            }
            
            payload = {
                'coordinates': coordinates,
                'instructions': False,
                'geometry': True,
                'elevation': False,
                'continue_straight': False
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'features' in data and data['features']:
                # Extract coordinates from the route geometry
                geometry = data['features'][0]['geometry']
                if geometry['type'] == 'LineString':
                    # Convert back to (lat, lon) format
                    return [(coord[1], coord[0]) for coord in geometry['coordinates']]
            
            return waypoints
            
        except Exception as e:
            logger.error(f"OpenRouteService API error: {e}")
            return waypoints
    
    def _get_osrm_route(self, waypoints: List[Tuple[float, float]], 
                        profile: str) -> List[Tuple[float, float]]:
        """Get route using OSRM (fallback, no API key required)"""
        try:
            osrm_profile = self._translate_profile_for_osrm(profile)
            # Format coordinates for OSRM
            coords_str = ';'.join([f"{lon},{lat}" for lat, lon in waypoints])
            
            url = f"{self.fallback_api}/{osrm_profile}/{coords_str}"
            params = {
                'overview': 'full',
                'geometries': 'geojson',
                'steps': 'false'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'routes' in data and data['routes']:
                # Extract coordinates from the route geometry
                geometry = data['routes'][0]['geometry']
                if geometry['type'] == 'LineString':
                    # Convert back to (lat, lon) format
                    return [(coord[1], coord[0]) for coord in geometry['coordinates']]
            
            return waypoints
            
        except Exception as e:
            logger.error(f"OSRM API error: {e}")
            return waypoints
    
    def get_route_summary(self, waypoints: List[Tuple[float, float]], 
                         profile: str = 'driving-car') -> Dict:
        """
        Get route summary with distance and duration
        
        Returns:
            Dict with 'distance' (km), 'duration' (minutes), 'coordinates'
        """
        try:
            if not getattr(settings, 'EXTERNAL_ROUTING_ENABLED', True):
                return self._calculate_straight_line_summary(waypoints)
            if self.api_key:
                return self._get_openroute_summary(waypoints, profile)
            else:
                return self._get_osrm_summary(waypoints, profile)
        except Exception as e:
            logger.warning(f"Failed to get route summary, using straight line calculation: {e}")
            return self._calculate_straight_line_summary(waypoints)
    
    def _get_openroute_summary(self, waypoints: List[Tuple[float, float]], 
                              profile: str) -> Dict:
        """Get route summary using OpenRouteService API"""
        try:
            coordinates = [[lon, lat] for lat, lon in waypoints]
            
            url = f"{self.api_base}/{profile}"
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8'
            }
            
            payload = {
                'coordinates': coordinates,
                'instructions': False,
                'geometry': True,
                'elevation': False,
                'continue_straight': False
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'features' in data and data['features']:
                route = data['features'][0]['properties']['summary']
                coordinates = self._get_openroute_route(waypoints, profile)
                
                return {
                    'distance': route['distance'] / 1000,  # Convert to km
                    'duration': route['duration'] / 60,    # Convert to minutes
                    'coordinates': coordinates
                }
            
            return self._calculate_straight_line_summary(waypoints)
            
        except Exception as e:
            logger.error(f"OpenRouteService summary error: {e}")
            return self._calculate_straight_line_summary(waypoints)
    
    def _get_osrm_summary(self, waypoints: List[Tuple[float, float]], 
                          profile: str) -> Dict:
        """Get route summary using OSRM"""
        try:
            osrm_profile = self._translate_profile_for_osrm(profile)
            coords_str = ';'.join([f"{lon},{lat}" for lat, lon in waypoints])
            
            url = f"{self.fallback_api}/{osrm_profile}/{coords_str}"
            params = {
                'overview': 'false',
                'geometries': 'geojson',
                'steps': 'false'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'routes' in data and data['routes']:
                route = data['routes'][0]
                coordinates = self._get_osrm_route(waypoints, profile)
                
                return {
                    'distance': route['distance'] / 1000,  # Convert to km
                    'duration': route['duration'] / 60,    # Convert to minutes
                    'coordinates': coordinates
                }
            
            return self._calculate_straight_line_summary(waypoints)
            
        except Exception as e:
            logger.error(f"OSRM summary error: {e}")
            return self._calculate_straight_line_summary(waypoints)
    
    def _calculate_straight_line_summary(self, waypoints: List[Tuple[float, float]]) -> Dict:
        """Fallback: calculate straight line distance and estimated time"""
        total_distance = 0
        for i in range(len(waypoints) - 1):
            lat1, lon1 = waypoints[i]
            lat2, lon2 = waypoints[i + 1]
            total_distance += GPSTracker.calculate_distance(lat1, lon1, lat2, lon2)
        
        # Estimate time based on average speed (25 km/h for city driving)
        estimated_time = (total_distance / 25) * 60  # minutes
        
        return {
            'distance': total_distance,
            'duration': estimated_time,
            'coordinates': waypoints
        }

class LogisticsManager:
    """Main logistics management class"""
    
    def __init__(self):
        self.gps_tracker = GPSTracker()
        self.route_optimizer = RouteOptimizer()
        self.geocoder = GeoCoder()
        self.delivery_calculator = DeliveryTimeCalculator()
    
    def assign_optimal_courier(self, order: Order) -> Optional[Courier]:
        """Find the best available courier for an order"""
        available_couriers = Courier.objects.filter(available=True)
        
        if not available_couriers:
            return None
        
        order_lat = order.latitude or order.client.latitude
        order_lon = order.longitude or order.client.longitude
        
        if not order_lat or not order_lon:
            # Geocode the address if coordinates are missing
            order_lat, order_lon = self.geocoder.geocode_address(order.address)
            if order_lat and order_lon:
                order.latitude = order_lat
                order.longitude = order_lon
                order.save()
        
        if not order_lat or not order_lon:
            # Return any available courier if geocoding fails
            return available_couriers.first()
        
        # Find nearest courier
        best_courier = None
        min_distance = float('inf')
        
        for courier in available_couriers:
            if courier.current_latitude and courier.current_longitude:
                distance = self.gps_tracker.calculate_distance(
                    courier.current_latitude, courier.current_longitude,
                    order_lat, order_lon
                )
                if distance < min_distance:
                    min_distance = distance
                    best_courier = courier
        
        return best_courier or available_couriers.first()
    
    def create_optimized_routes_for_day(self, date=None) -> List[DeliveryRoute]:
        """Create optimized routes for all pending orders"""
        if not date:
            date = timezone.now().date()
        
        # Get pending orders for the day
        pending_orders = Order.objects.filter(
            status__in=['new', 'assigned'],
            created_at__date=date
        ).select_related('client', 'courier')
        
        # Group orders by priority and location
        grouped_orders = self._group_orders_for_routing(pending_orders)
        
        routes = []
        for courier_id, orders in grouped_orders.items():
            try:
                courier = Courier.objects.get(id=courier_id, available=True)
                route = self.route_optimizer.create_delivery_route(courier, orders)
                routes.append(route)
                
                # Update order statuses and estimates
                for order in orders:
                    order.courier = courier
                    order.status = 'assigned'
                    self.delivery_calculator.update_delivery_estimates(order)
                    order.save()
                    
            except Courier.DoesNotExist:
                continue
        
        return routes
    
    def _group_orders_for_routing(self, orders: List[Order]) -> Dict[int, List[Order]]:
        """Group orders by optimal courier assignment"""
        grouped = {}
        
        for order in orders:
            # Try to use existing courier assignment or find optimal one
            courier = order.courier or self.assign_optimal_courier(order)
            
            if courier:
                if courier.id not in grouped:
                    grouped[courier.id] = []
                grouped[courier.id].append(order)
        
        return grouped
