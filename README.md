# LLM Chatbot with Key Failover and Response Caching

A full-stack AI chatbot with automatic API-key failover, LiteLLM response caching, SQLite multi-turn conversation memory, and per-request token tracking.

**Tech stack:** React · Python / FastAPI · SQLite · LiteLLM · Docker · Uvicorn

---

## 1. Live URLs

| Tier | Deployment | Live Production URL |
|---|---|---|
| **Frontend** | Vercel | [https://task-manager-fullstack-q1wv.vercel.app](https://task-manager-fullstack-q1wv.vercel.app) |
| **Backend** | Render | [https://llm-chatbot-backend-gyhi.onrender.com](https://llm-chatbot-backend-gyhi.onrender.com) |

---

## 2. How to Run Locally

### With Docker & Make (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/saksham121902/LLM-Chatbot.git
cd LLM-Chatbot

# 2. Copy the environment template and insert your API keys
cp .env.example .env
# Edit .env and set your keys (comma-separated, at least 2 keys):
# LLM_API_KEYS=your-first-key,your-second-key

# 3. Start the entire full-stack application (frontend on port 3000, backend on port 8000)
make up

# 4. To stop the containers
make down
```

### Without Docker

#### Backend (FastAPI + SQLite)

```bash
cd backend

# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
export DATABASE_URL=sqlite:///./app.db
export LLM_API_KEYS=your-first-key,your-second-key
export LLM_MODEL=groq/openai/gpt-oss-20b
export ALLOWED_ORIGINS=http://localhost:3000
export ENABLE_FAILURE_SIMULATION=true

# Start Uvicorn development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend (React)

```bash
cd frontend

# Install Node dependencies
npm install

# Point to local backend (or live Render endpoint)
export REACT_APP_API_URL=http://localhost:8000

# Start React development server
npm start
```

#### Run Backend Unit Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

---

## 3. Design Decisions

### Key Failover Strategy
- API keys are parsed from the comma-separated `LLM_API_KEYS` environment variable and assigned sequential identifiers (`key_1`, `key_2`, etc.).
- When handling `/chat` requests, the router sequentially attempts requests starting from `key_1`.
- If an API key encounters an HTTP 429 (rate limiting), quota depletion, 5xx upstream outage, or network timeout, the router logs the failure and automatically falls back to `key_2`.
- When `ENABLE_FAILURE_SIMULATION=true`, the `X-Simulate-Failure` header can simulate failure per-key (e.g. `key_1=429`, `key_1=429,key_2=500`, or `*=429`), allowing rigorous failover testing without quota exhaustion.
- If all configured keys fail, the request returns `503 {"detail": "all providers unavailable"}` and **rolls back** so that failed messages are never recorded in conversation history.

### Response Caching Strategy
- LiteLLM's response cache is initialized on application startup.
- The cache key incorporates the entire multi-turn message payload (system prompt + historical turns + new user message).
- On a cache hit:
  - `metadata.resolution_source` is set to `"LLM_CACHE"`.
  - Latency is near-instant (0–5 ms) with zero upstream API round-trip.
  - `metadata.key_id` is set to `null` and `metadata.fallback_attempts` is set to `0`.
- Repeating an identical prompt in a new session returns a cache hit, whereas modifying any preceding message in the multi-turn context triggers a live inference call.

### SQLite Multi-Turn Session Storage
- Messages are persisted in SQLite under the `messages` table containing `id`, `session_id`, `role`, `content`, `metadata` (JSON), and `created_at` (ISO-8601).
- In Docker environments, SQLite uses a persistent named volume mapped to `/data/app.db` ensuring data survives container restarts.
- Auto-fallback logic ensures database connectivity works seamlessly in local paths (`./app.db`) and non-root hosting containers.
- Conversations can be retrieved via `GET /sessions/{session_id}/messages`, returning all historical turns in chronological order (oldest first).

---

## 4. Verification & Testing

### 1. Health Check

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
# Response:
# {
#     "status": "ok",
#     "keys_configured": 2,
#     "cache_enabled": true
# }
```

### 2. Normal Chat (Live Inference)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-1", "message": "What is the capital of Italy?"}' | python3 -m json.tool
# Metadata will show:
# "resolution_source": "LIVE_INFERENCE",
# "key_id": "key_1",
# "fallback_attempts": 0
```

### 3. Failover Simulation (Key 1 Fails ➔ Key 2 Succeeds)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id": "test-session-2", "message": "What is the capital of Spain?"}' | python3 -m json.tool
# Metadata will show:
# "resolution_source": "LIVE_INFERENCE",
# "key_id": "key_2",
# "fallback_attempts": 1
```

### 4. Complete Outage Simulation (All Keys Fail ➔ HTTP 503)

```bash
curl -i -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id": "test-session-3", "message": "Hello"}'
# Response:
# HTTP/1.1 503 Service Unavailable
# {"detail": "all providers unavailable"}
```

### 5. Response Caching Verification

```bash
# First Call (Cold cache)
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "cache-test-1", "message": "Explain quantum computing in 5 words"}' | python3 -m json.tool

# Second Call with identical prompt in a new session (Cache hit)
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "cache-test-2", "message": "Explain quantum computing in 5 words"}' | python3 -m json.tool
# Metadata will show:
# "resolution_source": "LLM_CACHE",
# "key_id": null,
# "fallback_attempts": 0
```

### 6. Session History Retrieval

```bash
curl -s http://localhost:8000/sessions/test-session-1/messages | python3 -m json.tool
# Returns stored turns chronologically without the system prompt.
```

---

## 5. Setup Used

- **Code Editor:** VS Code
- **AI Tooling:** GitHub Copilot

---

## 6. Bonus Features

None implemented — strictly prioritized 100% contract compliance, key failover resilience, response caching, and frontend stability within the assignment scope.
