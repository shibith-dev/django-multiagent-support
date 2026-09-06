from django.shortcuts import render, get_object_or_404
from .models import Order, RefundRequest
from django.contrib.auth.decorators import login_required

# Create your views here.

@login_required
def orders(request):
    orders = Order.objects.filter(user=request.user)
    context ={
        "orders": orders
    }
    return render(request, 'orders_list.html', context) 

def order_details(request, order_id):
    print(order_id)
    order = get_object_or_404(Order, user=request.user, pk=order_id)
    refund = RefundRequest.objects.filter(order=order)
    context = {
        'order': order,
        'refunds': refund
    }
    return render(request, 'order_detail.html', context)
