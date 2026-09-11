from decouple import config
from anthropic import Anthropic

client = Anthropic(
    api_key=config("ANTHROPIC_API_KEY"),  # This is the default and can be omitted
)

message = client.messages.create(
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "What is agentic ai",
        }
    ],

    model=config('ANTHROPIC_MODEL'),
)

print(message.content)