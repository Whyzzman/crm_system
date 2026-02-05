from django.contrib import admin
from django.urls import path, include  # додали include
from crm import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('crm.urls')),  # підключили urls з додатку crm
]