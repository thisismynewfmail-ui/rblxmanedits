"""Player profiles: 3D preview, stats, wall comments, posts and social actions."""
from __future__ import annotations

from ..http import router as R
from ..http.router import Request
from ..game import registry as game_registry
from ..models import avatars, inventory, users, worlds
from ..social import comments, follows, friends, posts
from .base import (api_error, api_ok, flash_redirect, login_required, render,
                   router)


def _profile_or_404(username: str):
    return users.get_by_username(username)


@router.get("/profile/<username>")
def profile(req: Request, username: str = ""):
    profile_user = _profile_or_404(username)
    if profile_user is None:
        return R.error(404, "There is nobody called '%s' here." % username)
    pid = int(profile_user["id"])
    viewer = int(req.user["id"]) if req.user else 0
    viewer_admin = bool(req.user and req.user["is_admin"])
    inv = inventory.list_for_user(pid)
    by_inv = {int(row["inv_id"]): row for row in inv}

    def visible(field: str) -> bool:
        return users.can_view(profile_user, field, viewer, viewer_admin)

    show_inventory = visible("inventory")
    show_server = visible("server")
    show_online = visible("online")
    playing = game_registry.player_world(pid) if show_server else ""

    pinned = [by_inv[i] for i in users.pinned_of(profile_user) if i in by_inv]
    pinned_ids = {int(row["inv_id"]) for row in pinned}
    # everything else goes in the smaller strip under Statistics
    rest = [row for row in inv if int(row["inv_id"]) not in pinned_ids]

    return render(
        req, "profile.html",
        profile=profile_user,
        avatar=avatars.descriptor(pid, profile_user["username"]),
        is_self=viewer == pid,
        online=users.is_online(profile_user) and show_online,
        show_online=show_online,
        playing=playing,
        friend_status=friends.status_for(viewer, pid) if viewer else "none",
        following=follows.is_following(viewer, pid) if viewer else False,
        follow_counts=follows.counts(pid),
        friends_list=friends.list_friends(pid, 12) if visible("friends_list") else [],
        show_friends=visible("friends_list"),
        friend_count=friends.count_friends(pid),
        mutuals=len(friends.mutual_friends(viewer, pid)) if viewer else 0,
        posts_list=posts.for_user(pid, 10, viewer),
        wall=comments.for_profile(pid, 25),
        wall_count=comments.count_for_profile(pid),
        can_comment=users.can_view(profile_user, "wall", viewer, viewer_admin),
        pinned=pinned,
        pinned_slots=users.MAX_PINNED,
        inventory_strip=rest[:12] if show_inventory else [],
        show_inventory=show_inventory,
        show_stats=visible("stats"),
        inventory_summary=inventory.summary(pid),
        stats=worlds.player_stats(pid),
        favourites=[worlds.get(w) for w in worlds.favourites_of(pid)
                    if worlds.get(w)],
    )


@router.get("/profile")
@login_required
def my_profile(req: Request):
    return R.redirect("/profile/%s" % req.user["username"])


# Deliberately not /profile/edit: routes match in registration order and
# /profile/<username> is registered first, so it would swallow it.
@router.route("/profile-editor", ("GET", "POST"))
@login_required
def edit_profile(req: Request):
    """The profile editor: description, privacy and the three pinned items."""
    uid = int(req.user["id"])
    if req.method == "POST":
        form = req.data()
        users.update_profile(uid, str(form.get("blurb", "")),
                             str(form.get("location", "")))
        users.set_privacy(uid, {field: str(form.get("privacy_%s" % field, ""))
                                for field, _ in users.PRIVACY_LABELS})
        pins = form.get("pinned")
        if not isinstance(pins, list):
            pins = [form.get("pin_%d" % index, 0)
                    for index in range(users.MAX_PINNED)]
        users.set_pinned(uid, pins)
        if req.wants_json:
            return api_ok(pinned=users.pinned_of(users.get_by_id(uid)))
        return flash_redirect("/profile/%s" % req.user["username"],
                              "Profile updated.")
    fresh = users.get_by_id(uid)
    return render(req, "profile_edit.html", page_title="Edit profile",
                  privacy=users.privacy_of(fresh),
                  privacy_labels=users.PRIVACY_LABELS,
                  visibilities=users.VISIBILITIES,
                  pinned=users.pinned_of(fresh),
                  pin_slots=users.MAX_PINNED,
                  owned=inventory.list_for_user(uid))


@router.post("/api/social/friend")
@login_required
def friend_action(req: Request):
    data = req.data()
    target = users.get_by_username(str(data.get("username", "")))
    if target is None:
        return api_error("No such player.")
    action = str(data.get("action", ""))
    uid, tid = int(req.user["id"]), int(target["id"])
    try:
        if action == "request":
            state = friends.request(uid, tid)
        elif action == "accept":
            friends.accept(uid, tid)
            state = "friends"
        elif action == "decline":
            friends.decline(uid, tid)
            state = "none"
        elif action == "remove":
            friends.remove(uid, tid)
            state = "none"
        else:
            return api_error("Unknown action.")
    except friends.FriendError as exc:
        return api_error(str(exc))
    return api_ok(state=state, count=friends.count_friends(uid))


@router.post("/api/social/follow")
@login_required
def follow_action(req: Request):
    data = req.data()
    target = users.get_by_username(str(data.get("username", "")))
    if target is None:
        return api_error("No such player.")
    try:
        following = follows.toggle(int(req.user["id"]), int(target["id"]))
    except follows.FollowError as exc:
        return api_error(str(exc))
    return api_ok(following=following, counts=follows.counts(int(target["id"])))


@router.post("/api/social/post")
@login_required
def create_post(req: Request):
    try:
        post_id = posts.create(int(req.user["id"]), str(req.data().get("body", "")))
    except posts.PostError as exc:
        return api_error(str(exc))
    return api_ok(post=posts.get(post_id))


@router.post("/api/social/post/delete")
@login_required
def delete_post(req: Request):
    try:
        posts.delete(int(req.data().get("id", 0)), int(req.user["id"]),
                     bool(req.user["is_admin"]))
    except posts.PostError as exc:
        return api_error(str(exc))
    return api_ok()


@router.post("/api/social/post/like")
@login_required
def like_post(req: Request):
    try:
        result = posts.toggle_like(int(req.data().get("id", 0)),
                                   int(req.user["id"]))
    except posts.PostError as exc:
        return api_error(str(exc))
    return api_ok(**result)


@router.post("/api/social/post/comment")
@login_required
def comment_post(req: Request):
    data = req.data()
    try:
        comments.add_to_post(int(data.get("id", 0)), int(req.user["id"]),
                             str(data.get("body", "")))
    except comments.CommentError as exc:
        return api_error(str(exc))
    return api_ok(comments=comments.for_post(int(data.get("id", 0))))


@router.get("/api/social/post/comments")
def list_post_comments(req: Request):
    try:
        post_id = int(req.query.get("id", 0))
    except ValueError:
        return api_error("Bad id.")
    return api_ok(comments=comments.for_post(post_id))


@router.post("/api/profile/comment")
@login_required
def profile_comment(req: Request):
    data = req.data()
    target = users.get_by_username(str(data.get("username", "")))
    if target is None:
        return api_error("No such profile.")
    if not users.can_view(target, "wall", int(req.user["id"]),
                          bool(req.user["is_admin"])):
        return api_error("%s has closed their profile comments."
                         % target["username"], 403)
    try:
        comments.add_to_profile(int(target["id"]), int(req.user["id"]),
                                str(data.get("body", "")))
    except comments.CommentError as exc:
        return api_error(str(exc))
    return api_ok(wall=comments.for_profile(int(target["id"]), 25))


@router.post("/api/profile/comment/delete")
@login_required
def profile_comment_delete(req: Request):
    try:
        comments.delete_profile_comment(int(req.data().get("id", 0)),
                                        int(req.user["id"]),
                                        bool(req.user["is_admin"]))
    except comments.CommentError as exc:
        return api_error(str(exc))
    return api_ok()


@router.get("/api/avatar/<username>")
def avatar_json(req: Request, username: str = ""):
    target = users.get_by_username(username)
    if target is None:
        return api_error("No such player.", 404)
    return api_ok(avatar=avatars.descriptor(int(target["id"]),
                                            target["username"]))
