#!/usr/bin/env python3
"""HTTP-level tests for the website.

Exercises the flows a browser performs -- registration, the starter kit, the
market (including the server-side price and ownership checks), avatar slots,
the social features, messaging, and the administrator dashboard's access
control -- against a running server.

    python3 tools/sitetests.py [--port 8972]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import string
import sys
from http.client import HTTPConnection
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

PASSED: List[str] = []
FAILED: List[str] = []


def check(name: str, condition: bool, detail: Any = "") -> bool:
    if condition:
        PASSED.append(name)
        print("  PASS  %s" % name)
    else:
        FAILED.append(name)
        print("  FAIL  %s  %s" % (name, str(detail)[:200]))
    return bool(condition)


class Client:
    def __init__(self, host: str, port: int):
        self.host, self.port = host, port
        self.cookie = ""
        self.csrf = ""

    def request(self, method: str, path: str, body: Optional[str] = None,
                json_body: bool = False,
                headers: Optional[Dict[str, str]] = None) -> Tuple[int, bytes, Dict[str, str]]:
        conn = HTTPConnection(self.host, self.port, timeout=15)
        head = dict(headers or {})
        if self.cookie:
            head["Cookie"] = self.cookie
        if body is not None:
            head.setdefault("Content-Type", "application/json" if json_body
                            else "application/x-www-form-urlencoded")
            if self.csrf and "X-CSRF-Token" not in head:
                head["X-CSRF-Token"] = self.csrf
        conn.request(method, path, body, head)
        response = conn.getresponse()
        data = response.read()
        out_headers = {k.lower(): v for k, v in response.getheaders()}
        if "set-cookie" in out_headers:
            self.cookie = out_headers["set-cookie"].split(";")[0]
        status = response.status
        conn.close()
        return status, data, out_headers

    def get(self, path: str) -> Tuple[int, str]:
        status, data, _ = self.request("GET", path)
        return status, data.decode("utf-8", "replace")

    def api(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        status, data, _ = self.request("POST", path, json.dumps(payload), True)
        try:
            return json.loads(data.decode())
        except Exception:
            return {"ok": False, "error": "bad json (%s)" % status, "status": status}

    def get_api(self, path: str) -> Dict[str, Any]:
        status, data, _ = self.request("GET", path, None, False,
                                       {"X-Requested-With": "fetch"})
        try:
            return json.loads(data.decode())
        except Exception:
            return {"ok": False, "error": "bad json (%s)" % status}

    def refresh_csrf(self) -> None:
        _, html = self.get("/")
        match = re.search(r'csrf: "([^"]*)"', html)
        self.csrf = match.group(1) if match else ""

    def login(self, username: str, password: str) -> int:
        status, _, _ = self.request(
            "POST", "/login", urlencode({"username": username,
                                         "password": password}))
        self.refresh_csrf()
        return status


def random_name() -> str:
    return "test_" + "".join(random.choice(string.ascii_lowercase) for _ in range(8))


def run(host: str, port: int) -> int:
    print("== registration and the starter kit ==")
    client = Client(host, port)
    name = random_name()
    status, _, _ = client.request("POST", "/register", urlencode(
        {"username": name, "password": "hunter22", "confirm": "hunter22"}))
    if not check("register: a new account is created", status in (302, 303),
                 status):
        print("  (registration was refused -- the per-hour limit may have been "
              "hit; restart the server or wait before re-running)")
        return 1
    client.refresh_csrf()
    inventory = client.get_api("/api/inventory")
    check("register: the account starts with 2,000 credits",
          inventory.get("balance") == 2000, inventory.get("balance"))
    owned = {item["item_id"] for item in inventory.get("items", [])}
    check("register: the starter kit is granted",
          {"use_pistol", "use_shotgun", "use_stick"} <= owned, sorted(owned))
    avatar = client.get_api("/api/avatar")
    hotbar = [entry["item_id"] if entry else None
              for entry in avatar.get("avatar", {}).get("hotbar", [])]
    check("register: the hotbar is pre-filled with the starter weapons",
          hotbar[:3] == ["use_pistol", "use_shotgun", "use_stick"], hotbar)
    check("register: five hotbar slots exist", len(hotbar) == 5, hotbar)

    print("\n== duplicate accounts and validation ==")
    fresh = Client(host, port)
    status, data, _ = fresh.request("POST", "/register", urlencode(
        {"username": name, "password": "hunter22", "confirm": "hunter22"}))
    check("register: duplicate usernames are refused",
          b"already taken" in data, status)
    status, data, _ = fresh.request("POST", "/register", urlencode(
        {"username": "bad name!", "password": "hunter22", "confirm": "hunter22"}))
    check("register: invalid usernames are refused", b"Usernames must be" in data,
          status)
    status, data, _ = fresh.request("POST", "/register", urlencode(
        {"username": random_name(), "password": "abc", "confirm": "abc"}))
    check("register: short passwords are refused", b"at least" in data, status)

    print("\n== market rules ==")
    result = client.api("/api/market/buy", {"item_id": "hat_traffic_cone"})
    check("market: buying charges the catalogue price",
          result.get("ok") and result.get("balance") == 2000 - 90, result)
    check("market: a purchase always has a tier",
          result.get("tier") in ("normal", "unusual"), result.get("tier"))
    expensive = client.api("/api/market/buy", {"item_id": "hat_halo"})
    check("market: you cannot buy what you cannot afford",
          not expensive.get("ok") and "credits" in expensive.get("error", ""),
          expensive)
    unknown = client.api("/api/market/buy", {"item_id": "hat_does_not_exist"})
    check("market: unknown items are rejected", not unknown.get("ok"), unknown)
    free_again = client.api("/api/market/buy", {"item_id": "use_pistol"})
    check("market: free starter items cannot be farmed",
          not free_again.get("ok"), free_again)

    print("\n== avatar ownership checks ==")
    inventory = client.get_api("/api/inventory")
    cone = next((i for i in inventory["items"] if i["item_id"] == "hat_traffic_cone"),
                None)
    equip = client.api("/api/avatar/equip", {"slot": "hat",
                                             "inv_id": cone["inv_id"]})
    check("avatar: you can wear something you own", equip.get("ok"), equip)
    wrong_slot = client.api("/api/avatar/equip", {"slot": "shirt",
                                                  "inv_id": cone["inv_id"]})
    check("avatar: an item cannot go in the wrong slot",
          not wrong_slot.get("ok"), wrong_slot)
    stolen = client.api("/api/avatar/equip", {"slot": "hat", "inv_id": 1})
    check("avatar: you cannot wear another player's copy",
          not stolen.get("ok"), stolen)
    bad_colour = client.api("/api/avatar/colors", {"colors": {"head": "javascript:1"}})
    check("avatar: colours are validated", not bad_colour.get("ok"), bad_colour)
    good_colour = client.api("/api/avatar/colors", {"colors": {"head": "#12ab34"}})
    check("avatar: a valid colour is stored",
          good_colour.get("ok") and good_colour["colors"]["head"] == "#12ab34",
          good_colour)
    hotbar_theft = client.api("/api/avatar/hotbar", {"index": 4, "inv_id": 1})
    check("avatar: the hotbar rejects unowned items",
          not hotbar_theft.get("ok"), hotbar_theft)

    print("\n== social features ==")
    post = client.api("/api/social/post", {"body": "hello from the site tests"})
    check("social: posting works", post.get("ok"), post)
    post_id = (post.get("post") or {}).get("id")
    like = client.api("/api/social/post/like", {"id": post_id})
    check("social: liking works", like.get("ok") and like.get("likes") == 1, like)
    comment = client.api("/api/social/post/comment", {"id": post_id, "body": "nice"})
    check("social: commenting works", comment.get("ok"), comment)
    friend = client.api("/api/social/friend", {"action": "request",
                                               "username": "builderman_x"})
    check("social: a friend request is recorded",
          friend.get("ok") and friend.get("state") in ("pending_out", "friends"),
          friend)
    self_friend = client.api("/api/social/friend", {"action": "request",
                                                    "username": name})
    check("social: you cannot befriend yourself", not self_friend.get("ok"),
          self_friend)
    follow = client.api("/api/social/follow", {"username": "PixelPatty"})
    check("social: following works", follow.get("ok"), follow)
    wall = client.api("/api/profile/comment", {"username": "builderman_x",
                                               "body": "great base"})
    check("social: profile comments work", wall.get("ok"), wall)

    print("\n== messaging ==")
    sent = client.api("/api/messages/send", {"to": "builderman_x",
                                             "subject": "hello",
                                             "body": "testing the mail"})
    check("messages: a message can be sent", sent.get("ok"), sent)
    nobody = client.api("/api/messages/send", {"to": "not_a_real_user",
                                               "subject": "x", "body": "y"})
    check("messages: unknown recipients are refused", not nobody.get("ok"), nobody)
    other = Client(host, port)
    other.login("builderman_x", "blockhaven")
    counts = other.get_api("/api/social/counts")
    status, inbox_html = other.get("/messages")
    check("messages: it arrives in the recipient's inbox",
          "testing the mail" in inbox_html or "hello" in inbox_html, status)
    check("messages: the unread counter moves",
          other.get_api("/api/social/counts").get("unread", 0) >= 1, counts)
    match = re.search(r'/messages/(\d+)', inbox_html)
    if match:
        message_id = match.group(1)
        status, _body = client.get("/messages/%s" % message_id)
        check("messages: the sender can read their own message", status == 200,
              status)
        snooper = Client(host, port)
        snooper.login("PixelPatty", "blockhaven")
        status, _ = snooper.get("/messages/%s" % message_id)
        check("messages: an unrelated player cannot read someone else's mail",
              status == 404, status)

    print("\n== admin access control ==")
    status, _, headers = client.request("GET", "/admin-dashboard")
    check("admin: normal players are redirected away from the dashboard",
          status in (302, 303) and headers.get("location", "").endswith("/"),
          "%s %s" % (status, headers.get("location")))
    denied = client.api("/api/admin/credits", {"username": name, "amount": 999999,
                                               "mode": "add"})
    check("admin: normal players cannot grant themselves credits",
          not denied.get("ok"), denied)
    balance_now = client.get_api("/api/inventory").get("balance")
    check("admin: the balance really did not change", balance_now == 2000 - 90,
          balance_now)

    admin = Client(host, port)
    admin.login("admin_system", "passman69")
    status, html = admin.get("/admin-dashboard")
    check("admin: administrators can open the dashboard", status == 200, status)
    granted = admin.api("/api/admin/credits", {"username": name, "amount": 500,
                                               "mode": "add", "reason": "test"})
    check("admin: administrators can adjust credits",
          granted.get("ok") and granted.get("balance") == 2000 - 90 + 500, granted)
    unusual = admin.api("/api/admin/grant", {"username": name,
                                             "item_id": "hat_crown",
                                             "tier": "unusual",
                                             "effect": "frostbite"})
    check("admin: administrators can grant an Unusual hat",
          unusual.get("ok") and unusual["item"]["tier"] == "unusual", unusual)
    bad_unusual = admin.api("/api/admin/grant", {"username": name,
                                                 "item_id": "shirt_tux",
                                                 "tier": "unusual"})
    check("admin: only hats can be Unusual", not bad_unusual.get("ok"), bad_unusual)

    print("\n== csrf ==")
    raw = Client(host, port)
    raw.login(name, "hunter22")
    raw.csrf = "not-the-right-token"
    forged = raw.api("/api/market/buy", {"item_id": "hat_pot"})
    check("csrf: a request with a bad token is rejected", not forged.get("ok"),
          forged)

    print("\n== page smoke test ==")
    pages = ["/", "/worlds", "/market", "/users", "/help", "/inventory",
             "/avatar", "/friends", "/messages", "/settings",
             "/profile/%s" % name, "/inventory/%s" % name,
             "/worlds/capture_the_flag", "/worlds/burger_tycoon",
             "/worlds/fortress_team_2", "/capture_the_flag", "/burger_tycoon",
             "/fortress_team_2", "/search?q=hat", "/api/catalog",
             "/api/worlds/status"]
    broken = []
    for page in pages:
        status, _ = client.get(page)
        if status != 200:
            broken.append((page, status))
    check("pages: every page renders", not broken, broken)

    print("\n==================== %d passed, %d failed ===================="
          % (len(PASSED), len(FAILED)))
    for item in FAILED:
        print("  FAILED:", item)
    return 1 if FAILED else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8972)
    args = parser.parse_args()
    return run(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
