# Quick Start Guide

## Starting the Server

```bash
uv sync          # first time only
uv run main.py   # starts webapp :8000 and agent router :3002
```

## First Time Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Copy and fill in your environment file:
   ```bash
   cp .env.example .env
   # Edit .env — Twilio keys are required; everything else is optional
   ```

3. Start the server:
   ```bash
   uv run main.py
   ```

4. Open your browser:
   - Landing page: http://localhost:8000
   - Register an account: http://localhost:8000/login

## Pages

| Page | URL |
|------|-----|
| Landing | http://localhost:8000 |
| Login / Register | http://localhost:8000/login |
| Dashboard | http://localhost:8000/dashboard |
| Settings | http://localhost:8000/settings |
| Admin | http://localhost:8000/admin |
| API Docs | http://localhost:8000/docs |

## Common Tasks

**Regenerate a password hash:**
```bash
python webapp/hash_password.py your_password
```

**Kill a port that's already in use:**
```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:3002 | xargs kill -9
```

**Stop the server:** `Ctrl+C`

## Troubleshooting

**Module not found:**
```bash
uv sync
```

**Can't connect to server:**
- Confirm the server is running (`uv run main.py`)
- Confirm you're on http://localhost:8000
- Check terminal output for errors

**API endpoint test:**
```
GET http://localhost:8000/api
```
Should return a JSON status response.

## Docker

```bash
./build.sh
```

See `README.md` for full Docker details and environment variable reference.
