# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
from typing import TypedDict, Annotated
import operator
import os
import re
import asyncio
import traceback
from html import escape as _xml_escape

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from twilio.rest import Client as TwilioClient

from agent_router.llm_setup import get_llm, update_model, get_model_name, set_request_llm, clear_request_llm, create_llm_for_user
from agent_router.weather.agent import weather_agent
from agent_router.firstAid.agent import first_aid_agent
from agent_router.search_web.agent import search_web_agent
from agent_router.camping_advice.agent import camping_advice_agent
from agent_router.langfuse_setup import langfuse_handler
from agent_router.human_in_the_loop import ask_user_clarification
from agent_router.human_in_the_loop.agent import TIMEOUT_MESSAGE
from agent_router.gmail.agent import run_gmail_agent
from agent_router.trails.agent import run_trails_agent
from database import db, decrypt_value, encrypt_value

# -----------------------------------------------------------------------------
# Twilio & FastAPI app
# -----------------------------------------------------------------------------
# Twilio client for sending outbound SMS
twilio_client = TwilioClient(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"],
)
TWILIO_PHONE_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]

app = FastAPI()

# -----------------------------------------------------------------------------
# Graph state
# -----------------------------------------------------------------------------
class RouterState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], operator.add]
    route: str
    phone_number: str
    user_id: int
    clarification_got_answer: bool
    user_location: str  # e.g. "Provo, UT" from Twilio carrier data


# -----------------------------------------------------------------------------
# Classification
# -----------------------------------------------------------------------------
def classify(state: RouterState) -> RouterState:
    """Use the LLM to classify which agent should handle the message."""
    from langchain_core.messages import SystemMessage as _SM
    last = state["messages"][-1]
    text = (last.content if isinstance(last.content, str) else "").strip()

    # Inject Twilio carrier location as a system hint for all downstream agents
    location = state.get("user_location", "")
    extra_messages = []
    if location:
        extra_messages = [_SM(content=(
            f"The user's approximate carrier location is: {location}. "
            "ONLY use this as a fallback if the user has not mentioned a specific city, state, or location in their message. "
            "If the user specifies any location, always use what they said and ignore this carrier location."
        ))]

    if text.lower().startswith("google "):
        return {"route": "search_web", "messages": extra_messages}

    response = get_llm().invoke([
    HumanMessage(content=(
        "Classify the following user message into ONE category. "
        "Reply with ONLY the category name.\n\n"

        "Categories: weather, first_aid, search_web, camping_advice, "
        "trails, gmail, help, parks, need_clarification, unknown\n\n"

        "weather: Questions about atmospheric conditions, forecasts, "
        "temperature, rain, snow, wind, storms, humidity. "
        "Route here even if real-time data is required.\n\n"

        "first_aid: Injuries, CPR, bleeding, choking, burns, poisoning, "
        "medical emergencies, urgent health care guidance. "
        "Includes urgent distress phrases.\n\n"

        "search_web: Questions requiring current, real-time, "
        "location-specific, business, or recent information. "
        "Examples: business hours, stock prices, news, sports scores, "
        "trail closures, availability.\n\n"

        "camping_advice: General outdoor skills and camping knowledge "
        "that does NOT require real-time or location-specific data. "
        "Examples: how to build a fire, what tent to buy, how to filter water.\n\n"

        "trails: Questions about hiking trails, trail routes, distances, difficulty, "
        "trail maps, safety on a specific trail, or what trails are available. "
        "Examples: Devils Garden routes, Angels Landing permit, Narrows conditions, "
        "how long is the trail, is it hard, trail map, Zion Canyon routes, "
        "Kolob Canyons, East Rim, trail safety tips.\n\n"

        "gmail: User wants to check email, list inbox, see recent emails, "
        "read emails, reply to an email, or send an email.\n\n"

        "help: User is asking what the bot can do, what commands are available, "
        "how to use it, what agents or features exist, or wants a general overview. "
        "Examples: what can you do, how do I use this, what are your capabilities.\n\n"

        "parks: User wants a list of known trails or parks. "
        "Examples: list all trails, what parks do you know, show available hikes.\n\n"

        "need_clarification: Message is ambiguous, incomplete, or could "
        "fit multiple categories without more context.\n\n"

        "unknown: Does not fit any category above. If you are not sure, route to search_web\n\n"

        f"Message: {state['messages'][-1].content}"
    ))
    ])
    route = response.content.strip().lower()
    if "weather" in route:
        route = "weather"
    elif "first_aid" in route or "first aid" in route:
        route = "first_aid"
    elif "search_web" in route or "search web" in route:
        route = "search_web"
    elif "camping_advice" in route or "camping" in route:
        route = "camping_advice"
    elif "trails" in route or "trail" in route:
        route = "trails"
    elif "gmail" in route or "email" in route:
        route = "gmail"
    elif "help" in route:
        route = "help"
    elif "parks" in route:
        route = "parks"
    elif "need_clarification" in route or "clarification" in route:
        route = "need_clarification"
    else:
        route = "unknown"
    return {"route": route, "messages": extra_messages}


def route_decision(state: RouterState) -> str:
    """Route to the correct agent based on classification."""
    return state["route"]


# -----------------------------------------------------------------------------
# Ambiguous-message clarification (human-in-the-loop before classify)
# -----------------------------------------------------------------------------
CLARIFY_QUESTION = (
    "What would you like help with? Reply with: weather, first aid, search, camping, trails, or gmail."
)


def handle_need_clarification(state: RouterState) -> RouterState:
    """Ask the user a clarifying question via SMS and wait for reply (human-in-the-loop)."""
    phone = state.get("phone_number")
    user_id = state.get("user_id")
    if not phone or user_id is None:
        return {
            "messages": [AIMessage(content="We need to know your phone to ask a follow-up. Please try again.")],
            "clarification_got_answer": False,
        }
    answer, got_answer = ask_user_clarification(
        phone_number=phone,
        user_id=user_id,
        question=CLARIFY_QUESTION,
        twilio_client=twilio_client,
        from_twilio_number=TWILIO_PHONE_NUMBER,
        context=state["messages"][-1].content if state.get("messages") else None,
    )
    if got_answer and answer:
        return {
            "messages": [HumanMessage(content=answer)],
            "clarification_got_answer": True,
        }
    return {"messages": [], "clarification_got_answer": False}


def route_after_clarification(state: RouterState):
    """If we got an answer, re-classify; else end (timeout SMS already sent)."""
    return "classify" if state.get("clarification_got_answer") else END


# -----------------------------------------------------------------------------
# Post-agent routing (clarification vs SMS vs search fallback)
# -----------------------------------------------------------------------------
def _is_agent_asking_clarification(state: RouterState) -> bool:
    """True if the last message is an AI clarification request (e.g. 'Please specify city and state').

    Requires the message to look like a question or an explicit ask, not just to mention a
    keyword. Otherwise factual answers that happen to contain words like 'location' route
    incorrectly to the human-in-the-loop flow.
    """
    if not state.get("messages"):
        return False
    last = state["messages"][-1]
    if not hasattr(last, "content") or not isinstance(last.content, str):
        return False
    content = last.content.strip().lower()
    if len(content) > 250:
        return False
    looks_like_question = content.endswith("?") or content.startswith((
        "please specify", "please provide", "which city", "which state",
        "what city", "what state", "what location", "where are you",
        "where is", "could you specify", "can you specify", "could you tell me",
    ))
    return looks_like_question


# Phrases that indicate the first-aid or camping RAG agent couldn't find relevant advice
_RAG_NO_MATCH_PHRASES = (
    "not in the context",
    "not in the manual",
    "not in the following",
    "no relevant",
    "couldn't find",
    "could not find",
    "don't have information",
    "do not have information",
    "is not covered",
    "not covered in",
    "not found in",
    "no excerpts",
    "no manual excerpts",
    "answer is not in",
    "not in our",
    "outside the scope",
    "not in this",
)


def _rag_found_nothing(state: RouterState) -> bool:
    """True if the last AI message indicates the RAG agent found no relevant advice."""
    if not state.get("messages"):
        return False
    last = state["messages"][-1]
    if not hasattr(last, "content") or not isinstance(last.content, str):
        return False
    content = last.content.strip().lower()
    return any(phrase in content for phrase in _RAG_NO_MATCH_PHRASES)


def _route_after_first_aid_or_camping(state: RouterState) -> str:
    """After first_aid or camping_advice: try search_web if RAG found nothing, else humain_in_the_loop or format_for_sms."""
    if _rag_found_nothing(state):
        return "search_web_fallback"
    return _route_after_agent(state)


def _route_after_agent(state: RouterState) -> str:
    """After weather/first_aid/search_web: go to humain_in_the_loop if they asked for more info, else format_for_sms."""
    if state.get("route") not in ("weather", "first_aid", "search_web"):
        return "format_for_sms"
    if not state.get("phone_number") or state.get("user_id") is None:
        return "format_for_sms"
    if not _is_agent_asking_clarification(state):
        return "format_for_sms"
    return "humain_in_the_loop"


def handle_agent_clarification(state: RouterState) -> RouterState:
    """Send the agent's question via SMS, wait for reply, then re-invoke that agent with the answer."""
    phone = state["phone_number"]
    user_id = state["user_id"]
    route = state["route"]
    question = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        state["messages"][-1].content,
    )
    answer, got_answer = ask_user_clarification(
        phone_number=phone,
        user_id=user_id,
        question=question,
        twilio_client=twilio_client,
        from_twilio_number=TWILIO_PHONE_NUMBER,
        context=state["messages"][0].content if state.get("messages") else None,
    )
    if not got_answer or not answer:
        return {"messages": [AIMessage(content=TIMEOUT_MESSAGE)]}
    # Re-invoke the same agent with original messages + the user's reply
    updated_messages = list(state["messages"]) + [HumanMessage(content=answer)]
    if route == "weather":
        result = weather_agent.invoke({"messages": updated_messages})
    elif route == "first_aid":
        result = first_aid_agent.invoke({"messages": updated_messages})
    else:
        result = search_web_agent.invoke({"messages": updated_messages})
    return {"messages": result["messages"]}


# -----------------------------------------------------------------------------
# Agent node handlers
# -----------------------------------------------------------------------------
def handle_weather(state: RouterState) -> RouterState:
    """Hand off to the weather agent."""
    result = weather_agent.invoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


def handle_first_aid(state: RouterState) -> RouterState:
    """Hand off to the first-aid RAG agent."""
    result = first_aid_agent.invoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


def handle_search_web(state: RouterState) -> RouterState:
    """Hand off to the smol agent (web search + scrape)."""
    result = search_web_agent.invoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


def handle_camping_advice(state: RouterState) -> RouterState:
    """Hand off to the camping/outdoors advice RAG agent."""
    result = camping_advice_agent.invoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


def handle_search_web_fallback(state: RouterState) -> RouterState:
    """Run search_web with the user's original question when first_aid or camping_advice found nothing."""
    messages = state.get("messages", [])
    user_message = next(
        (m for m in messages if isinstance(m, HumanMessage)),
        None,
    )
    if not user_message or not getattr(user_message, "content", None):
        return state
    content = user_message.content
    if not isinstance(content, str):
        content = str(content)
    result = search_web_agent.invoke({"messages": [HumanMessage(content=content)]})
    return {"messages": result["messages"]}


def handle_gmail(state: RouterState) -> RouterState:
    """Hand off to the Gmail agent."""
    result = run_gmail_agent(state["messages"], state.get("user_id"))
    return {"messages": result["messages"]}


def handle_trails(state: RouterState) -> RouterState:
    """Hand off to the trails agent."""
    result = run_trails_agent(state["messages"])
    return {"messages": result["messages"]}


def handle_help(state: RouterState) -> RouterState:
    """Return the help text listing available agents and commands."""
    return {"messages": [AIMessage(content=HELP_TEXT)]}


def handle_parks(state: RouterState) -> RouterState:
    """Return the list of known trails and parks."""
    return {"messages": [AIMessage(content=_parks_list_text())]}


def handle_unknown(state: RouterState) -> RouterState:
    """Fallback for unrecognized requests."""
    response = get_llm().invoke(state["messages"])
    return {"messages": [response]}


# -----------------------------------------------------------------------------
# SMS formatting (final graph node)
# -----------------------------------------------------------------------------
SMS_MAX_CHARS = 480       # 3 segments — enough for real advice, not excessive
SMS_REWRITE_THRESHOLD = 300  # rewrite anything over ~2 segments    

# Emoji ranges (supplementary and common symbols) for stripping from SMS
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002600-\U000026FF"  # misc symbols
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"  # supplemental symbols & pictographs
    "]+",
    flags=re.UNICODE,
)


def _strip_and_truncate_for_sms(text: str) -> str:
    """Strip markdown, remove emojis, and truncate to SMS-safe length."""
    text = _EMOJI_PATTERN.sub("", text)
    text = re.sub(r'\*+', '', text)           # remove * and **
    text = re.sub(r'#+\s*', '', text)         # remove # headers
    text = re.sub(r'- ', '', text)            # remove bullet dashes
    text = re.sub(r'\n{2,}', '\n', text)     # collapse all multi-newlines
    text = re.sub(r'  +', ' ', text)         # collapse extra spaces
    text = text.strip()
    if len(text) > SMS_MAX_CHARS:
        text = text[:SMS_MAX_CHARS - 3] + "..."
    return text


def format_for_sms(state: RouterState) -> RouterState:
    """Strip markdown and truncate. Only invoke the LLM to rewrite if the reply is too long
    for SMS — otherwise we burn a round trip on text that already fits."""
    text = state["messages"][-1].content
    text = _strip_and_truncate_for_sms(text)

    if len(text) <= SMS_REWRITE_THRESHOLD:
        return {"messages": [AIMessage(content=text)]}

    try:
        response = get_llm().invoke([
            HumanMessage(content=(
                f"Rewrite this so it makes sense as a standalone SMS. "
                f"Under {SMS_MAX_CHARS} characters. Plain text only — no markdown, "
                f"bullets, headers, or emojis.\n\n{text}"
            ))
        ])
        rewritten = (response.content or "").strip()
        if rewritten:
            text = _strip_and_truncate_for_sms(rewritten)
    except Exception as e:
        # If the rewrite call fails, fall back to the truncated original.
        print(f"[format_for_sms] rewrite failed: {e}")

    return {"messages": [AIMessage(content=text)]}


# -----------------------------------------------------------------------------
# LangGraph build
# -----------------------------------------------------------------------------
# Build the router graph
graph_builder = StateGraph(RouterState)
graph_builder.add_node("classify", classify)
graph_builder.add_node("weather", handle_weather)
graph_builder.add_node("first_aid", handle_first_aid)
graph_builder.add_node("search_web", handle_search_web)
graph_builder.add_node("camping_advice", handle_camping_advice)
graph_builder.add_node("search_web_fallback", handle_search_web_fallback)
graph_builder.add_node("gmail", handle_gmail)
graph_builder.add_node("trails", handle_trails)
graph_builder.add_node("help", handle_help)
graph_builder.add_node("parks", handle_parks)
graph_builder.add_node("unknown", handle_unknown)
graph_builder.add_node("format_for_sms", format_for_sms)

graph_builder.add_edge(START, "classify")
graph_builder.add_conditional_edges(
    "classify",
    route_decision,
    ["weather", "first_aid", "search_web", "camping_advice", "trails", "gmail", "help", "parks", "need_clarification", "unknown"],
)
graph_builder.add_node("need_clarification", handle_need_clarification)
graph_builder.add_conditional_edges(
    "need_clarification",
    route_after_clarification,
    ["classify", END],
)
graph_builder.add_node("humain_in_the_loop", handle_agent_clarification)
graph_builder.add_conditional_edges(
    "weather",
    _route_after_agent,
    ["humain_in_the_loop", "format_for_sms"],
)
graph_builder.add_conditional_edges(
    "first_aid",
    _route_after_first_aid_or_camping,
    ["search_web_fallback", "humain_in_the_loop", "format_for_sms"],
)
graph_builder.add_conditional_edges(
    "search_web",
    _route_after_agent,
    ["humain_in_the_loop", "format_for_sms"],
)
graph_builder.add_conditional_edges(
    "camping_advice",
    _route_after_first_aid_or_camping,
    ["search_web_fallback", "humain_in_the_loop", "format_for_sms"],
)
graph_builder.add_edge("humain_in_the_loop", "format_for_sms")
graph_builder.add_edge("search_web_fallback", "format_for_sms")
graph_builder.add_edge("gmail", "format_for_sms")
graph_builder.add_edge("trails", "format_for_sms")
graph_builder.add_edge("help", "format_for_sms")
graph_builder.add_edge("parks", "format_for_sms")
graph_builder.add_edge("unknown", "format_for_sms")
graph_builder.add_edge("format_for_sms", END)

router_graph = graph_builder.compile()


# -----------------------------------------------------------------------------
# Graph invocation (per-user LLM)
# -----------------------------------------------------------------------------
def _invoke_for_user(state: dict, user_id: int, **kwargs) -> dict:
    """Invoke the router graph with the user's preferred LLM set for this thread."""
    user_llm = create_llm_for_user(user_id, db)
    set_request_llm(user_llm)
    try:
        return router_graph.invoke(state, **kwargs)
    finally:
        clear_request_llm()


# -----------------------------------------------------------------------------
# Gmail poller (optional Google API deps)
# -----------------------------------------------------------------------------
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from googleapiclient.discovery import build as _gmail_build
    _GMAIL_POLL_AVAILABLE = True
except ImportError:
    _GMAIL_POLL_AVAILABLE = False

GMAIL_POLL_INTERVAL = int(os.environ.get("GMAIL_POLL_INTERVAL", "300"))  # seconds (default 5 min)
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def _extract_email_body(payload: dict) -> str:
    """Recursively extract plain text body from a Gmail message payload."""
    import base64
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    if body_data and "text/plain" in mime_type:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_email_body(part)
        if result:
            return result
    return ""


def _summarise_email(sender: str, subject: str, body: str, user_id: int) -> str:
    """Use the LLM to produce a 1–2 sentence SMS-friendly summary of the email."""
    body_snippet = body[:2000].strip() if body else ""
    prompt = (
        f"Summarise this email in 1-2 plain sentences (no markdown, no emojis, under 200 chars). "
        f"Focus on what action, if any, is needed.\n\n"
        f"From: {sender}\nSubject: {subject}\n\n{body_snippet}"
    )
    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        summary = (response.content or "").strip()
        # Strip any markdown that crept in
        summary = re.sub(r'\*+', '', summary)
        summary = re.sub(r'#+\s*', '', summary)
        return summary[:200]
    except Exception as e:
        print(f"[Gmail poll] Summary LLM error: {e}")
        return ""


def _poll_gmail_notifications():
    """Check each connected user's Gmail for new emails from watched senders and SMS-notify."""
    if not _GMAIL_POLL_AVAILABLE:
        return

    users = db.get_all_gmail_users()
    for u in users:
        user_id      = u["user_id"]
        phone_number = u["phone_number"]
        watched      = db.get_watched_senders(user_id)
        if not watched:
            continue

        try:
            access_token  = decrypt_value(u["access_token"])
            refresh_token = decrypt_value(u["refresh_token"]) if u.get("refresh_token") else None

            creds = Credentials(
                token=access_token, refresh_token=refresh_token,
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
                    refresh_token=encrypt_value(creds.refresh_token) if creds.refresh_token else u["refresh_token"],
                    gmail_address=u.get("gmail_address"),
                    token_expiry=creds.expiry.isoformat() if creds.expiry else None,
                )

            service = _gmail_build("gmail", "v1", credentials=creds)

            # Build query: from any watched sender, unread in inbox
            from_query = " OR ".join(f"from:{s['email_address']}" for s in watched)
            result = service.users().messages().list(
                userId="me", q=f"in:inbox ({from_query})", maxResults=20
            ).execute()

            for msg in result.get("messages", []):
                msg_id = msg["id"]
                if db.is_email_notified(user_id, msg_id):
                    continue

                # Fetch full message to get body for summarisation
                detail = service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()
                hdrs    = detail.get("payload", {}).get("headers", [])
                subject = next((h["value"] for h in hdrs if h["name"].lower() == "subject"), "(no subject)")
                sender  = next((h["value"] for h in hdrs if h["name"].lower() == "from"), "")
                body    = _extract_email_body(detail.get("payload", {}))

                summary = _summarise_email(sender, subject, body, user_id)

                if summary:
                    sms_text = f"Email from {sender}\n{summary}"
                else:
                    sms_text = f"Email from {sender}: {subject}"

                if len(sms_text) > 320:
                    sms_text = sms_text[:317] + "..."

                try:
                    twilio_client.messages.create(
                        body=sms_text, from_=TWILIO_PHONE_NUMBER, to=phone_number
                    )
                    db.mark_email_notified(user_id, msg_id)
                    print(f"[Gmail poll] Notified {phone_number}: {sms_text!r}")
                except Exception as sms_err:
                    print(f"[Gmail poll] SMS error for user {user_id}: {sms_err}")

        except Exception as e:
            print(f"[Gmail poll] Error for user {user_id}: {e}")


async def _gmail_poll_loop():
    """Background asyncio task that polls Gmail on a fixed interval."""
    await asyncio.sleep(30)  # brief startup delay
    while True:
        try:
            await asyncio.to_thread(_poll_gmail_notifications)
        except Exception as e:
            print(f"[Gmail poll] Loop error: {e}")
        await asyncio.sleep(GMAIL_POLL_INTERVAL)


@app.on_event("startup")
async def start_gmail_poller():
    asyncio.create_task(_gmail_poll_loop())


# -----------------------------------------------------------------------------
# HTTP models & SMS / intent helpers
# -----------------------------------------------------------------------------
class AskRequest(BaseModel):
    message: str
    phone_number: str


HELP_TEXT = (
    "Commands: MORE, SHORT, WHY, STEPS, CLEAR\n"
    "Say 'list trails' to see available parks.\n"
    "Agents:\n"
    "Weather: forecasts, rain, temp\n"
    "Search: news, business hours, prices\n"
    "First Aid: injuries, emergencies\n"
    "Camping: outdoor skills, gear\n"
    "Trails: routes, maps, safety\n"
    "Gmail: check/reply to emails"
)

_COMMANDS = {"more", "short", "why", "steps", "clear"}

_HELP_PHRASES = (
    "what can you do", "what do you do", "list your commands", "list commands",
    "what commands", "what tools", "what tools do you have", "what are your tools",
    "what are your commands", "show commands", "show tools", "help me",
    "what are you", "what are you capable of", "capabilities", "features",
    "how do i use", "how to use", "what can i ask", "what can i say",
)

_PARKS_PHRASES = (
    "list parks", "list trails", "list all trails", "what parks",
    "what trails", "what trails do you have", "what parks do you have",
    "show parks", "show trails", "available trails", "available parks",
    "what hikes", "list hikes", "what hikes do you know",
)


def _is_help_intent(text: str) -> bool:
    """Return True if the message is asking what the bot can do."""
    t = text.strip().lower()
    return any(phrase in t for phrase in _HELP_PHRASES)


def _is_parks_intent(text: str) -> bool:
    """Return True if the message is asking for a list of known trails/parks."""
    t = text.strip().lower()
    return any(phrase in t for phrase in _PARKS_PHRASES)


def _parks_list_text() -> str:
    """Build a quick trail/park listing from the registry."""
    from agent_router.trails.data.registry import list_trails
    trails = list_trails()
    # Group by park
    seen_parks: dict[str, list[str]] = {}
    for t in trails:
        park = t.get("park") or t.get("name")
        name = t["name"]
        seen_parks.setdefault(park, []).append(name)
    lines = ["Available trails:"]
    for park, areas in seen_parks.items():
        if len(areas) == 1 and areas[0] == park:
            lines.append(f"- {park}")
        else:
            lines.append(f"- {park}: {', '.join(areas)}")
    lines.append("Ask about any trail for routes, maps, or safety.")
    return "\n".join(lines)


def _handle_command(cmd: str, user_id: int, phone_number: str) -> str | None:
    """
    Handle a single-word command. Returns reply text or None if not a command.
    Commands: MORE, SHORT, WHY, STEPS, CLEAR
    """
    cmd = cmd.strip().lower()
    if cmd not in _COMMANDS and cmd != "clear history":
        return None

    if cmd in ("clear", "clear history"):
        db.clear_user_messages(user_id)
        db.remove_follow_up_hold(phone_number)
        return "Conversation cleared. Send any message to start fresh."

    # MORE / SHORT / WHY / STEPS all need the last AI reply
    rows = db.get_user_messages(user_id, limit=6)
    last_ai = next((r["message_text"] for r in rows if r.get("direction") == "outbound"), None)
    if not last_ai:
        return "No previous reply to work with."

    prompts = {
        "more": (
            f"Expand this SMS reply with more detail. Plain text, no markdown:\n\n{last_ai}"
        ),
        "short": (
            f"Compress this into the shortest possible plain-text SMS reply:\n\n{last_ai}"
        ),
        "why": (
            f"Explain the reasoning behind this reply in plain text, no markdown:\n\n{last_ai}"
        ),
        "steps": (
            f"Rewrite this as a numbered step-by-step action list. Plain text, no markdown:\n\n{last_ai}"
        ),
    }
    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=prompts[cmd])])
        return (response.content or "").strip()
    except Exception as e:
        return f"Error: {e}"


def _messages_from_db(user_id: int, limit: int = 50) -> list[BaseMessage]:
    """Load conversation history from DB (chronological order)."""
    rows = db.get_user_messages(user_id, limit=limit)
    # DB returns newest first; we need oldest first for conversation order
    out: list[BaseMessage] = []
    for row in reversed(rows):
        text = row.get("message_text") or ""
        if row.get("direction") == "inbound":
            out.append(HumanMessage(content=text))
        else:
            out.append(AIMessage(content=text))
    return out


# -----------------------------------------------------------------------------
# API routes
# -----------------------------------------------------------------------------
@app.post("/updateModel")
async def updateModel(request: Request):
    """Update the model by sending a test message."""
    print("Updating model...")
    new_model = await request.json()
    print(f"New model: {new_model.get('model')}")
    model = new_model.get('model')
    if model:
        update_model(model)
        return {"response": f"Model updated to {model}."}
    else:
        return {"response": "No model provided."}


@app.post("/ask")
def ask(request: AskRequest):
    """Single entry point — LangGraph routes to the appropriate agent. Uses phone_number for hold check and DB history. phone_number must be a registered active user."""
    phone_number = request.phone_number
    message = (request.message or "").strip()
    print(f"[ASK] {phone_number}: {message[:80]!r}")
    print(f"Using model: {get_model_name()}.")
    if not message:
        return {"response": "Message cannot be empty."}

    user = db.get_user_by_phone(phone_number)
    if not user or not user.get("is_active", False):
        return {"response": "Unregistered or inactive user. Use a registered phone number."}

    if message.lower() == "clear":
        db.remove_follow_up_hold(phone_number)
        return {"response": "Cleared."}

    hold = db.get_recent_follow_up_hold_by_phone(phone_number)
    if hold:
        db.set_follow_up_answer(phone_number, message)
        return {"response": "Follow-up received."}

    if db.is_phone_in_follow_up_hold(phone_number):
        db.remove_follow_up_hold(phone_number)

    user_id = user["id"]

    # Help intent and single-word commands — handle before routing to agent
    if _is_help_intent(message):
        return {"response": HELP_TEXT}
    if _is_parks_intent(message):
        return {"response": _parks_list_text()}
    command_reply = _handle_command(message.strip(), user_id, phone_number)
    if command_reply is not None:
        return {"response": command_reply}

    messages: list[BaseMessage] = _messages_from_db(user_id) + [
        HumanMessage(content=message)
    ]
    result = _invoke_for_user(
        {
            "messages": messages,
            "phone_number": phone_number,
            "user_id": user_id,
        },
        user_id=user_id,
        config={"callbacks": [langfuse_handler] if langfuse_handler else []},
    )
    last_message = result["messages"][-1]
    reply = last_message.content

    db.log_sms_message(user_id, phone_number, message, "inbound")
    db.log_sms_message(user_id, phone_number, reply, "outbound")

    return {"response": reply}

@app.get("/sms")
async def sms_webhook_get(request: Request):
    print("Received SMS webhook GET")
    return Response(content="OK", media_type="text/plain")

@app.post("/sms")
async def sms_webhook(request: Request):
    """Handle incoming SMS from Twilio — respond immediately, process in background."""
    print("Received SMS webhook")
    print(request.body)
    form_data = await request.form()
    body = form_data.get("Body", "")
    from_number = form_data.get("From", "")
    from_city    = form_data.get("FromCity", "").strip().title()
    from_state   = form_data.get("FromState", "").strip().upper()
    user_location = f"{from_city}, {from_state}" if from_city and from_state else from_state or from_city or ""
    print(f"Received SMS from {from_number} ({user_location or 'unknown location'}): {body}")

    # Look up sender by phone number
    
    user = db.get_user_by_phone(from_number)
    if not user or not user.get("is_active", False):
        print(f"Unregistered or inactive user {from_number}")
        return Response(content="<Response/>", media_type="application/xml")
    
    if body.lower() == "test":
        print("Test message received, returning test reply")
        return Response(
            content="<Response><Message>we got your test message</Message></Response>",
            media_type="application/xml",
        )
    if body.lower() == "clear":
        db.remove_follow_up_hold(from_number)
        print(f"Cleared follow-up hold for {from_number}")
        return Response(content="<Response/>", media_type="application/xml")

    # Fast-path: help/parks intent and CLEAR always bypass follow-up hold logic
    cmd_lower = body.strip().lower()
    fast_reply = None
    if _is_help_intent(cmd_lower):
        fast_reply = HELP_TEXT
    elif _is_parks_intent(cmd_lower):
        fast_reply = _parks_list_text()
    elif cmd_lower in ("clear", "clear history"):
        uid = user["id"]
        fast_reply = _handle_command(cmd_lower, uid, from_number)
    if fast_reply is not None:
        uid = user["id"]
        db.log_sms_message(uid, from_number, body, "inbound")
        db.log_sms_message(uid, from_number, fast_reply, "outbound")
        return Response(
            content=f"<Response><Message>{_xml_escape(fast_reply)}</Message></Response>",
            media_type="application/xml",
        )

    # Only treat as follow-up if there's a *recent* hold (someone is actually waiting for this reply)
    hold = db.get_recent_follow_up_hold_by_phone(from_number)
    if hold:
        db.set_follow_up_answer(from_number, body)
        print(f"Stored follow-up answer for {from_number}")
        return Response(content="<Response/>", media_type="application/xml")
    # Stale or leftover hold: clear it so this message is processed as a new request
    if db.is_phone_in_follow_up_hold(from_number):
        db.remove_follow_up_hold(from_number)
        print(f"Cleared stale follow-up hold for {from_number}, processing as new message")

    # Return empty TwiML immediately so Twilio doesn't timeout
    asyncio.create_task(_process_and_reply(user, from_number, body, user_location))
    return Response(content="<Response/>", media_type="application/xml")


async def _process_and_reply(user: dict, from_number: str, body: str, user_location: str = ""):
    """Run the agent and send the reply via Twilio REST API."""
    user_id = user["id"]
    try:
        # Log inbound message
        db.log_sms_message(user_id, from_number, body, "inbound")

        # Help intent and commands before routing to agent
        if _is_help_intent(body):
            reply = HELP_TEXT
        elif _is_parks_intent(body):
            reply = _parks_list_text()
        else:
            reply = await asyncio.to_thread(_handle_command, body.strip(), user_id, from_number)
        if reply is not None:
            db.log_sms_message(user_id, from_number, reply, "outbound")
            twilio_client.messages.create(body=reply, from_=TWILIO_PHONE_NUMBER, to=from_number)
            return

        # Route through the LangGraph agent (runs in thread pool to avoid blocking)
        result = await asyncio.to_thread(
            _invoke_for_user,
            {
                "messages": [HumanMessage(content=body)],
                "phone_number": from_number,
                "user_id": user_id,
                "user_location": user_location,
            },
            user_id,
            config={
                "callbacks": [langfuse_handler],
                "metadata": {"user_id": user_id, "phone": from_number},
            },
        )
        agent_reply = (result["messages"][-1].content or "").strip()
        if not agent_reply:
            agent_reply = "Done."

        # Log outbound response
        db.log_sms_message(user_id, from_number, agent_reply, "outbound")

        # Send reply via Twilio REST API
        message = twilio_client.messages.create(
            body=agent_reply,
            from_=TWILIO_PHONE_NUMBER,
            to=from_number,
        )
        print(f"Sent reply to {from_number} (SID: {message.sid})")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] SMS processing failed for {from_number}: {e}\n{tb}")
        # Always send something back so the user knows the request finished
        try:
            twilio_client.messages.create(
                body="Something went wrong on my end.\nPlease try again.",
                from_=TWILIO_PHONE_NUMBER,
                to=from_number,
            )
        except Exception as twilio_err:
            print(f"Failed to send error SMS to {from_number}: {twilio_err}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="192.168.1.23", port=3002)
