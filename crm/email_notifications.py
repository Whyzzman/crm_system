"""
Email notification система для CRM
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.models import User
from .models import Order, Client, Courier

logger = logging.getLogger('crm')


class EmailNotificationService:
    """Сервис для отправки email уведомлений"""
    
    @staticmethod
    def send_email(subject, template_name, context, recipient_list, html_template_name=None):
        """
        Базовый метод для отправки email
        """
        try:
            # Не отправляем, если список получателей пустой
            if not recipient_list:
                logger.info(f"Email не отправлен (нет получателей): {subject}")
                return False
            
            # Создаем текстовое содержимое
            text_content = render_to_string(template_name, context)
            
            # Создаем email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipient_list
            )
            
            # Добавляем HTML версию если указана
            if html_template_name:
                html_content = render_to_string(html_template_name, context)
                email.attach_alternative(html_content, "text/html")
            
            # Отправляем
            email.send()
            logger.info(f"Email отправлен: {subject} -> {recipient_list}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки email: {str(e)}")
            return False
    
    @classmethod
    def notify_order_created(cls, order):
        """Уведомление о создании заказа"""
        if not settings.EMAIL_NOTIFICATIONS.get('ORDER_CREATED', True):
            return False
            
        context = {
            'order': order,
            'client': order.client,
            'total_amount': order.total_price,
        }
        
        # Отправляем клиенту
        client_subject = f"Заказ #{order.id} создан - CRM System"
        cls.send_email(
            subject=client_subject,
            template_name='crm/emails/order_created_client.txt',
            html_template_name='crm/emails/order_created_client.html',
            context=context,
            recipient_list=[order.client.email] if order.client.email else []
        )
        
        # Отправляем менеджерам
        managers = User.objects.filter(is_staff=True, email__isnull=False)
        manager_emails = [user.email for user in managers if user.email]
        
        if manager_emails:
            manager_subject = f"Новый заказ #{order.id} - CRM System"
            cls.send_email(
                subject=manager_subject,
                template_name='crm/emails/order_created_manager.txt',
                html_template_name='crm/emails/order_created_manager.html',
                context=context,
                recipient_list=manager_emails
            )
    
    @classmethod
    def notify_order_status_changed(cls, order, old_status, new_status):
        """Уведомление об изменении статуса заказа"""
        if not settings.EMAIL_NOTIFICATIONS.get('ORDER_STATUS_CHANGED', True):
            return False
            
        context = {
            'order': order,
            'client': order.client,
            'old_status': old_status,
            'new_status': new_status,
            'total_amount': order.total_price,
        }
        
        if order.client.email:
            subject = f"Статус заказа #{order.id} изменен - CRM System"
            cls.send_email(
                subject=subject,
                template_name='crm/emails/order_status_changed.txt',
                html_template_name='crm/emails/order_status_changed.html',
                context=context,
                recipient_list=[order.client.email]
            )
    
    @classmethod
    def notify_payment_received(cls, payment):
        """Уведомление о получении платежа"""
        if not settings.EMAIL_NOTIFICATIONS.get('PAYMENT_RECEIVED', True):
            return False
            
        context = {
            'payment': payment,
            'order': payment.order,
            'client': payment.order.client,
        }
        
        if payment.order.client.email:
            subject = f"Платеж получен для заказа #{payment.order.id} - CRM System"
            cls.send_email(
                subject=subject,
                template_name='crm/emails/payment_received.txt',
                html_template_name='crm/emails/payment_received.html',
                context=context,
                recipient_list=[payment.order.client.email]
            )
    
    @classmethod
    def notify_delivery_assigned(cls, order, courier):
        """Уведомление о назначении курьера"""
        if not settings.EMAIL_NOTIFICATIONS.get('DELIVERY_ASSIGNED', True):
            return False
            
        context = {
            'order': order,
            'client': order.client,
            'courier': courier,
        }
        
        # Уведомляем клиента
        if order.client.email:
            subject = f"Курьер назначен для заказа #{order.id} - CRM System"
            cls.send_email(
                subject=subject,
                template_name='crm/emails/delivery_assigned_client.txt',
                html_template_name='crm/emails/delivery_assigned_client.html',
                context=context,
                recipient_list=[order.client.email]
            )
        
        # Уведомляем курьера
        if courier.email:
            subject = f"Новый заказ #{order.id} назначен вам - CRM System"
            cls.send_email(
                subject=subject,
                template_name='crm/emails/delivery_assigned_courier.txt',
                html_template_name='crm/emails/delivery_assigned_courier.html',
                context=context,
                recipient_list=[courier.email]
            )
    
    @classmethod
    def notify_delivery_completed(cls, order):
        """Уведомление о завершении доставки"""
        if not settings.EMAIL_NOTIFICATIONS.get('DELIVERY_COMPLETED', True):
            return False
            
        context = {
            'order': order,
            'client': order.client,
        }
        
        if order.client.email:
            subject = f"Заказ #{order.id} доставлен - CRM System"
            cls.send_email(
                subject=subject,
                template_name='crm/emails/delivery_completed.txt',
                html_template_name='crm/emails/delivery_completed.html',
                context=context,
                recipient_list=[order.client.email]
            )
    
    @classmethod
    def send_reminder_notification(cls, order, reminder_type="general"):
        """Отправка напоминания"""
        if not settings.EMAIL_NOTIFICATIONS.get('REMINDER_NOTIFICATIONS', True):
            return False
            
        context = {
            'order': order,
            'client': order.client,
            'reminder_type': reminder_type,
        }
        
        if order.client.email:
            subject = f"Напоминание по заказу #{order.id} - CRM System"
            cls.send_email(
                subject=subject,
                template_name='crm/emails/reminder_notification.txt',
                html_template_name='crm/emails/reminder_notification.html',
                context=context,
                recipient_list=[order.client.email]
            )
