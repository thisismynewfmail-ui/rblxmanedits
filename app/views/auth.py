"""Sign up, sign in, sign out and account settings."""
from __future__ import annotations

from .. import config, db
from ..http import router as R
from ..http.router import Request
from ..models import users
from .base import flash_redirect, login_required, render, router

SAFE_NEXT_PREFIXES = ("/",)


def _safe_next(value: str) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


@router.route("/login", ("GET", "POST"))
def login(req: Request):
    if req.user is not None and req.method == "GET":
        return R.redirect("/")
    next_url = _safe_next(req.query.get("next", "/"))
    if req.method == "GET":
        return render(req, "login.html", next_url=next_url, error="")
    form = req.data()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    ip = req.remote_addr
    # Two limits: a tight one per account (that is what stops brute forcing)
    # and a loose one per address, so a whole household behind one router --
    # or a test run -- does not lock itself out.
    if not db.rate_limit("login:user:%s" % username.lower()[:40], 12, 300):
        return render(req, "login.html", next_url=next_url,
                      error="Too many attempts for that account. Wait a minute.")
    if not db.rate_limit("login:ip:%s" % ip, 150, 300):
        return render(req, "login.html", next_url=next_url,
                      error="Too many attempts from this address. Wait a minute.")
    try:
        user = users.authenticate(username, password)
    except users.AuthError as exc:
        db.audit(None, "auth.fail", username, {"ip": ip})
        return render(req, "login.html", next_url=next_url, error=str(exc),
                      status=401)
    session = users.start_session(int(user["id"]),
                                  req.headers.get("user-agent", ""), ip)
    db.audit(int(user["id"]), "auth.login", user["username"], {"ip": ip})
    response = R.redirect(_safe_next(str(form.get("next", next_url))))
    response.set_cookie(config.SESSION_COOKIE, session["token"],
                        max_age=config.SESSION_TTL)
    return response


@router.route("/register", ("GET", "POST"))
def register(req: Request):
    if req.user is not None and req.method == "GET":
        return R.redirect("/")
    if req.method == "GET":
        return render(req, "register.html", error="", username="")
    form = req.data()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    confirm = str(form.get("confirm", ""))
    if not db.rate_limit("register:%s" % req.remote_addr, 20, 3600):
        return render(req, "register.html", username=username,
                      error="Too many accounts created from here recently.")
    if password != confirm:
        return render(req, "register.html", username=username,
                      error="Those passwords do not match.")
    try:
        user = users.create_user(username, password)
    except users.AuthError as exc:
        return render(req, "register.html", username=username, error=str(exc))
    session = users.start_session(int(user["id"]),
                                  req.headers.get("user-agent", ""),
                                  req.remote_addr)
    response = R.redirect("/avatar?welcome=1")
    response.set_cookie(config.SESSION_COOKIE, session["token"],
                        max_age=config.SESSION_TTL)
    return response


@router.route("/logout", ("GET", "POST"))
def logout(req: Request):
    if req.session:
        users.end_session(req.session["token"])
    response = R.redirect("/login")
    response.delete_cookie(config.SESSION_COOKIE)
    return response


@router.route("/settings", ("GET", "POST"))
@login_required
def settings(req: Request):
    user = req.user
    if req.method == "GET":
        return render(req, "settings.html", error="", ok="")
    form = req.data()
    action = str(form.get("action", ""))
    if action == "profile":
        users.update_profile(int(user["id"]), str(form.get("blurb", "")),
                             str(form.get("location", "")))
        return flash_redirect("/settings", "Profile updated.")
    if action == "password":
        try:
            users.change_password(int(user["id"]),
                                  str(form.get("current", "")),
                                  str(form.get("new", "")))
        except users.AuthError as exc:
            return flash_redirect("/settings", str(exc), "bad")
        response = R.redirect("/login?msg=Password%20changed.%20Sign%20in%20again.")
        response.delete_cookie(config.SESSION_COOKIE)
        return response
    return flash_redirect("/settings", "Nothing to do.", "bad")
