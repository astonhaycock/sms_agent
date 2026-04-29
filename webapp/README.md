# Web Application

FastAPI backend + HTML frontend for the Off-Grid AI Agent user portal.

## Structure

```
webapp/
├── api.py              # FastAPI backend (auth, SMS webhook, user/settings/stats endpoints)
├── database.py         # SQLite database layer (pysqlite3)
├── hash_password.py    # Password hash utility
└── frontend/
    ├── index.html      # Public landing page
    ├── login.html      # Login and registration
    ├── dashboard.html  # User dashboard
    ├── settings.html   # User settings
    ├── admin.html      # Admin panel
    └── static/         # Images, CSS, JS assets
```

## Running

Preferred — start from the project root, which also starts the agent router:
```bash
uv run main.py
```

Webapp only (from project root):
```bash
cd webapp && uvicorn api:app --reload --port 8000
```

Server starts at http://localhost:8000.

## Database

SQLite via pysqlite3. File: `offgrid_agent.db` (auto-created at startup, path configurable via `DATABASE_PATH` env var).

Stores:
- User accounts (username, email, bcrypt password hash, phone number)
- SMS message history (inbound/outbound)
- User settings and preferences
- Per-user encrypted cloud LLM API keys
- Usage statistics

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login, returns JWT |
| POST | `/api/auth/token` | OAuth2 token endpoint |
| GET | `/api/auth/me` | Current user (protected) |

### User
| Method | Path | Description |
|--------|------|-------------|
| PUT | `/api/users/phone` | Update phone number (protected) |

### Messages
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/messages` | User SMS history (protected) |
| POST | `/api/messages/log` | Log a message (protected) |

### Stats
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats` | Usage statistics (protected) |

### Settings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | All user settings (protected) |
| GET | `/api/settings/{key}` | Single setting (protected) |
| PUT | `/api/settings` | Update setting (protected) |

### Gmail OAuth
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/gmail/callback` | Google OAuth2 callback |

## Security

- JWT authentication (configurable expiry via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- bcrypt password hashing with salt
- Rate limiting: 10 login/min, 5 register/hour per IP
- Account lockout after 5 failed attempts (15-minute lock)
- Security headers: CSP, HSTS, X-Frame-Options, XSS protection
- Encrypted per-user credential storage (cloud API keys)

## First Time Setup

1. Copy `.env.example` to `.env` and fill in required values.
2. Start the server — the database is created automatically.
3. Go to http://localhost:8000/login and register your account.
4. Add your phone number in the dashboard to authorize SMS access.

## Development

The server runs with `--reload` by default so changes to `api.py` restart automatically. Frontend changes (HTML/CSS) take effect on browser refresh.

Regenerate a password hash manually:
```bash
python hash_password.py yourpassword
```
