"""First-run seeding: the admin accounts, demo players and world stat rows.

Everything here is idempotent -- it only creates what is missing, so it is safe
to run on every boot.
"""
from __future__ import annotations

import random
import time

from . import config, db
from .models import avatars, catalog, inventory, users, worlds
from .social import comments, follows, friends, messages, posts

DEMO_USERS = [
    ("builderman_x", "Been building since the baseplate days.", "The Workshop"),
    ("RetroKid2007", "ctf or nothing. red team forever.", "Crossroads"),
    ("BlockSmith", "I make hats. Ask me about hats.", "Hat Foundry"),
    ("NoobSlayer99", "top of the leaderboard. usually.", "Dustworks"),
    ("PixelPatty", "Burger Tycoon speedrunner. 8 plots, 8 empires.", "Patty Plains"),
    ("CartPusher", "Standing next to the cart is a full time job.", "Badlands"),
    ("FlagRunner", "If you see me sprinting, follow.", "Blue Base"),
    ("GrillMaster", "Medium rare only. Fight me.", "Kitchen"),
]

DEMO_POSTS = [
    "just unboxed something purple. i am never taking this hat off",
    "who else remembers when the plaza fountain was just a hole?",
    "3-0 on crossroads today. red team stand up",
    "my tycoon hit the golden arches. 26k coins. worth it",
    "looking for a crew for burger tycoon, i have the fry station down",
    "the cart does not push itself people",
    "new shirt in the market and it actually matches my legs for once",
    "does anyone else just stand on the bridge and look at the sky",
    "got sniped from across the whole map. respect honestly",
    "selling nothing, buying everything. as usual",
]

DEMO_COMMENTS = [
    "nice avatar!!",
    "gg earlier, good match",
    "add me for tycoon runs",
    "how did you get that hat",
    "welcome to blockhaven :)",
    "your profile is so clean",
    "we should team up on dustworks",
]


def sync_catalog() -> None:
    """Mirror the Python catalogue into the items table.

    The table is what inventory rows reference, so adding an item to
    ``models/catalog.py`` and restarting is all it takes to ship new content.
    """
    import json
    now = int(time.time())
    rows = []
    for item in catalog.ALL_ITEMS:
        rows.append((
            item["id"], item["name"], item["slot"], int(item.get("price", 0)),
            item.get("rarity", "common"), item.get("description", ""),
            item.get("creator", "BLOCKHAVEN"),
            json.dumps(item.get("data", {}), separators=(",", ":")),
            1 if item.get("price", 0) >= 0 else 0,
            1 if item.get("is_default") else 0,
            int(item.get("sort_order", 0)), now))
    db.executemany(
        "INSERT INTO items(id,name,slot,price,rarity,description,creator,data,"
        "on_sale,is_default,sort_order,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET name=excluded.name, slot=excluded.slot,"
        " price=excluded.price, rarity=excluded.rarity,"
        " description=excluded.description, data=excluded.data,"
        " on_sale=excluded.on_sale, is_default=excluded.is_default,"
        " sort_order=excluded.sort_order", rows)


def seed() -> None:
    db.init_db()
    sync_catalog()
    worlds.ensure_rows()
    _seed_admin()
    _seed_admin_test()
    _seed_demo_users()
    _seed_social()
    users.purge_expired_sessions()


def _seed_admin() -> None:
    admin = users.get_by_username(config.ADMIN_USERNAME)
    if admin is None:
        admin = users.create_user(config.ADMIN_USERNAME, config.ADMIN_PASSWORD,
                                  is_admin=True, credits=250000,
                                  blurb="System operator. If something is on "
                                        "fire, it is probably my fault.")
        print("[seed] created admin account %s" % config.ADMIN_USERNAME)
    uid = int(admin["id"])
    if not db.query_one("SELECT 1 FROM users WHERE id=? AND is_admin=1", (uid,)):
        db.execute("UPDATE users SET is_admin=1 WHERE id=?", (uid,))
    # every admin gets one guaranteed Unusual so the tier system is visible
    if not db.query_one("SELECT 1 FROM inventory WHERE user_id=? AND"
                        " tier='unusual'", (uid,)):
        inventory.grant(uid, "hat_top_hat", source="seed", allow_unusual=False,
                        force_tier="unusual", force_effect="burning")
        inventory.grant(uid, "hat_crown", source="seed", allow_unusual=False,
                        force_tier="unusual", force_effect="starstruck")
        for item_id in ("hat_halo", "face_cool", "shirt_tux", "pants_tux",
                        "use_sniper", "use_rocket", "back_wings"):
            inventory.grant(uid, item_id, source="seed", allow_unusual=False)
        avatar = avatars.raw_avatar(uid)
        hat = inventory.first_of(uid, "hat_top_hat")
        if hat:
            avatars.equip(uid, "hat", hat["id"])
        for slot, item_id in (("face", "face_cool"), ("shirt", "shirt_tux"),
                              ("pants", "pants_tux"), ("back", "back_wings")):
            row = inventory.first_of(uid, item_id)
            if row:
                avatars.equip(uid, slot, row["id"])
        avatars.set_colors(uid, {"head": "#f5cd30", "torso": "#1b2a35",
                                 "left_arm": "#f5cd30", "right_arm": "#f5cd30",
                                 "left_leg": "#1b2a35", "right_leg": "#1b2a35"})
        rifle = inventory.first_of(uid, "use_sniper")
        rocket = inventory.first_of(uid, "use_rocket")
        if rifle:
            avatars.set_hotbar_slot(uid, 3, rifle["id"])
        if rocket:
            avatars.set_hotbar_slot(uid, 4, rocket["id"])
        print("[seed] granted admin starter kit + 2 unusuals")


def _seed_admin_test() -> None:
    """A non-privileged demo account that also carries an Unusual."""
    user = users.get_by_username(config.DEMO_ADMIN_TEST_USERNAME)
    if user is None:
        user = users.create_user(config.DEMO_ADMIN_TEST_USERNAME,
                                 config.DEMO_ADMIN_TEST_PASSWORD,
                                 credits=5000,
                                 blurb="Test account for the Unusual system.")
        print("[seed] created demo account %s"
              % config.DEMO_ADMIN_TEST_USERNAME)
    uid = int(user["id"])
    if not db.query_one("SELECT 1 FROM inventory WHERE user_id=? AND"
                        " tier='unusual'", (uid,)):
        inventory.grant(uid, "hat_propeller", source="seed",
                        allow_unusual=False, force_tier="unusual",
                        force_effect="cloud_nine")
        inventory.grant(uid, "hat_spikes", source="seed", allow_unusual=False,
                        force_tier="unusual", force_effect="circuitry")
        for item_id in ("face_grin", "shirt_hoodie_blue", "pants_jeans",
                        "use_smg"):
            inventory.grant(uid, item_id, source="seed", allow_unusual=False)
        hat = inventory.first_of(uid, "hat_propeller")
        if hat:
            avatars.equip(uid, "hat", hat["id"])
        for slot, item_id in (("face", "face_grin"),
                              ("shirt", "shirt_hoodie_blue"),
                              ("pants", "pants_jeans")):
            row = inventory.first_of(uid, item_id)
            if row:
                avatars.equip(uid, slot, row["id"])
        smg = inventory.first_of(uid, "use_smg")
        if smg:
            avatars.set_hotbar_slot(uid, 3, smg["id"])
        print("[seed] granted admin_test an Unusual Propeller Beanie")


def _seed_demo_users() -> None:
    rng = random.Random(7331)
    hats = [item["id"] for item in catalog.HATS]
    faces = [item["id"] for item in catalog.FACES if item["price"] > 0]
    shirts = [item["id"] for item in catalog.SHIRTS if item["price"] > 0]
    pants = [item["id"] for item in catalog.PANTS if item["price"] > 0]
    palette = [entry["hex"] for entry in catalog.BODY_PALETTE]
    for username, blurb, location in DEMO_USERS:
        if users.get_by_username(username) is not None:
            continue
        user = users.create_user(username, "blockhaven", credits=rng.randint(400, 6000),
                                 blurb=blurb)
        uid = int(user["id"])
        db.execute("UPDATE users SET location=?, created_at=?, last_seen=?"
                   " WHERE id=?",
                   (location, int(time.time()) - rng.randint(86400, 86400 * 400),
                    int(time.time()) - rng.randint(300, 86400 * 3), uid))
        for item_id in (rng.choice(hats), rng.choice(faces), rng.choice(shirts),
                        rng.choice(pants)):
            inventory.grant(uid, item_id, source="seed", allow_unusual=False)
        if rng.random() < 0.4:
            inventory.grant(uid, rng.choice(hats), source="seed",
                            allow_unusual=False, force_tier="unusual",
                            force_effect=rng.choice(catalog.EFFECT_IDS))
        for row in inventory.list_for_user(uid):
            if row["slot"] in ("hat", "face", "shirt", "pants"):
                try:
                    avatars.equip(uid, row["slot"], row["inv_id"])
                except avatars.AvatarError:
                    pass
        avatars.set_colors(uid, {part: rng.choice(palette)
                                 for part in catalog.BODY_PARTS})
        for world in worlds.all_worlds():
            worlds.add_game_stats(uid, world["id"],
                                  kills=rng.randint(0, 90),
                                  deaths=rng.randint(0, 80),
                                  wins=rng.randint(0, 12),
                                  rounds=rng.randint(0, 30),
                                  playtime=rng.randint(0, 40000),
                                  score=rng.randint(0, 4000))
    print("[seed] demo players ready")


def _seed_social() -> None:
    if int(db.scalar("SELECT COUNT(*) FROM posts")) > 0:
        return
    rng = random.Random(4242)
    everyone = db.rows_to_dicts(db.query("SELECT id, username FROM users"))
    if len(everyone) < 3:
        return
    ids = [int(row["id"]) for row in everyone]
    for text in DEMO_POSTS:
        author = rng.choice(ids)
        try:
            post_id = posts.create(author, text)
            db.execute("UPDATE posts SET created_at=? WHERE id=?",
                       (int(time.time()) - rng.randint(600, 86400 * 20), post_id))
            for _ in range(rng.randint(0, 3)):
                posts.toggle_like(post_id, rng.choice(ids))
            if rng.random() < 0.6:
                comments.add_to_post(post_id, rng.choice(ids),
                                     rng.choice(DEMO_COMMENTS))
        except Exception:
            continue
    for _ in range(26):
        a, b = rng.sample(ids, 2)
        try:
            friends.request(a, b)
            if rng.random() < 0.75:
                friends.accept(b, a)
        except Exception:
            continue
    for _ in range(30):
        a, b = rng.sample(ids, 2)
        try:
            follows.follow(a, b)
        except Exception:
            continue
    for _ in range(24):
        a, b = rng.sample(ids, 2)
        try:
            comments.add_to_profile(b, a, rng.choice(DEMO_COMMENTS))
        except Exception:
            continue
    admin = users.get_by_username(config.ADMIN_USERNAME)
    if admin:
        for row in everyone[:4]:
            if int(row["id"]) == int(admin["id"]):
                continue
            try:
                messages.send(int(row["id"]), config.ADMIN_USERNAME,
                              "Hello!", "Loving the new worlds. When is the "
                              "next hat drop?")
            except Exception:
                pass
    print("[seed] social graph ready")
