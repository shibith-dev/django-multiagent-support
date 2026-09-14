from django.shortcuts import render
import json
from django.http import JsonResponse
import time
from django.shortcuts import get_object_or_404
from orders.models import Order
from .models import Conversation, Message
from .agents import run_support_agent
from django.contrib.admin.views.decorators import staff_member_required

# Create your views here.


def chat(request, order_id):
    if request.method == "POST":
        data = json.loads(request.body)
        user_message = data.get("message")

        if not user_message:
            return JsonResponse({"error": "No message recieved."}, status=400)

        # get the order details first
        order = get_object_or_404(Order, pk=order_id, user=request.user)

        # Get the conversation related to the order and the user, if not exist create one :
        conversation, created = Conversation.objects.get_or_create(
            user=request.user, order=order
        )

        # append the new user_message to the conversation :
        Message.objects.create(
            conversation=conversation, role="user", content=user_message
        )

        # Send user message and conversation to LLM
        agent_reply = run_support_agent(
            user_message, conversation.id, order.id, request.user.id
        )

        # store LLM Replay to db
        Message.objects.create(
            conversation=conversation, role="assistant", content=agent_reply
        )

        return JsonResponse({"response": agent_reply})


@staff_member_required
def dashboard(request):
    conversation = Conversation.objects.all().order_by("-created_at")
    context = {"conversations": conversation}
    return render(request, "support/dashboard.html", context)


def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    messages = conversation.messages.order_by("created_at")
    agentlogs = conversation.agentlogs.order_by("created_at")

    context = {
        "conversation": conversation,
        "messages": messages,
        "agentlogs": agentlogs,
    }

    return render(request, "support/conversation_detail.html", context)
