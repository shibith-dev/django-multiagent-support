from django.urls import path
from . import views

urlpatterns = [
    path('', views.orders, name='orders_list'),
    path('<int:order_id>', views.order_details, name='order_detail')
]