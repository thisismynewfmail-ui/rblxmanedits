"""Friends list, follower lists and the messaging inbox."""
from __future__ import annotations

from ..http import router as R
from ..http.router import Request
from ..models import users
from ..social import follows, friends, messages
from .base import (api_error, api_ok, flash_redirect, login_required, render,
                   router)


@router.get("/friends")
@login_required
def friends_page(req: Request):
    uid = int(req.user["id"])
    tab = req.query.get("tab", "friends")
    return render(req, "friends.html", tab=tab,
                  friends_list=friends.list_friends(uid, 200),
                  incoming=friends.incoming_requests(uid),
                  outgoing=friends.outgoing_requests(uid),
                  followers=follows.followers(uid, 100),
                  following=follows.following(uid, 100),
                  counts=follows.counts(uid),
                  online_fn=users.is_online)


@router.get("/messages")
@login_required
def inbox(req: Request):
    uid = int(req.user["id"])
    box = req.query.get("box", "inbox")
    rows = messages.sent(uid) if box == "sent" else messages.inbox(uid)
    view = []
    for row in rows:
        view.append({
            "id": int(row["id"]),
            "who": row["recipient_name"] if box == "sent" else row["sender_name"],
            "subject": row["subject"],
            "preview": messages.preview(row["body"]),
            "created_at": int(row["created_at"]),
            "unread": box == "inbox" and not row["read_at"],
        })
    return render(req, "messages.html", box=box, rows=view,
                  unread=messages.unread_count(uid))


@router.get("/messages/compose")
@login_required
def compose(req: Request):
    return render(req, "compose.html", to=req.query.get("to", ""),
                  subject=req.query.get("subject", ""), body="", error="")


@router.post("/messages/compose")
@login_required
def compose_post(req: Request):
    form = req.data()
    try:
        messages.send(int(req.user["id"]), str(form.get("to", "")),
                      str(form.get("subject", "")), str(form.get("body", "")))
    except messages.MessageError as exc:
        return render(req, "compose.html", to=str(form.get("to", "")),
                      subject=str(form.get("subject", "")),
                      body=str(form.get("body", "")), error=str(exc))
    return flash_redirect("/messages", "Message sent.")


@router.get("/messages/<message_id:int>")
@login_required
def read_message(req: Request, message_id: str = "0"):
    uid = int(req.user["id"])
    message = messages.get(int(message_id), uid)
    if message is None:
        return R.error(404, "That message is not in your mailbox.")
    messages.mark_read(int(message_id), uid)
    return render(req, "message.html", message=message,
                  thread=messages.thread_for(message, uid),
                  other=(message["sender_name"]
                         if int(message["recipient_id"]) == uid
                         else message["recipient_name"]))


@router.post("/messages/<message_id:int>/delete")
@login_required
def delete_message(req: Request, message_id: str = "0"):
    messages.delete(int(message_id), int(req.user["id"]))
    return flash_redirect("/messages", "Message deleted.")


@router.post("/api/messages/send")
@login_required
def api_send(req: Request):
    data = req.data()
    try:
        message_id = messages.send(int(req.user["id"]),
                                   str(data.get("to", "")),
                                   str(data.get("subject", "")),
                                   str(data.get("body", "")))
    except messages.MessageError as exc:
        return api_error(str(exc))
    return api_ok(id=message_id)


@router.get("/api/messages/recent")
@login_required
def api_recent(req: Request):
    return api_ok(rows=messages.recent(int(req.user["id"]), 8))


@router.get("/api/social/counts")
@login_required
def counts(req: Request):
    """One poll drives every live element in the chrome.

    Credits and the theme come back too so a second device signed into the
    same account catches up without a reload.
    """
    uid = int(req.user["id"])
    fresh = users.get_by_id(uid) or req.user
    return api_ok(unread=messages.unread_count(uid),
                  requests=friends.pending_count(uid),
                  friends=friends.count_friends(uid),
                  credits=int(fresh["credits"]),
                  theme=users.theme_of(fresh))
