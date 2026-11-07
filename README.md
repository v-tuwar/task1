# StudyBuddy Memory Chatbot

A multi-turn chatbot with a **FastAPI** backend and web frontend, backed by **Groq's OpenAI-compatible API**. It keeps conversation history per session and applies context window management so the model can reference earlier messages.

## Features (assignment requirements)

- **Backend endpoint**: `POST /chat` accepts a user message (and optional `conversation_id`) and returns the model reply.
- **Multi-turn history per conversation**: messages are stored server-side by `conversation_id`; the frontend persists the ID in `sessionStorage` so a conversation continues across turns.
- **Context window management (truncation)**: only the most recent **10** stored messages are sent with each new request (`MAX_HISTORY_MESSAGES` in `backend/main.py`), keeping requests within a manageable context size while preserving recent turns.
- **System prompt**: StudyBuddy has a defined role/personality via a system message (friendly study assistant, clear explanations).
- **Error handling**: API/auth/rate-limit/connection errors and **timeouts** are handled. The backend enforces a per-request timeout and returns clear error messages; the frontend uses an `AbortController` timeout so the UI recovers instead of hanging.
- **Secrets in env vars**: the Groq API key is loaded from `GROQ_API_KEY` in `.env` (never hardcoded). `.env` is gitignored.

## Project structure

```text
backend/
  main.py          # FastAPI app, Groq calls, history + truncation
frontend/
  index.html       # Chat UI (served at /)
.env.example       # Template for environment variables
checkmodels.py     # Quick Groq connectivity check
requirements.txt
```

## Setup

1. **Python 3.10+** recommended.
2. Create/activate a virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Create `.env` from the template and add your key:

   ```powershell
   copy .env.example .env
   ```

   Edit `.env`:

   ```env
   GROQ_API_KEY=your_groq_api_key_here
   # Optional:
   # GROQ_MODEL=openai/gpt-oss-120b
   # GROQ_BASE_URL=https://api.groq.com/openai/v1
   ```

   Get a free key from [Groq Console](https://console.groq.com/keys). **Never commit `.env` or share your key.**

4. (Optional) Verify API access:

   ```powershell
   .\.venv\Scripts\python.exe .\checkmodels.py
   ```

## Run

From the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8001
```

Open [http://127.0.0.1:8001](http://127.0.0.1:8001) in your browser.

Endpoints:
- `GET /` — chat UI
- `GET /health` — health check (shows provider/model)
- `POST /chat` — `{ "message": "...", "conversation_id": "optional" }`

## Verifying multi-turn context

Before submitting, have a real conversation of **at least 5 turns** and confirm the bot can reference something said 2–3 messages earlier (the `conversation_id` is reused by the UI within the browser session).

## Notes / limitations

- Conversation history is **in-memory** and resets when the server restarts (demo scope).
- If you ever exposed a key, **rotate/revoke it** in the Groq console and update `.env`.
- If `POST /chat` returns an error, check the message shown in the UI/server logs (common causes: missing/invalid key, model access, quota/rate limits).
