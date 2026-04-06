# Multi Booking Agent

An AI-powered booking agent that lets users book movies, cabs, doctors, and restaurants through a natural language chat interface. Built as a production-quality portfolio project demonstrating async Python, distributed systems patterns, and LLM-driven agent design.

---

## What It Does

Users chat with an AI agent. The agent understands the intent behind the message and handles the full booking flow — selecting availability, processing payments, sending confirmations, and remembering preferences for future sessions.

**Supported booking types:**
- Movies — search showtimes, pick seats, confirm booking
- Cabs — request a ride, get fare estimate, track status
- Doctors — find available slots, book appointments
- Restaurants — check availability, make reservations

---

## How It Works

```
User message
    │
    ▼
FastAPI Chat Endpoint
    │
    ▼
LangChain AI Agent  ◄──── mem0 (long-term user preferences)
    │
    ├── Understands intent
    ├── Calls the right booking tool
    │
    ▼
Service Layer (movie / cab / doctor / restaurant)
    │
    ├── Redis distributed lock  →  prevents double bookings
    ├── MongoDB                 →  persists booking data
    ├── Idempotency check       →  prevents duplicate payments
    │
    ▼
Payment Service (Stripe mock)
    │
    ▼
Notification Service (Twilio mock SMS)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Pydantic v2 |
| Database | MongoDB via Motor (async) |
| Cache / Locks | Redis (asyncio) |
| AI Agent | LangChain + OpenAI |
| User Memory | mem0 |
| Payments | Stripe (mock) |
| Notifications | Twilio (mock SMS) |
| Validation | Pydantic v2 |

---

## Project Structure

```
app/
├── main.py                  # FastAPI app entry point
├── config.py                # Settings loaded from environment
├── database.py              # MongoDB connection
├── redis_client.py          # Redis connection
│
├── agent/
│   ├── agent.py             # LangChain agent setup
│   ├── tools.py             # Agent tools (one per booking type)
│   ├── memory.py            # mem0 integration
│   └── prompts.py           # System prompts
│
├── services/
│   ├── movie_service.py
│   ├── cab_service.py
│   ├── doctor_service.py
│   ├── restaurant_service.py
│   ├── payment_service.py
│   └── notification_service.py
│
├── routers/
│   ├── chat.py              # Main chat endpoint
│   ├── movie.py
│   ├── cab.py
│   ├── doctor.py
│   ├── restaurant.py
│   └── payment.py
│
├── models/
│   ├── user.py
│   ├── movie.py
│   ├── cab.py
│   ├── doctor.py
│   ├── restaurant.py
│   └── payment.py
│
├── core/
│   ├── redis_lock.py        # Distributed locking logic
│   ├── idempotency.py       # Idempotency key management
│   └── exceptions.py        # Custom exception classes
│
└── mocks/
    ├── razorpay_mock.py     # Fake payment responses
    └── twilio_mock.py       # Fake SMS responses
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url>
cd multi_booking_agent
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your actual values. See the [Environment Variables](#environment-variables) section below.

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

---

## Environment Variables

Copy `.env.example` to `.env` and replace each placeholder with your actual value.

| Variable | Description |
|---|---|
| `APP_ENV` | `development` or `production` |
| `SECRET_KEY` | Secret used for JWT token signing |
| `MONGO_URL` | MongoDB connection string |
| `MONGO_DB_NAME` | Name of the MongoDB database |
| `REDIS_URL` | Redis connection URL |
| `OPENAI_API_KEY` | OpenAI API key for the AI agent |
| `MEM0_API_KEY` | mem0 API key for user memory |
| `STRIPE_SECRET_KEY` | Stripe secret key (mock) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (mock) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID (mock) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (mock) |
| `TWILIO_PHONE_NUMBER` | Twilio sender phone number (mock) |

---

## Key Design Decisions

**Distributed locks via Redis** — Before any booking is confirmed, a Redis lock is acquired on the resource (seat, cab, time slot). This prevents two concurrent requests from double-booking the same item.

**Idempotent payments** — Every payment request carries a unique idempotency key stored in Redis. If the same request is retried (network failure, timeout), it returns the original result instead of charging again.

**Async throughout** — Motor (MongoDB) and redis[asyncio] keep every I/O operation non-blocking, allowing FastAPI to handle high concurrency without threading overhead.

**mem0 for memory** — The AI agent remembers user preferences (favourite seat type, dietary restrictions, preferred pickup location) across sessions without storing them in the main database.