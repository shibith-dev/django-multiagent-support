from anthropic import Anthropic
from django.conf import settings
from .tools import (
    get_order_details,
    get_refund_history,
    get_delivery_status,
    get_customer_risk_profile,
)
from .models import Conversation, AgentLog
from .event_queue import publish, DONE

# initialize gemini client
client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

model = settings.ANTHROPIC_MODEL

# SUPPORT - SYSTEM PROMPT :
SUPPORT_SYSTEM_PROMPT = """
You are Maya, a customer support agent at CoolBreeze AC.
You help customers with issues related to their AC orders.

Your Responsibilities :
 - Always use your tools to gather facts before responding.
 - Check order details when customer mentions their order.
 - Check refund history before making any refund decisions.
 - Be empathetic and honest.

Your Personality :
 - Friendly and Professional
 - Patient even when customer is angry
 - Clear and concise in your replies
 - No emojies

Important rules :
 - Always check order details first before responding
 - Never approve or deny a refund yourself
 - If refund decision is needed - tell customer you are checking with your team.
 - Never use bold text, bullet points, or any markdown formatting. Use plain text only.
 - Keep replies concise and conversational. Maximum 3-4 sentences. No longer paragraphs.
"""

# MANAGER - SYSTEM PROMPT
MANAGER_SYSTEM_PROMPT = """
You are a senior manager at CoolBreeze AC.
A support agent has escalated a customer case to you for a refund decision.

Your Responsibilities :
 - Review the case summary carefully
 - Consider the customer's refund history
 - Make a fair and final refund decision
 - Give a clear reason for your decision
 - You should be very careful before taking the decision because it is highly risk involved.

Your Decision Options :
 - Approve refund - If the case is genuine and within policy
 - Deny refund - If the case is suspicious or outside the policy
 - Escalate to risk team - if suspect fraud

Important rules : 
 - Be fair but firm
 - Base decision on facts - Not emotions
 - Always give a specific reason for your decision
 - Keep your response concise and professional
"""

# RISK - SYSTEM PROMPT :
RISK_SYSTEM_PROMPT = """
You are a fraud risk analyst at CoolBreeze AC.
A support manager has sent you a customer profile for risk assessment.

Your Job:
 - Analyse the customer's order and refund patterns
 - Identify suspicious behaviour
 - Return a clear risk verdict

Risk Levels:
 - LOW - genuine customer, normal behaviour
 - MEDIUM - Some suspicious signals, proceed with caution
 - HIGH - Clear fraud pattern, recommend denial

Your response format :
 - Risk Level: LOW / MEDIUM / HIGH
 - Key Signals: What you found suspicious or genuine
 - Recommendation: What manager should do

Important : 
 - Be objective - base verdict on data only
 - One bad refund does not make someone fraudulent 
 - Look for patterns - not isolated incidents
"""


# SUPPORT TOOLS - Tool schemas, that ai agents will read :
SUPPORT_TOOLS = [
    {
        "name": "get_order_details",
        "description": "Fetch complete order details including status, carrier, tracking number and days since order was placed. Use this when customer mentions their order or complains about delivery.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "The order ID to look up",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "get_refund_history",
        "description": "Get complete refund history of a user. Use this before making any refund related decisions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The user ID to check refund history for",
                }
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_delivery_status",
        "description": "Check current delivery status using tracking number and carrier. Use this when customer complaints about delayed or missing delivery.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tracking_number": {
                    "type": "string",
                    "description": "The shipment tracking number",
                },
                "carrier": {
                    "type": "string",
                    "description": "The carrier name for example BlueDart or Delhivery",
                },
            },
            "required": ["tracking_number", "carrier"],
        },
    },
    {
        "name": "escalate_to_manager",
        "description": "Escalate the case to the manager for a refund decision. Use this when customer requests a refund or compensation. Prepare a detailed case summary including order details, refund history and customer complaint before escalating.",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_summary": {
                    "type": "string",
                    "description": "Complete case summary including order details, refund history and customer complaint",
                }
            },
            "required": ["case_summary"],
        },
    },
]

MANAGER_TOOLS = [
    {
        "name": "assess_fraud_risk",
        "description":"Consult the risk agent to assess fraud risk for a customer. Use this when refund request looks suspicious or customer has multiple refund requests. Pass the user_id to get a risk verdict.",
        "input_schema":{
            "type":"object",
            "properties": {
                "user_id":{
                    "type": "integer",
                    "description": "The user ID to assess fraud risk for"
                }
            },
            "required": ["user_id"]
        }
    }
]

RISK_TOOLS = [
    {
        "name": "get_customer_risk_profile",
        "description": "Get complete risk profile for a customer including order history, refund, patterns, and ratio. Use this to assess fraud risk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The user ID to assess risk for",
                }
            },
            "required": ["user_id"],
        },
    }
]


# execute_tool - bridge between model and tools :
def execute_tool(tool_name, tool_input, conversation_id):
    if tool_name == "get_order_details":
        return get_order_details(tool_input["order_id"])
    
    if tool_name == "get_refund_history":
        return get_refund_history(tool_input["user_id"])
    
    if tool_name == "get_delivery_status":
        return get_delivery_status(tool_input["tracking_number"], tool_input["carrier"])
    
    if tool_name == "escalate_to_manager":
        return run_manager_agent(tool_input["case_summary"], conversation_id)
    
    if tool_name == "assess_fraud_risk":
        return run_risk_agent(tool_input["user_id"], conversation_id)
    
    if tool_name == "get_customer_risk_profile":
        return get_customer_risk_profile(tool_input["user_id"])


# Agent Loop - While loop that loops until the task is done
def run_support_agent(user_message, conversation_id, order_id, user_id):

    # get the conversation containing the latest client query:
    conversation = Conversation.objects.get(pk=conversation_id)

    # Lets prepare the conversation in a proper format to send to claude :
    conversation_messages = []
    for message in conversation.messages.order_by("created_at"):
        conversation_messages.append({"role": message.role, "content": message.content})

    while True:
        # we will send this conversation to LLM
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SUPPORT_SYSTEM_PROMPT
            + f"\n\nContext: This conversation is about the order id: {order_id}, user: {user_id}",
            tools=SUPPORT_TOOLS,
            messages=conversation_messages,
        )

        # if the model stoped due to get any resource from any tool then execute that tool :
        if response.stop_reason == "tool_use":
            tool_result = []
            for block in response.content:
                if block.type == "tool_use":

                    event = {"type": "tool_call", "message": f'calling tool {block.name} with {block.input}.'}
                    publish(conversation_id, event)

                    # Log the tool call:
                    AgentLog.objects.create(conversation=conversation, event_type="tool_call", message=f'calling tool {block.name} with {block.input}.')

                    # execute the tool :
                    result = execute_tool(block.name, block.input, conversation.id)

                    event = {"type": "tool_result", "message": f"{block.name} returned: {str(result)[:200]}"}
                    publish(conversation_id, event)

                    # log the tool result :
                    AgentLog.objects.create(conversation=conversation, event_type="tool_result", message=f"{block.name} returned: {str(result)[:200]}")

                    tool_result.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }
                    )
            conversation_messages.append(
                {"role": "assistant", "content": response.content}
            )
            conversation_messages.append({"role": "user", "content": tool_result})
        else:
            final_reply = response.content[0].text

            # publish final event to the queue :
            event = {"type": "final", "message": final_reply}
            publish(conversation_id, event)
            publish(conversation_id, DONE) # closes the live stream after all logs are streamed
            # log final reply :
            AgentLog.objects.create(conversation=conversation, event_type="final", message=final_reply)
            return final_reply


def run_manager_agent(case_summary, conversation_id):
    conversation = Conversation.objects.get(pk=conversation_id)

    event = {"type": "manager", "message": f"Case received for review: {case_summary[:200]}"}
    publish(conversation_id, event)

    # log manager message :
    AgentLog.objects.create(conversation=conversation, event_type="manager", message=f"Case received for review: {case_summary[:200]}")
    manager_messages = [{"role": "user", "content": case_summary}]

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=MANAGER_SYSTEM_PROMPT,
            tools=MANAGER_TOOLS,
            messages=manager_messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":

                    event = {"type": "manager", "message": f"consulting risk agent for fraud assessment."}
                    publish(conversation_id, event)

                    # log manager tool call :
                    AgentLog.objects.create(conversation=conversation, event_type="manager", message=f"consulting risk agent for fraud assessment.")

                    result = execute_tool(block.name, block.input, conversation.id)

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }
                    )

            manager_messages.append({"role": "assistant", "content": response.content})

            manager_messages.append({"role": "user", "content": tool_results})
        else:

            event = {"type": "manager", "message": f"Decision: {response.content[0].text[:200]}"}
            publish(conversation_id, event)

            # Log manager final decision
            AgentLog.objects.create(conversation=conversation, event_type="manager", message=f"Decision: {response.content[0].text[:200]}")
            return response.content[0].text


def run_risk_agent(user_id, conversation_id):

    conversation = Conversation.objects.get(pk=conversation_id)

    event = {"type": "risk", "message": f"Case received for fraud assessment on user: {user_id}"}
    publish(conversation_id, event)

    # log risk assessment call :
    AgentLog.objects.create(conversation=conversation, event_type="risk", message=f"Case received for fraud assessment on user: {user_id}")

    risk_messages = [
        {
            "role": "user",
            "content": f"please assess the fraud risk for user ID {user_id}. Use your tool to get their profile and return a verdict.",
        }
    ]

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=RISK_SYSTEM_PROMPT,
            tools=RISK_TOOLS,
            messages=risk_messages,
        )

        if response.stop_reason == "tool_use":
            tool_messages = []
            for block in response.content:
                if block.type == "tool_use":

                    event = {"type": "risk", "message": f"Calling {block.name} to get customer risk profile."}
                    publish(conversation_id, event)

                    # Log tool call :
                    AgentLog.objects.create(conversation=conversation, event_type="risk", message=f"Calling {block.name} to get customer risk profile.")
                    result = execute_tool(block.name, block.input, conversation_id)

                    tool_messages.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }
                    )

            risk_messages.append({"role": "assistant", "content": response.content})

            risk_messages.append({"role": "user", "content": tool_messages})

        else:

            event = {"type": "risk", "message": f"Verdict : {response.content[0].text[:200]}"}
            publish(conversation_id, event)

            # log risk assessment final verdict :
            AgentLog.objects.create(conversation=conversation, event_type="risk", message=f"Verdict : {response.content[0].text[:200]}")
            return response.content[0].text
