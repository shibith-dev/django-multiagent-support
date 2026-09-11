from django.shortcuts import render, get_object_or_404
from .models import Order, RefundRequest
from django.contrib.auth.decorators import login_required
from support.models import Conversation

# Create your views here.

@login_required
def orders(request):
    orders = Order.objects.filter(user=request.user)
    context ={
        "orders": orders
    }
    return render(request, 'orders_list.html', context) 

def order_details(request, order_id):

    order = get_object_or_404(Order, user=request.user, pk=order_id)
    refund = RefundRequest.objects.filter(order=order)

    #conversation History :
    try:
        conversation = Conversation.objects.get(user=request.user, order=order_id)
        previous_messages = conversation.messages.order_by("created_at")
    except Conversation.DoesNotExist:
        conversation = None
        previous_messages = []

    context = {
        'order': order,
        'refunds': refund,
        'conversation': conversation,
        'previous_messages': previous_messages
    }
    return render(request, 'order_detail.html', context)
