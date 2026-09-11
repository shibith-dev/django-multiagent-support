from orders.models import Order, RefundRequest
from django.utils import timezone
from datetime import timedelta
from .tracking_data import DELIVERY_DATA



def get_order_details(order_id):
    try:
        order = Order.objects.get(pk=order_id)
        return  {
            "order_id": order.id,
            "product_name": order.product_name,
            "amount": str(order.amount),
            "status": order.status,
            "carrier": order.carrier,
            "tracking_number": order.tracking_number,
            "delivery_address": order.delivery,
            "ordered_on": order.created_at.strftime("%d %b %Y"),
            "days_since_order": (timezone.now() - order.created_at).days
        }
    except Order.DoesNotExist: 
        return {"error": f"Order #{order_id} not found."}


def get_refund_history(user_id):
    refunds = RefundRequest.objects.filter(user=user_id).order_by('-created_at')
    history = []
    for refund in refunds:
        history.append({
            "order_id": refund.order.id,
            "prodct": refund.order.product_name,
            "reason": refund.reason,
            "status": refund.status,
            "requested_on": refund.created_at.strftime("%d %b %Y")
        })
    return {
        "total_refund_requests": len(history),
        "history": history
    }


def get_delivery_status(tracking_id, carrier):
    default_response = {
        "status": "Unknown",
        "last_location": "Tracking info unavailabele",
        "last_update": "N/A",
        "estimated_delivery": "Contact Carrier Directly",
        "delay_reason": "No update from carrier",
    }
    result = DELIVERY_DATA.get(tracking_id, default_response)
    result['tracking_number'] = tracking_id
    result['carrier'] = carrier
    return result

def get_customer_risk_profile(user_id):
    refunds = RefundRequest.objects.filter(user=user_id)
    orders = Order.objects.filter(user=user_id)

    # Refund requests since last 90 days :
    recent_refunds = refunds.filter(created_at__gte=timezone.now() - timedelta(days=90)).count()
    denied = refunds.filter(status="denied").count()
    approved = refunds.filter(status="approved").count()
    pending = refunds.filter(status="pending").count()

    total_refund = refunds.count()
    total_orders = orders.count()

    if total_orders > 0:
        refund_to_orders_ratio = round(total_refund / total_orders, 2)
    else:
        refund_to_orders_ratio = 0

    return {
        "user_id": user_id,
        "total_orders": total_orders,
        "total_refund_requests": total_refund,
        "refund_last_90_days": recent_refunds,
        "denied": denied,
        "approved": approved,
        "pending": pending,
        "refund_to_order_ratio": refund_to_orders_ratio
    }