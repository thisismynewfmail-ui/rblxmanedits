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


def _compose_return(req: Request, supplied: str = "") -> str:
    """Where "send" and "cancel" should land.

    Composing is almost always an interruption -- you were reading a profile,
    or the inbox, or a thread -- so the useful destination is wherever the
    writer came from rather than the inbox every time.  The candidate is taken
    from the form, then the query string, then the Referer, and it has to be a
    path on this site that is not the composer itself; anything else falls
    back to the inbox.
    """
    for candidate in (supplied, req.query.get("back", ""),
                      req.headers.get("referer", "")):
        candidate = (candidate or "").strip()
        if not candidate:
            continue
        if candidate.startswith("http"):
            # keep only the path of a same-origin referer
            rest = candidate.split("//", 1)[-1]
            slash = rest.find("/")
            candidate = rest[slash:] if slash >= 0 else "/"
        if (candidate.startswith("/") and not candidate.startswith("//")
                and not candidate.startswith("/messages/compose")):
            return candidate
    return "/messages"


@router.get("/messages/compose")
@login_required
def compose(req: Request):
    return render(req, "compose.html", to=req.query.get("to", ""),
                  subject=req.query.get("subject", ""), body="", error="",
                  back=_compose_return(req))


@router.post("/messages/compose")
@login_required
def compose_post(req: Request):
    form = req.data()
    back = _compose_return(req, str(form.get("back", "")))
    try:
        messages.send(int(req.user["id"]), str(form.get("to", "")),
                      str(form.get("subject", "")), str(form.get("body", "")))
    except messages.MessageError as exc:
        return render(req, "compose.html", to=str(form.get("to", "")),
                      subject=str(form.get("subject", "")),
                      body=str(form.get("body", "")), error=str(exc),
                      back=back)
    return flash_redirect(back, "Message sent.")


@router.get("/api/users/suggest")
@login_required
def suggest_users(req: Request):
    """Name completions for the composer's To box.

    Friends first and always -- they are who you actually write to -- then
    anyone else whose name matches, so a new correspondent is still findable.
    An empty term returns the friends list, which makes the box useful before
    a single key is pressed.
    """
    term = (req.query.get("q", "") or "").strip().lower()
    uid = int(req.user["id"])
    seen = {req.user["username"].lower()}
    out = []

    def take(rows, is_friend):
        for row in rows:
            name = str(row["username"])
            if name.lower() in seen:
                continue
            if term and term not in name.lower():
                continue
            seen.add(name.lower())
            out.append({"username": name, "friend": is_friend,
                        "online": users.is_online(row)})
            if len(out) >= 8:
                return True
        return False

    if not take(friends.list_friends(uid, 100), True):
        # users.search with an empty term is "everyone, most recently seen
        # first", which is the right second list both before and after the
        # writer starts typing.
        take(users.search(term, 60), False)
    return api_ok(users=out, term=term)


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
