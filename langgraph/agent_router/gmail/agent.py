"""
Gmail SMS agent — lets users list recent emails and send replies via SMS.

Tools:
  list_recent_emails  — last 10 inbox emails (subject, sender, date)
  reply_to_email      — send a reply to a specified email address
"""

import os
import sys
import base64
from email.mime.text import MIMEText
from pathlib import Path
from typing import Annotated
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, AIMessage, HumanMessage

# Import the shared database (path resolves to /app/webapp/ in Docker)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from webapp.database import db, decrypt_value, encrypt_value

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

GMAIL_SYSTEM = SystemMessage(content=(
    "You are a Gmail assistant over SMS. "
    "IMPORTANT: You MUST call a tool on every turn. Never respond with text alone.\n"
    "- If the user wants to see emails: call list_recent_emails immediately.\n"
    "- If the user wants to send a new email: call send_email.\n"
    "- If the user wants to reply to a thread: call reply_to_email.\n"
    "Do NOT describe what you are about to do. Do NOT ask for confirmation. "
    "Do NOT say 'I can help with that'. Just call the tool and return the result. "
    "Plain text only, no markdown, no emojis, under 600 characters."
))


def _get_service(user_id: int):
    """Return an authenticated Gmail API service for the given user, or None."""
    if not GMAIL_AVAILABLE:
        return None
    token_data = db.get_gmail_tokens(user_id)
    if not token_data:
        return None

    access_token  = decrypt_value(token_data["access_token"])
    refresh_token = decrypt_value(token_data["refresh_token"]) if token_data.get("refresh_token") else None

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
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


def _hdr(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def make_gmail_tools(user_id: int):
    """Create Gmail tools bound to a specific user's credentials."""

    @tool
    def list_recent_emails(count: int = 5) -> str:
        """List recent emails from the user's Gmail inbox.

        Args:
            count: How many emails to fetch (default 5, max 10).
        """
        service = _get_service(user_id)
        if not service:
            return "Gmail is not connected. Please connect it at the settings page."

        count = max(1, min(count, 10))

        try:
            result = service.users().messages().list(
                userId="me", labelIds=["INBOX"], maxResults=count
            ).execute()
        except Exception as e:
            return f"Could not fetch inbox: {e}"

        msgs = result.get("messages", [])
        if not msgs:
            return "Your inbox is empty."

        # Use a batch request to fetch all message details in one round trip
        lines = []
        batch = service.new_batch_http_request()
        details: dict[str, dict] = {}

        def _store(msg_id, response, exception):
            if exception is None:
                details[msg_id] = response

        for m in msgs:
            batch.add(
                service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject"],
                ),
                callback=_store,
                request_id=m["id"],
            )

        try:
            batch.execute()
        except Exception as e:
            return f"Could not fetch email details: {e}"

        for i, m in enumerate(msgs, 1):
            detail = details.get(m["id"])
            if not detail:
                continue
            hdrs = detail.get("payload", {}).get("headers", [])

            frm_full = _hdr(hdrs, "From")
            if "<" in frm_full:
                name = frm_full.split("<")[0].strip().strip('"') or frm_full
            else:
                name = frm_full.split("@")[0] if "@" in frm_full else frm_full

            subject = _hdr(hdrs, "Subject") or "(no subject)"
            subject = subject[:40] + "…" if len(subject) > 40 else subject

            unread = " *" if "UNREAD" in detail.get("labelIds", []) else ""
            lines.append(f"{i}. {name}{unread}: {subject}")

        if not lines:
            return "Could not load emails."
        return "Inbox:\n" + "\n".join(lines)

    def _send(to_email: str, subject: str, body: str, thread_id: str | None = None) -> str:
        """Internal helper — builds MIME, encodes, and calls Gmail send API."""
        service = _get_service(user_id)
        if not service:
            return "Gmail is not connected. Please connect it at the settings page."

        token_data = db.get_gmail_tokens(user_id)
        from_addr = token_data.get("gmail_address", "") if token_data else ""

        mime = MIMEText(body, "plain", "utf-8")
        mime["to"]      = to_email
        mime["subject"] = subject
        if from_addr:
            mime["from"] = from_addr

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        payload: dict = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id

        try:
            service.users().messages().send(userId="me", body=payload).execute()
            return f"Email sent to {to_email}."
        except Exception as e:
            return f"Failed to send email: {e}"

    @tool
    def send_email(to_email: str, subject: str, body: str) -> str:
        """Compose and send a new email.

        Args:
            to_email: Recipient email address.
            subject:  Subject line for the new email.
            body:     Email body text.
        """
        return _send(to_email, subject, body)

    @tool
    def reply_to_email(to_email: str, subject: str, body: str) -> str:
        """Reply to an existing email thread.

        Args:
            to_email: Recipient email address.
            subject:  Subject line (Re: will be added if not already present).
            body:     Reply text.
        """
        service = _get_service(user_id)
        if not service:
            return "Gmail is not connected. Please connect it at the settings page."

        subj = subject if subject.lower().startswith("re:") else f"Re: {subject}"

        # Find the existing thread to reply into
        thread_id = None
        try:
            results = service.users().messages().list(
                userId="me", q=f"from:{to_email} OR to:{to_email}", maxResults=5
            ).execute()
            for m in results.get("messages", []):
                detail = service.users().messages().get(
                    userId="me", id=m["id"], format="metadata"
                ).execute()
                if detail.get("threadId"):
                    thread_id = detail["threadId"]
                    break
        except Exception:
            pass  # send without threading if lookup fails

        return _send(to_email, subj, body, thread_id)

    return [list_recent_emails, send_email, reply_to_email]


class GmailState(dict):
    messages: Annotated[list[BaseMessage], operator.add]
    user_id: int


def make_gmail_agent(user_id: int):
    """Build and compile a Gmail agent graph for the given user."""
    from agent_router.llm_setup import invoke_with_tools

    tools     = make_gmail_tools(user_id)
    tool_node = ToolNode(tools)

    def call_llm(state):
        msgs = state["messages"]
        if not msgs or msgs[0] is not GMAIL_SYSTEM:
            msgs = [GMAIL_SYSTEM] + [m for m in msgs if m is not GMAIL_SYSTEM]
        response = invoke_with_tools(msgs, tools)
        return {"messages": [response]}

    def should_continue(state):
        msgs = state["messages"]
        if not msgs[-1].tool_calls:
            return END
        tool_results_so_far = sum(1 for m in msgs if isinstance(m, ToolMessage))
        if tool_results_so_far >= 4:
            return END
        return "tools"

    g = StateGraph(dict)
    g.add_node("agent", call_llm)
    g.add_node("tools", tool_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", should_continue, ["tools", END])
    g.add_edge("tools", "agent")
    return g.compile()


_LIST_VERBS = ("show", "list", "check", "see", "get", "fetch", "read")
_EMAIL_NOUNS = ("email", "emails", "inbox", "mail", "messages")


def _is_list_intent(text: str) -> bool:
    """Return True if the message is clearly asking to list/show emails."""
    t = text.strip().lower()
    if len(t.split()) > 10:
        return False
    return any(v in t for v in _LIST_VERBS) and any(n in t for n in _EMAIL_NOUNS)


def _extract_count(text: str) -> int:
    """Pull a number from the message for how many emails to show."""
    import re
    m = re.search(r'\b(\d+)\b', text)
    return int(m.group(1)) if m else 5


def _detect_send_intent(text: str):
    """
    Detect 'send email to X body Y' pattern.
    Returns (to_email, body) or None.
    """
    import re
    m = re.search(
        r'send\s+(?:an?\s+)?(?:email|mail)\s+to\s+([\w.+\-]+@[\w.\-]+)',
        text, re.IGNORECASE
    )
    if m:
        to_email = m.group(1)
        after = text[m.end():].strip()
        # Strip leading connectors
        after = re.sub(r'^(?:saying|that says|with body|body:?|message:?|:)\s*', '', after, flags=re.IGNORECASE)
        body = after or "This is an automated message."
        return to_email, body
    return None


def run_gmail_agent(messages: list[BaseMessage], user_id: int) -> dict:
    """Entry point called by the router."""
    if not GMAIL_AVAILABLE:
        return {"messages": [AIMessage(content="Gmail libraries not installed on this server.")]}

    if not db.get_gmail_tokens(user_id):
        return {"messages": [AIMessage(content="Your Gmail is not connected. Please visit the settings page to connect it.")]}

    last_human = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )
    tools = make_gmail_tools(user_id)

    # Fast path: list emails
    if _is_list_intent(last_human):
        list_tool = next(t for t in tools if t.name == "list_recent_emails")
        count = _extract_count(last_human)
        result = list_tool.invoke({"count": count})
        return {"messages": [AIMessage(content=result)]}

    # Fast path: send new email
    send_match = _detect_send_intent(last_human)
    if send_match:
        to_email, body = send_match
        send_tool = next(t for t in tools if t.name == "send_email")
        result = send_tool.invoke({
            "to_email": to_email,
            "subject": "Message from SMS",
            "body": body,
        })
        return {"messages": [AIMessage(content=result)]}

    # LLM agent for complex requests (reply to thread, etc.)
    agent = make_gmail_agent(user_id)
    return agent.invoke({"messages": messages, "user_id": user_id})
