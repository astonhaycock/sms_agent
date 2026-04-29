"""
Human-in-the-loop agent: send a clarifying question via SMS, hold the phone in the DB,
and poll for follow_up_answer. First check at 15s, then 10, 10, 10, 10, 5 (60s total).
If no answer in time, remove from hold and return timeout message.
Sync so it can be called from the router graph (invoke runs in a thread).
"""
import time
from typing import Optional, Tuple

from database import db


# Poll intervals in seconds: 30, then 10, 10, 10, 10, 5 (total 120s)
POLL_INTERVALS = [30, 10, 10, 10, 10, 5]

TIMEOUT_MESSAGE = (
    "Sorry we didn't get the information needed to answer this question."
)


def ask_user_clarification(
    phone_number: str,
    user_id: int,
    question: str,
    twilio_client,
    from_twilio_number: str,
    context: Optional[str] = None,
) -> Tuple[Optional[str], bool]:
    """
    Send the user a clarifying question via SMS, add them to follow_up_hold,
    then poll the DB at 30, 10, 10, 10, 10, 5 second intervals (120s total).
    Returns (answer_text, True) if the user replied in time, or (None, False)
    after sending the timeout SMS and removing from hold.
    """
    twilio_client.messages.create(
        body=question,
        from_=from_twilio_number,
        to=phone_number,
    )
    db.add_follow_up_hold(user_id, phone_number, context=context)

    for interval in POLL_INTERVALS:
        time.sleep(interval)
        row = db.get_follow_up_hold_by_phone(phone_number)
        if not row:
            return (None, False)
        if row.get("follow_up_answer"):
            answer = row["follow_up_answer"].strip()
            db.remove_follow_up_hold(phone_number)
            return (answer, True)

    db.remove_follow_up_hold(phone_number)
    twilio_client.messages.create(
        body=TIMEOUT_MESSAGE,
        from_=from_twilio_number,
        to=phone_number,
    )
    return (None, False)
