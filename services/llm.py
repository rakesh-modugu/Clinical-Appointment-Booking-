"""
LLM service wrapper — generates agent responses from conversation history.
Supports OpenAI GPT-4o and Groq (Llama 3) interchangeably.
"""

import openai
from core.config import settings

SYSTEM_PROMPT = (
    "You are a helpful, concise voice AI assistant. "
    "Keep responses under 3 sentences unless more detail is explicitly requested."
)


async def generate_response(user_text: str, history: list[dict]) -> str:
    """
    Generate an LLM response given the latest user message and conversation history.
    history: list of {"role": "user"|"assistant", "content": str}
    Returns: assistant response string.
    """
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=256,
    )
    return response.choices[0].message.content.strip()
