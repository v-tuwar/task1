import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Optional

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

# Groq exposes an OpenAI-compatible API.
api_key = os.getenv("GROQ_API_KEY")
if not api_key or api_key == "your_groq_api_key_here":
    raise RuntimeError(
        "GROQ_API_KEY is missing. Set it in your .env file."
    )

MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
API_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2
MAX_HISTORY_MESSAGES = 10  # context window management: truncate to last N messages

client = OpenAI(api_key=api_key, base_url=BASE_URL, timeout=API_TIMEOUT_SECONDS)
_executor = ThreadPoolExecutor(max_workers=4)

app = FastAPI(title="StudyBuddy Memory Chatbot")
FRONTEND_DIR = BASE_DIR / "frontend"


@app.get("/")
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "message": "StudyBuddy backend is running!",
        "provider": "groq",
        "model": MODEL_NAME,
    }


# --------------------------------------------------
# SYSTEM PROMPT
# --------------------------------------------------

SYSTEM_PROMPT = """
You are StudyBuddy, a friendly AI study assistant.
Explain technical concepts in simple language.
Use examples when helpful.
Keep answers organized and beginner-friendly.
Remember relevant details from the conversation history.
Ask for clarification if a question is unclear.
""".strip()


# --------------------------------------------------
# CONVERSATION MEMORY (demo-only, in-memory)
# --------------------------------------------------

# History resets when the server restarts.
conversations: dict[str, list[dict[str, str]]] = {}


# --------------------------------------------------
# REQUEST / RESPONSE MODELS
# --------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str


# --------------------------------------------------
# GROQ CALL WITH TIMEOUT + LIMITED RETRIES
# --------------------------------------------------

def _call_model(messages):
    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=1024,
    )
    choice = completion.choices[0] if completion.choices else None
    text = (choice.message.content or "") if choice and choice.message else ""
    return text.strip()


def generate_response(messages):
    """
    Generate a response with per-attempt timeout and limited retries for
    transient connection/server/rate-limit errors.
    """
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            future = _executor.submit(_call_model, messages)
            return future.result(timeout=API_TIMEOUT_SECONDS)
        except FuturesTimeoutError as e:
            future.cancel()
            last_error = e
            if attempt == MAX_RETRIES:
                raise TimeoutError(
                    f"Groq request timed out after {API_TIMEOUT_SECONDS} seconds."
                ) from e
        except (openai.APITimeoutError, openai.APIConnectionError) as e:
            last_error = e
            if attempt == MAX_RETRIES:
                raise
        except openai.RateLimitError as e:
            last_error = e
            if attempt == MAX_RETRIES:
                raise
        except openai.InternalServerError as e:
            last_error = e
            if attempt == MAX_RETRIES:
                raise
    if last_error:
        raise last_error
    raise RuntimeError("Failed to generate a response.")


# --------------------------------------------------
# CHAT ENDPOINT
# --------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Please enter a message.")

    conversation_id = request.conversation_id or str(uuid.uuid4())
    history = conversations.setdefault(conversation_id, [])

    # Context window management: keep only the latest N messages.
    recent_history = history[-MAX_HISTORY_MESSAGES:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in recent_history:
        role = "assistant" if item.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": item.get("content", "")})
    messages.append({"role": "user", "content": message})

    try:
        reply = generate_response(messages)
        if not reply:
            raise HTTPException(
                status_code=502,
                detail="The AI service returned an empty response.",
            )

        # Save conversation only after a successful response.
        history.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply},
            ]
        )

        return ChatResponse(conversation_id=conversation_id, reply=reply)

    except HTTPException:
        raise
    except TimeoutError as e:
        print(f"Groq request timed out: {e}")
        raise HTTPException(
            status_code=504,
            detail="The AI service took too long to respond. Please try again.",
        )
    except openai.AuthenticationError as e:
        print(f"Groq auth error: {e}")
        raise HTTPException(
            status_code=502,
            detail="Groq authentication failed. Check your GROQ_API_KEY.",
        )
    except openai.RateLimitError as e:
        print(f"Groq rate limit: {e}")
        raise HTTPException(
            status_code=503,
            detail=(
                "The AI service is rate-limited or out of quota. "
                "Please try again shortly or check your Groq limits."
            ),
        )
    except (openai.APIConnectionError, openai.APITimeoutError) as e:
        print(f"Groq connection/timeout error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Could not reach the AI service. Please check your connection and try again.",
        )
    except openai.NotFoundError as e:
        print(f"Groq model error: {e}")
        raise HTTPException(
            status_code=502,
            detail=(
                "The configured model is unavailable. "
                "Set GROQ_MODEL in .env to a model your key can use."
            ),
        )
    except openai.APIError as e:
        print(f"Groq API error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502,
            detail="Groq API request failed. Check your API key, model access, and quota.",
        )
    except Exception as e:
        print(f"Unexpected chatbot error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again.",
        )
