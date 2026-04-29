from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import asyncio
import jwt
import os
import secrets
import hashlib
import base64
from email.mime.text import MIMEText
import urllib.request
import json as _json
from dotenv import load_dotenv
from database import db

# Encryption (for API keys and Gmail tokens at rest)
from cryptography.fernet import Fernet

# Twilio (optional — webapp still runs if SMS isn't configured)
try:
    from twilio.rest import Client as _TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

WELCOME_SMS = (
    "Hi! I'm your Off-Grid AI Agent. Text me anytime for:\n"
    "- Weather forecasts\n"
    "- Web search (news, hours, prices)\n"
    "- First aid guidance\n"
    "- Camping advice\n"
    "- Trail info (routes, maps, safety)\n"
    "- Gmail (check/reply to emails)\n"
    "Reply HELP for commands, or LIST TRAILS to see parks. CLEAR resets the chat."
)


def _send_welcome_sms(phone_number: str) -> None:
    """Send a one-time welcome SMS. Never raises — failures are logged."""
    if not TWILIO_AVAILABLE:
        print(f"[welcome SMS] twilio package not installed; skipping for {phone_number}")
        return
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
        print(f"[welcome SMS] Twilio env vars missing; skipping for {phone_number}")
        return
    try:
        client = _TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=WELCOME_SMS,
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number,
        )
        print(f"[welcome SMS] sent to {phone_number} (SID: {msg.sid})")
    except Exception as e:
        print(f"[welcome SMS] failed for {phone_number}: {e}")

# Gmail OAuth (optional - only if Google credentials are configured)
try:
    from google_auth_oauthlib.flow import Flow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# Load environment variables
load_dotenv()

# Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY environment variable is required! "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Google / Gmail configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8080/api/gmail/callback")
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

# ── Encryption helpers ──────────────────────────────────────────────────────
def _get_fernet() -> Fernet:
    raw = hashlib.sha256(SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))

def encrypt_value(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()

def decrypt_value(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()

def make_key_hint(key: str) -> str:
    key = key.strip()
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "****" + key[-4:]

# CORS Configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")
if ENVIRONMENT == "production" and "http://localhost:8000" in ALLOWED_ORIGINS:
    raise ValueError("Production environment must not allow localhost origins!")

# Rate limiting configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, enabled=RATE_LIMIT_ENABLED)

# Initialize FastAPI
app = FastAPI(
    title="Off-Grid AI Agent API", 
    version="1.0.0",
    docs_url="/docs" if ENVIRONMENT == "development" else None,  # Disable docs in production
    redoc_url="/redoc" if ENVIRONMENT == "development" else None
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Get the directory where this script is located
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

# CORS middleware with restricted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # HSTS (HTTP Strict Transport Security) - only in production with HTTPS
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "media-src 'self'; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "frame-ancestors 'none';"
    )
    
    return response

# Mount static files (images, css, js)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

# Models
class User(BaseModel):
    id: Optional[int] = None
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    created_at: Optional[str] = None
    last_login: Optional[str] = None
    is_active: Optional[bool] = True

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.isalnum() and '_' not in v:
            raise ValueError('Username must be alphanumeric with optional underscores')
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if len(v) > 50:
            raise ValueError('Username must not exceed 50 characters')
        return v
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password must not exceed 72 characters')
        
        # Check for complexity
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)
        
        if not (has_upper and has_lower and has_digit):
            raise ValueError('Password must contain uppercase, lowercase, and numbers')
        
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

def normalize_phone_to_e164(phone: str) -> str:
    """Normalize to E.164 for storage and Twilio/LangGraph (+14357733009)."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        return phone  # let validator reject
    if len(digits) == 10:
        return "+1" + digits  # US/Canada
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits


class PhoneNumberUpdate(BaseModel):
    phone_number: str

    @validator("phone_number")
    def validate_and_normalize_phone(cls, v):
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        return normalize_phone_to_e164(v)

class SettingUpdate(BaseModel):
    key: str
    value: str

class SMSMessage(BaseModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    phone_number: str
    message_text: str
    direction: str
    timestamp: Optional[str] = None

class WatchedSenderRequest(BaseModel):
    email_address: str
    display_name: Optional[str] = None

    @validator("email_address")
    def valid_email(cls, v):
        v = v.strip().lower()
        if "@" not in v:
            raise ValueError("Must be a valid email address")
        return v

class LLMKeyRequest(BaseModel):
    provider: str
    api_key: str

    @validator("provider")
    def valid_provider(cls, v):
        if v not in ("claude", "openai", "gemini"):
            raise ValueError("provider must be claude, openai, or gemini")
        return v

    @validator("api_key")
    def key_not_empty(cls, v):
        if not v.strip():
            raise ValueError("api_key must not be empty")
        return v.strip()

class GmailReplyRequest(BaseModel):
    thread_id: str
    message_id: str
    to: str
    subject: str
    body: str

# Helper functions
def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user with account lockout protection"""
    user_dict = db.get_user_by_username(username)
    if not user_dict:
        return None
    
    # Check if account is locked
    if db.is_account_locked(username):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked due to too many failed login attempts. Please try again in 15 minutes."
        )
    
    if not user_dict.get('is_active'):
        return None
    
    # Verify password
    if not db.verify_password(password, user_dict['password_hash']):
        # Increment failed login attempts
        failed_attempts = db.increment_failed_login(username)
        
        if failed_attempts >= 5:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Too many failed login attempts. Account locked for 15 minutes."
            )
        
        remaining = 5 - failed_attempts
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Incorrect password. {remaining} attempts remaining before account lockout."
        )
    
    # Update last login and reset failed attempts
    db.update_last_login(user_dict['id'])
    
    return user_dict

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user_dict = db.get_user_by_username(username)
    if user_dict is None:
        raise credentials_exception
    return user_dict

async def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Ensure user is active"""
    if not current_user.get('is_active'):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# API Routes
@app.get("/api")
async def api_root():
    """API root endpoint - returns JSON"""
    return {
        "message": "Off-Grid AI Agent API",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/api/auth/register", response_model=Token)
@limiter.limit("5/hour")  # Limit registration to 5 per hour per IP
async def register(request: Request, user_data: UserCreate):
    """Register a new user"""
    print(f"Registration attempt for username: {user_data.username}")
    
    # Check if username exists
    if db.get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists
    if db.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user_id = db.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name
    )
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    
    print(f"User registered successfully: {user_data.username}")
    
    # Auto-login after registration
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_data.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=Token)
@limiter.limit("10/minute")  # Limit login attempts to 10 per minute per IP
async def login(request: Request, login_data: LoginRequest):
    """Login endpoint - returns JWT token"""
    print(f"Login attempt for username: {login_data.username}")
    
    try:
        user_dict = authenticate_user(login_data.username, login_data.password)
        
        if not user_dict:
            print(f"Login failed for username: {login_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_dict['username']}, expires_delta=access_token_expires
        )
        
        print(f"Login successful for username: {login_data.username}")
        return {"access_token": access_token, "token_type": "bearer"}
    
    except HTTPException:
        raise

@app.post("/api/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible token endpoint"""
    user_dict = authenticate_user(form_data.username, form_data.password)
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_dict['username']}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
async def read_users_me(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get current user information"""
    # Don't send password hash to client
    user_response = {
        "id": current_user['id'],
        "username": current_user['username'],
        "email": current_user['email'],
        "full_name": current_user.get('full_name'),
        "phone_number": current_user.get('phone_number'),
        "created_at": current_user.get('created_at'),
        "last_login": current_user.get('last_login'),
        "is_active": current_user.get('is_active')
    }
    return user_response

@app.put("/api/users/phone")
async def update_phone_number(
    phone_data: PhoneNumberUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update user's phone number. Sends a welcome SMS the first time a number is set."""
    # Snapshot the previous phone so we can detect first-time setup.
    previous_phone = (current_user.get('phone_number') or "").strip()
    is_first_time = not previous_phone

    success = db.update_user_phone(current_user['id'], phone_data.phone_number)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update phone number. It may already be in use."
        )

    # phone_data.phone_number is already E.164 from validator
    if is_first_time:
        # Fire-and-forget so the API responds immediately even if Twilio is slow.
        asyncio.create_task(asyncio.to_thread(_send_welcome_sms, phone_data.phone_number))

    return {"message": "Phone number updated successfully", "phone_number": phone_data.phone_number}

# SMS Agent specific endpoints (protected)
@app.get("/api/messages")
async def get_messages(
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get user's SMS messages"""
    messages = db.get_user_messages(current_user['id'], limit)
    return {
        "messages": messages,
        "count": len(messages)
    }

@app.post("/api/messages/log")
async def log_message(
    message: SMSMessage,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Log an SMS message (for integration with SMS system)"""
    message_id = db.log_sms_message(
        user_id=current_user['id'],
        phone_number=message.phone_number,
        message_text=message.message_text,
        direction=message.direction
    )

    return {"message_id": message_id, "status": "logged"}

@app.delete("/api/messages")
async def clear_messages(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Permanently delete all of the current user's SMS history."""
    deleted = db.clear_user_messages(current_user['id'])
    # Also clear any pending follow-up hold so the next inbound SMS starts fresh.
    phone = (current_user.get('phone_number') or "").strip()
    if phone:
        try:
            db.remove_follow_up_hold(phone)
        except Exception as e:
            print(f"[clear_messages] follow_up_hold cleanup failed for user {current_user['id']}: {e}")
    return {"deleted": deleted}


class DeleteAccountRequest(BaseModel):
    confirmation: str
    password: str


@app.delete("/api/users/me")
async def delete_account(
    req: DeleteAccountRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Permanently delete the current user's account and all associated data.

    Requires the literal string 'DELETE' and the user's current password to guard
    against accidental or session-hijack deletion.
    """
    if req.confirmation != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase must be exactly 'DELETE'.",
        )
    # Re-verify the password — the JWT alone shouldn't be enough for a destructive op.
    # Use db.verify_password directly to avoid authenticate_user's login-flow side effects
    # (lockout counter, 401 with login-attempt messaging) which would also trigger the
    # frontend's auto-redirect-on-401 and obscure the real error.
    if not db.verify_password(req.password, current_user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect.",
        )
    success = db.delete_user(current_user['id'])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account.",
        )
    return {"deleted": True, "user_id": current_user['id']}

@app.get("/api/stats")
async def get_stats(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get user statistics"""
    stats = db.get_user_stats(current_user['id'])
    return stats

@app.get("/api/settings")
async def get_settings(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get all user settings"""
    settings = db.get_all_user_settings(current_user['id'])
    return {"settings": settings}

@app.get("/api/settings/{key}")
async def get_setting(
    key: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get a specific user setting"""
    value = db.get_user_setting(current_user['id'], key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"key": key, "value": value}

@app.put("/api/settings")
async def update_setting(
    setting: SettingUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update a user setting"""
    success = db.set_user_setting(current_user['id'], setting.key, setting.value)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update setting"
        )
    
    return {"message": "Setting updated successfully", "key": setting.key, "value": setting.value}

# ── Gmail helpers ──────────────────────────────────────────────────────────

def _gmail_state_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "type": "gmail_oauth",
                "exp": datetime.utcnow() + timedelta(minutes=10)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def _verify_gmail_state(state: str) -> Optional[int]:
    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "gmail_oauth":
            return None
        return int(payload["sub"])
    except Exception:
        return None

def _get_gmail_service(user_id: int):
    if not GMAIL_AVAILABLE:
        raise HTTPException(status_code=501, detail="Gmail libraries not installed")
    token_data = db.get_gmail_tokens(user_id)
    if not token_data:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    access_token  = decrypt_value(token_data["access_token"])
    refresh_token = decrypt_value(token_data["refresh_token"]) if token_data.get("refresh_token") else None
    creds = Credentials(
        token=access_token, refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID, client_secret=GOOGLE_CLIENT_SECRET,
        scopes=GMAIL_SCOPES,
    )
    if creds.expired and refresh_token:
        creds.refresh(GoogleRequest())
        db.save_gmail_tokens(
            user_id=user_id,
            access_token=encrypt_value(creds.token),
            refresh_token=encrypt_value(creds.refresh_token) if creds.refresh_token else token_data["refresh_token"],
            gmail_address=token_data.get("gmail_address"),
            token_expiry=creds.expiry.isoformat() if creds.expiry else None,
        )
    return build("gmail", "v1", credentials=creds)

def _extract_email_body(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    if body_data and mime_type == "text/plain":
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_email_body(part)
        if result:
            return result
    return ""

def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


# ── LLM API Key endpoints ────────────────────────────────────────────────────

@app.post("/api/llm-keys")
async def save_llm_key(
    req: LLMKeyRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    encrypted = encrypt_value(req.api_key)
    hint = make_key_hint(req.api_key)
    success = db.save_llm_api_key(current_user["id"], req.provider, encrypted, hint)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save API key")
    return {"message": f"{req.provider} API key saved", "key_hint": hint}

@app.get("/api/llm-keys/status")
async def get_llm_keys_status(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    return {"providers": db.get_all_llm_keys_status(current_user["id"])}

@app.delete("/api/llm-keys/{provider}")
async def delete_llm_key(
    provider: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    if provider not in ("claude", "openai", "gemini"):
        raise HTTPException(status_code=400, detail="Invalid provider")
    db.delete_llm_api_key(current_user["id"], provider)
    # If the deleted provider was active, fall back to local
    if db.get_user_setting(current_user["id"], "active_provider") == provider:
        db.set_user_setting(current_user["id"], "active_provider", "local")
    return {"message": f"{provider} API key removed"}


class LLMProviderRequest(BaseModel):
    provider: str  # 'local', 'claude', 'openai', 'gemini'

    @validator("provider")
    def valid_provider(cls, v):
        if v not in ("local", "claude", "openai", "gemini"):
            raise ValueError("provider must be local, claude, openai, or gemini")
        return v


@app.get("/api/llm-provider")
async def get_active_provider(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    provider = db.get_user_setting(current_user["id"], "active_provider") or "local"
    return {"provider": provider}


@app.put("/api/llm-provider")
async def set_active_provider(
    req: LLMProviderRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    # Cloud providers require a saved key
    if req.provider != "local":
        key_data = db.get_llm_api_key(current_user["id"], req.provider)
        if not key_data:
            raise HTTPException(
                status_code=400,
                detail=f"No API key saved for {req.provider}. Add a key first."
            )
    db.set_user_setting(current_user["id"], "active_provider", req.provider)
    return {"provider": req.provider}


@app.get("/api/ollama-models")
async def get_ollama_models(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=5) as resp:
            data = _json.loads(resp.read())
        # Exclude embedding-only models
        models = [
            m["name"] for m in data.get("models", [])
            if "embed" not in m["name"].lower()
        ]
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not reach Ollama: {e}")


class LocalModelRequest(BaseModel):
    model: str


@app.get("/api/local-model")
async def get_local_model(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    model = db.get_user_setting(current_user["id"], "local_model") or os.getenv("DEFAULT_LOCAL_MODEL", "glm-4.7-flash")
    return {"model": model}


@app.put("/api/local-model")
async def set_local_model(
    req: LocalModelRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    if not req.model.strip():
        raise HTTPException(status_code=400, detail="Model name cannot be empty")
    db.set_user_setting(current_user["id"], "local_model", req.model.strip())
    return {"model": req.model.strip()}


# ── Gmail OAuth endpoints ────────────────────────────────────────────────────

@app.get("/api/gmail/auth-url")
async def gmail_auth_url(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    if not GMAIL_AVAILABLE:
        raise HTTPException(status_code=501, detail="Gmail libraries not installed")
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
    state = _gmail_state_token(current_user["id"])
    flow = Flow.from_client_config(
        {"web": {"client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": "https://oauth2.googleapis.com/token",
                 "redirect_uris": [GOOGLE_REDIRECT_URI]}},
        scopes=GMAIL_SCOPES, state=state, redirect_uri=GOOGLE_REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    # Save PKCE code_verifier so the callback can use it (library auto-generates it)
    code_verifier = getattr(flow, "code_verifier", None) or getattr(flow.oauth2session, "_code_verifier", None)
    if code_verifier:
        db.set_user_setting(current_user["id"], "_gmail_pkce", code_verifier)
    return {"auth_url": auth_url}

@app.get("/api/gmail/callback")
async def gmail_callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return RedirectResponse(url="/settings?gmail=error")
    user_id = _verify_gmail_state(state)
    if not user_id:
        return RedirectResponse(url="/settings?gmail=error")
    try:
        print(f"[gmail_callback] step1: building flow for user_id={user_id}")
        flow = Flow.from_client_config(
            {"web": {"client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
                     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                     "token_uri": "https://oauth2.googleapis.com/token",
                     "redirect_uris": [GOOGLE_REDIRECT_URI]}},
            scopes=GMAIL_SCOPES, state=state, redirect_uri=GOOGLE_REDIRECT_URI,
        )
        print(f"[gmail_callback] step2: fetching token")
        code_verifier = db.get_user_setting(user_id, "_gmail_pkce") or None
        if code_verifier:
            db.set_user_setting(user_id, "_gmail_pkce", "")
        await asyncio.wait_for(
            asyncio.to_thread(flow.fetch_token, code=code, code_verifier=code_verifier),
            timeout=30
        )
        print(f"[gmail_callback] step3: token fetched, building gmail service")
        creds = flow.credentials
        gmail_service = await asyncio.to_thread(build, "gmail", "v1", credentials=creds)
        print(f"[gmail_callback] step4: getting gmail profile")
        profile = await asyncio.to_thread(lambda: gmail_service.users().getProfile(userId="me").execute())
        print(f"[gmail_callback] step5: saving tokens for {profile.get('emailAddress')}")
        db.save_gmail_tokens(
            user_id=user_id,
            access_token=encrypt_value(creds.token),
            refresh_token=encrypt_value(creds.refresh_token) if creds.refresh_token else None,
            gmail_address=profile.get("emailAddress", ""),
            token_expiry=creds.expiry.isoformat() if creds.expiry else None,
        )
        print(f"[gmail_callback] step6: done, redirecting to settings")
        return RedirectResponse(url="/settings?gmail=connected")
    except Exception as e:
        print(f"Gmail OAuth callback error: {e}")
        return RedirectResponse(url="/settings?gmail=error")

@app.get("/api/gmail/status")
async def gmail_status(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    token_data = db.get_gmail_tokens(current_user["id"])
    if not token_data:
        return {"connected": False, "email": None}
    return {"connected": True, "email": token_data.get("gmail_address")}

@app.get("/api/gmail/emails")
async def get_gmail_emails(
    max_results: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    service = _get_gmail_service(current_user["id"])
    result = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=max_results).execute()
    emails = []
    for msg in result.get("messages", []):
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["Subject", "From", "To", "Date"]
        ).execute()
        headers = detail.get("payload", {}).get("headers", [])
        labels = detail.get("labelIds", [])
        emails.append({
            "id": detail["id"], "thread_id": detail.get("threadId"),
            "subject": _get_header(headers, "Subject") or "(no subject)",
            "from": _get_header(headers, "From"), "to": _get_header(headers, "To"),
            "date": _get_header(headers, "Date"), "snippet": detail.get("snippet", ""),
            "is_unread": "UNREAD" in labels,
        })
    return {"emails": emails, "count": len(emails)}

@app.get("/api/gmail/email/{message_id}")
async def get_gmail_email(
    message_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    service = _get_gmail_service(current_user["id"])
    detail = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = detail.get("payload", {}).get("headers", [])
    body = _extract_email_body(detail.get("payload", {}))
    if "UNREAD" in detail.get("labelIds", []):
        service.users().messages().modify(userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}).execute()
    return {
        "id": detail["id"], "thread_id": detail.get("threadId"),
        "subject": _get_header(headers, "Subject") or "(no subject)",
        "from": _get_header(headers, "From"), "to": _get_header(headers, "To"),
        "date": _get_header(headers, "Date"), "body": body,
    }

@app.post("/api/gmail/reply")
async def send_gmail_reply(
    req: GmailReplyRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    service = _get_gmail_service(current_user["id"])
    subject = req.subject if req.subject.lower().startswith("re:") else f"Re: {req.subject}"
    mime_msg = MIMEText(req.body)
    mime_msg["to"] = req.to
    mime_msg["subject"] = subject
    mime_msg["In-Reply-To"] = req.message_id
    mime_msg["References"] = req.message_id
    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw, "threadId": req.thread_id}).execute()
    return {"message": "Reply sent"}

@app.delete("/api/gmail/disconnect")
async def gmail_disconnect(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    db.delete_gmail_tokens(current_user["id"])
    return {"message": "Gmail disconnected"}

@app.get("/api/gmail/watched-senders")
async def get_watched_senders(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    return {"senders": db.get_watched_senders(current_user["id"])}

@app.post("/api/gmail/watched-senders")
async def add_watched_sender(
    req: WatchedSenderRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    added = db.add_watched_sender(current_user["id"], req.email_address, req.display_name)
    if not added:
        raise HTTPException(status_code=400, detail="Sender already in watch list")

    # Pre-seed existing emails from this sender so the poller doesn't
    # notify about historical messages — only truly new ones will trigger SMS.
    try:
        service = _get_gmail_service(current_user["id"])
        result = await asyncio.to_thread(
            lambda: service.users().messages().list(
                userId="me",
                q=f"from:{req.email_address}",
                maxResults=500,
            ).execute()
        )
        for msg in result.get("messages", []):
            db.mark_email_notified(current_user["id"], msg["id"])
    except Exception:
        pass  # Gmail not connected or query failed — poller will handle it gracefully

    return {"message": "Sender added", "email_address": req.email_address}

@app.delete("/api/gmail/watched-senders/{email_address:path}")
async def remove_watched_sender(
    email_address: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    db.remove_watched_sender(current_user["id"], email_address)
    return {"message": "Sender removed"}


# Frontend routes - serve HTML files
@app.get("/login")
async def login_page():
    """Serve login page"""
    login_file = FRONTEND_DIR / "login.html"
    if login_file.exists():
        return FileResponse(login_file)
    raise HTTPException(status_code=404, detail="Login page not found")

@app.get("/login.html")
async def login_page_html():
    """Serve login page (alternative URL)"""
    login_file = FRONTEND_DIR / "login.html"
    if login_file.exists():
        return FileResponse(login_file)
    raise HTTPException(status_code=404, detail="Login page not found")

@app.get("/dashboard")
async def dashboard_page():
    """Serve dashboard page"""
    dashboard_file = FRONTEND_DIR / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(dashboard_file)
    raise HTTPException(status_code=404, detail="Dashboard page not found")

@app.get("/dashboard.html")
async def dashboard_page_html():
    """Serve dashboard page (alternative URL)"""
    dashboard_file = FRONTEND_DIR / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(dashboard_file)
    raise HTTPException(status_code=404, detail="Dashboard page not found")

@app.get("/settings")
async def settings_page():
    """Serve settings page"""
    settings_file = FRONTEND_DIR / "settings.html"
    if settings_file.exists():
        return FileResponse(settings_file)
    raise HTTPException(status_code=404, detail="Settings page not found")

@app.get("/settings.html")
async def settings_page_html():
    """Serve settings page (alternative URL)"""
    settings_file = FRONTEND_DIR / "settings.html"
    if settings_file.exists():
        return FileResponse(settings_file)
    raise HTTPException(status_code=404, detail="Settings page not found")

@app.get("/")
async def root_page():
    """Serve main landing page"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    # Fallback to API info if no frontend
    return {
        "message": "Off-Grid AI Agent API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "admin": "/admin",
            "api": "/api"
        }
    }

@app.get("/index.html")
async def index_page():
    """Serve main landing page (alternative URL)"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Index page not found")

if __name__ == "__main__":
    import uvicorn
    
    db.init_database()
 
    if ENVIRONMENT == "development":
        print(f"📖 API Docs:      http://localhost:8000/docs")
        print(f"📖 webapp:      http://localhost:8001")
    
    # Use import string format for proper reload functionality
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

