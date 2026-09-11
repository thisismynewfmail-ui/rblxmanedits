"""The central item catalogue.

Everything wearable, holdable or purchasable in BLOCKHAVEN lives here.  The
catalogue is data only -- it is synchronised into the ``items`` table on boot,
so adding a new hat later is a matter of appending one dict and restarting.

Geometry convention (matches static/js/engine + app/game):
  * 1 unit == 1 "stud".  +Y is up, the avatar faces +Z.
  * Avatar root sits at the feet.  Torso 2x2x1, head 1.4x1.2x1.2,
    limbs 1x2x1.  Total height 5.2.
  * Hat parts are expressed relative to the TOP CENTRE OF THE HEAD (0,0,0).
  * Back parts are relative to the centre of the torso's back face.
  * Held ("usable") parts are relative to the right hand grip point, with the
    barrel pointing towards +Z.

Primitive types understood by the renderer and by the server side collision
helpers: box, cyl (cylinder, Y axis), sph (sphere), cone, wedge.
"""
from __future__ import annotations

from typing import Any, Dict, List

# --------------------------------------------------------------------- tiers
TIERS: Dict[str, Dict[str, Any]] = {
    "normal": {
        "id": "normal",
        "label": "Normal",
        "color": "#e8b71a",
        "text": "#4a3800",
        "border": "#b8900d",
        "glow": "#ffd95e",
        "rank": 0,
    },
    "unusual": {
        "id": "unusual",
        "label": "Unusual",
        "color": "#8b3fd6",
        "text": "#f3e6ff",
        "border": "#5d1f9c",
        "glow": "#c78bff",
        "rank": 1,
    },
}

# ------------------------------------------------------------------ effects
# Particle recipes for Unusual hats.  Consumed by static/js/engine/particles.js
UNUSUAL_EFFECTS: Dict[str, Dict[str, Any]] = {
    "burning": {
        "name": "Burning Flames", "rate": 26, "life": [0.55, 0.95],
        "size": [0.30, 0.62], "grow": -0.55, "gravity": 1.9,
        "spread": 0.34, "rise": [1.6, 2.6], "blend": "add", "spin": 2.2,
        "colors": ["#ffd24a", "#ff9422", "#ff5311", "#8f2a06"],
        "shape": "flame", "radius": 0.42,
    },
    "scorching": {
        "name": "Scorching Flames", "rate": 34, "life": [0.5, 0.85],
        "size": [0.24, 0.5], "grow": -0.4, "gravity": 2.6,
        "spread": 0.5, "rise": [2.1, 3.3], "blend": "add", "spin": 3.4,
        "colors": ["#ffffff", "#ffe66d", "#ff8c1a", "#e02b00"],
        "shape": "flame", "radius": 0.5,
    },
    "cloud_nine": {
        "name": "Cloud Nine", "rate": 9, "life": [1.5, 2.4],
        "size": [0.5, 0.95], "grow": 0.34, "gravity": 0.12,
        "spread": 0.7, "rise": [0.25, 0.6], "blend": "normal", "spin": 0.5,
        "colors": ["#ffffff", "#eef4ff", "#d7e6ff"],
        "shape": "puff", "radius": 0.6,
    },
    "starstruck": {
        "name": "Starstruck", "rate": 14, "life": [0.9, 1.5],
        "size": [0.20, 0.42], "grow": -0.1, "gravity": -0.4,
        "spread": 0.55, "rise": [0.4, 1.1], "blend": "add", "spin": 4.5,
        "colors": ["#fff9c4", "#ffe14d", "#ffc400", "#fff"],
        "shape": "star", "radius": 0.66, "orbit": 1.1,
    },
    "void_mist": {
        "name": "Void Mist", "rate": 16, "life": [1.1, 1.9],
        "size": [0.38, 0.72], "grow": 0.18, "gravity": 0.25,
        "spread": 0.46, "rise": [0.5, 1.0], "blend": "add", "spin": 1.2,
        "colors": ["#c78bff", "#8b3fd6", "#4b1580", "#2a0a4a"],
        "shape": "puff", "radius": 0.52,
    },
    "frostbite": {
        "name": "Frostbite", "rate": 15, "life": [1.3, 2.1],
        "size": [0.18, 0.34], "grow": -0.05, "gravity": -1.4,
        "spread": 0.62, "rise": [0.1, 0.45], "blend": "normal", "spin": 2.8,
        "colors": ["#ffffff", "#cdeaff", "#8fd0ff", "#5aa9e6"],
        "shape": "flake", "radius": 0.7,
    },
    "circuitry": {
        "name": "Circuitry", "rate": 20, "life": [0.6, 1.0],
        "size": [0.14, 0.26], "grow": -0.1, "gravity": 0.0,
        "spread": 0.2, "rise": [0.0, 0.3], "blend": "add", "spin": 6.0,
        "colors": ["#b9ffcf", "#37f28a", "#0bbd63", "#e8fff2"],
        "shape": "spark", "radius": 0.78, "orbit": 2.4,
    },
    "bubbly": {
        "name": "Bubbly", "rate": 11, "life": [1.4, 2.3],
        "size": [0.22, 0.48], "grow": 0.1, "gravity": -0.8,
        "spread": 0.5, "rise": [0.6, 1.2], "blend": "normal", "spin": 1.0,
        "colors": ["#dff6ff", "#a9e4ff", "#ffffff"],
        "shape": "bubble", "radius": 0.5,
    },
    "ember_storm": {
        "name": "Ember Storm", "rate": 22, "life": [0.9, 1.6],
        "size": [0.12, 0.3], "grow": -0.2, "gravity": 1.1,
        "spread": 0.75, "rise": [1.0, 2.0], "blend": "add", "spin": 3.0,
        "colors": ["#ffb347", "#ff6b1a", "#7a2f0a", "#3d1c0a"],
        "shape": "spark", "radius": 0.6,
    },
    "sunbeam": {
        "name": "Sunbeam", "rate": 12, "life": [1.0, 1.7],
        "size": [0.30, 0.6], "grow": 0.05, "gravity": -0.2,
        "spread": 0.3, "rise": [0.2, 0.55], "blend": "add", "spin": 1.6,
        "colors": ["#fff6c9", "#ffd75e", "#ffae19"],
        "shape": "ray", "radius": 0.72, "orbit": 0.9,
    },
    "toxic_haze": {
        "name": "Toxic Haze", "rate": 17, "life": [1.2, 2.0],
        "size": [0.34, 0.66], "grow": 0.22, "gravity": 0.3,
        "spread": 0.5, "rise": [0.35, 0.85], "blend": "add", "spin": 0.9,
        "colors": ["#e8ffb0", "#9ade3a", "#4e9e17", "#1f4d08"],
        "shape": "puff", "radius": 0.55,
    },
    "static_charge": {
        "name": "Static Charge", "rate": 24, "life": [0.35, 0.7],
        "size": [0.16, 0.34], "grow": -0.3, "gravity": 0.0,
        "spread": 0.9, "rise": [0.0, 0.2], "blend": "add", "spin": 8.0,
        "colors": ["#ffffff", "#bfe9ff", "#4fa8ff", "#1450b8"],
        "shape": "spark", "radius": 0.8,
    },
}

EFFECT_IDS: List[str] = list(UNUSUAL_EFFECTS.keys())

# ------------------------------------------------------------------- colours
BODY_PALETTE: List[Dict[str, str]] = [
    {"name": "Bright yellow", "hex": "#f5cd30"},
    {"name": "Cool yellow", "hex": "#f3cf9b"},
    {"name": "Brick yellow", "hex": "#d7c59a"},
    {"name": "Nougat", "hex": "#cc8e69"},
    {"name": "Light orange", "hex": "#f0b47b"},
    {"name": "Bright orange", "hex": "#d3592b"},
    {"name": "Bright red", "hex": "#c4281c"},
    {"name": "Really red", "hex": "#ff1b1b"},
    {"name": "Hot pink", "hex": "#ff98dc"},
    {"name": "Carnation pink", "hex": "#ff5f9e"},
    {"name": "Bright violet", "hex": "#6b327c"},
    {"name": "Lilac", "hex": "#a75fd1"},
    {"name": "Bright blue", "hex": "#0d69ac"},
    {"name": "Deep blue", "hex": "#0b3b7a"},
    {"name": "Pastel blue", "hex": "#b4d2e4"},
    {"name": "Sand blue", "hex": "#6c81a5"},
    {"name": "Teal", "hex": "#008f9c"},
    {"name": "Bright green", "hex": "#4b974b"},
    {"name": "Dark green", "hex": "#287f47"},
    {"name": "Lime", "hex": "#a4bd47"},
    {"name": "Earth green", "hex": "#27462d"},
    {"name": "Reddish brown", "hex": "#7c503a"},
    {"name": "Dark brown", "hex": "#40292a"},
    {"name": "White", "hex": "#f2f3f3"},
    {"name": "Light stone", "hex": "#c8cbcd"},
    {"name": "Medium stone", "hex": "#a3a2a5"},
    {"name": "Dark stone", "hex": "#6d6e6c"},
    {"name": "Really black", "hex": "#1b2a35"},
]

DEFAULT_COLORS: Dict[str, str] = {
    "head": "#f5cd30",
    "torso": "#0d69ac",
    "left_arm": "#f5cd30",
    "right_arm": "#f5cd30",
    "left_leg": "#a4bd47",
    "right_leg": "#a4bd47",
}

BODY_PARTS = ["head", "torso", "left_arm", "right_arm", "left_leg", "right_leg"]

SLOTS = ["face", "hat", "shirt", "pants", "back"]
HOTBAR_SIZE = 5

SLOT_LABELS = {
    "face": "Face", "hat": "Hat", "shirt": "Shirt", "pants": "Pants",
    "back": "Back", "usable": "Usable",
}


def _hat(item_id, name, price, parts, desc, rarity="common", order=0):
    return {"id": item_id, "name": name, "slot": "hat", "price": price,
            "rarity": rarity, "description": desc, "sort_order": order,
            "data": {"parts": parts}}


# --------------------------------------------------------------------- hats
HATS: List[Dict[str, Any]] = [
    _hat("hat_red_cap", "Classic Red Cap", 250, [
        {"t": "sph", "p": [0, 0.28, 0], "s": [1.62, 1.05, 1.62], "c": "#5a2d22"},
        {"t": "box", "p": [0, 0.07, 0.92], "s": [1.44, 0.16, 0.86], "c": "#c4281c"},
        {"t": "sph", "p": [0, 0.72, 0], "s": [0.3, 0.3, 0.3], "c": "#c4281c"},
        {"t": "box", "p": [0, 0.32, 0.74], "s": [0.5, 0.42, 0.08], "c": "#f2f3f3",
         "decal": "letter_R"},
    ], "The cap every builder owns. Faded, beloved, iconic.", "common", 1),

    _hat("hat_top_hat", "Silk Top Hat", 750, [
        {"t": "cyl", "p": [0, 0.06, 0], "s": [2.0, 0.12, 2.0], "c": "#151515"},
        {"t": "cyl", "p": [0, 0.72, 0], "s": [1.28, 1.32, 1.28], "c": "#1b2a35"},
        {"t": "cyl", "p": [0, 0.30, 0], "s": [1.33, 0.2, 1.33], "c": "#8b1a1a"},
    ], "For the distinguished block about town.", "uncommon", 2),

    _hat("hat_hard_hat", "Builder's Hard Hat", 300, [
        {"t": "sph", "p": [0, 0.34, 0], "s": [1.62, 1.18, 1.62], "c": "#f2b01e"},
        {"t": "box", "p": [0, 0.12, 0.86], "s": [1.35, 0.14, 0.7], "c": "#f2b01e"},
        {"t": "box", "p": [0, 0.86, 0], "s": [0.22, 0.2, 1.3], "c": "#d99a10"},
    ], "Safety first. Officially issued by the Build Corps.", "common", 3),

    _hat("hat_beanie", "Winter Beanie", 180, [
        {"t": "sph", "p": [0, 0.22, 0], "s": [1.58, 1.0, 1.58], "c": "#2f5fa8"},
        {"t": "cyl", "p": [0, 0.06, 0], "s": [1.66, 0.3, 1.66], "c": "#e8e8e8"},
        {"t": "sph", "p": [0, 0.78, 0], "s": [0.44, 0.44, 0.44], "c": "#e8e8e8"},
    ], "Knitted by somebody's grandmother. Extremely warm.", "common", 4),

    _hat("hat_crown", "Golden Crown", 1500, [
        {"t": "cyl", "p": [0, 0.28, 0], "s": [1.5, 0.56, 1.5], "c": "#f5c518",
         "mat": "metal"},
        {"t": "box", "p": [0, 0.68, 0.62], "s": [0.26, 0.46, 0.2], "c": "#f5c518", "mat": "metal"},
        {"t": "box", "p": [0, 0.68, -0.62], "s": [0.26, 0.46, 0.2], "c": "#f5c518", "mat": "metal"},
        {"t": "box", "p": [0.62, 0.68, 0], "s": [0.2, 0.46, 0.26], "c": "#f5c518", "mat": "metal"},
        {"t": "box", "p": [-0.62, 0.68, 0], "s": [0.2, 0.46, 0.26], "c": "#f5c518", "mat": "metal"},
        {"t": "sph", "p": [0, 0.42, 0.72], "s": [0.3, 0.3, 0.3], "c": "#c4281c"},
    ], "Heavy is the head. Worth every credit.", "rare", 5),

    _hat("hat_cowboy", "Ten Gallon Hat", 600, [
        {"t": "cyl", "p": [0, 0.1, 0], "s": [2.3, 0.14, 1.9], "c": "#8a5a2b"},
        {"t": "cyl", "p": [0, 0.55, 0], "s": [1.3, 0.9, 1.3], "c": "#9c6733"},
        {"t": "cyl", "p": [0, 0.28, 0], "s": [1.36, 0.18, 1.36], "c": "#4a2f18"},
    ], "Yeehaw, partner. Smells faintly of hay.", "uncommon", 6),

    _hat("hat_pot", "Cooking Pot", 120, [
        {"t": "cyl", "p": [0, 0.5, 0], "s": [1.7, 1.0, 1.7], "c": "#8f9296", "mat": "metal"},
        {"t": "cyl", "p": [0, 1.02, 0], "s": [1.8, 0.12, 1.8], "c": "#6f7276", "mat": "metal"},
        {"t": "box", "p": [1.0, 0.55, 0], "s": [0.5, 0.14, 0.16], "c": "#6f7276", "mat": "metal"},
    ], "Doubles as a helmet. Mostly.", "common", 7),

    _hat("hat_horns", "Ruin Horns", 900, [
        {"t": "cone", "p": [0.58, 0.5, 0.1], "s": [0.42, 1.0, 0.42], "c": "#8b1e1e",
         "r": [0, 0, -0.4]},
        {"t": "cone", "p": [-0.58, 0.5, 0.1], "s": [0.42, 1.0, 0.42], "c": "#8b1e1e",
         "r": [0, 0, 0.4]},
        {"t": "box", "p": [0, 0.12, 0], "s": [1.5, 0.24, 1.5], "c": "#3a0d0d"},
    ], "Recovered from the lava caves. Still slightly warm.", "rare", 8),

    _hat("hat_propeller", "Propeller Beanie", 450, [
        {"t": "sph", "p": [0, 0.2, 0], "s": [1.5, 0.9, 1.5], "c": "#c4281c"},
        {"t": "cyl", "p": [0, 0.68, 0], "s": [0.16, 0.5, 0.16], "c": "#f2f3f3"},
        {"t": "box", "p": [0, 0.92, 0], "s": [2.0, 0.08, 0.24], "c": "#0d69ac",
         "spin": 8.0},
        {"t": "box", "p": [0, 0.92, 0], "s": [0.24, 0.08, 2.0], "c": "#f5cd30",
         "spin": 8.0},
    ], "Aerodynamically useless. Socially essential.", "uncommon", 9),

    _hat("hat_visor", "Neon Visor", 350, [
        {"t": "box", "p": [0, 0.05, 0], "s": [1.62, 0.26, 1.62], "c": "#22262b"},
        {"t": "box", "p": [0, -0.12, 0.78], "s": [1.6, 0.42, 0.14], "c": "#19f0d8",
         "mat": "neon"},
    ], "Cyberpunk on a budget.", "uncommon", 10),

    _hat("hat_bucket", "Bucket Hat", 200, [
        {"t": "cyl", "p": [0, 0.42, 0], "s": [1.5, 0.84, 1.5], "c": "#5e7c4a"},
        {"t": "cone", "p": [0, 0.1, 0], "s": [2.2, 0.36, 2.2], "c": "#6d8c55"},
    ], "Fisherman chic. Never goes out of style.", "common", 11),

    _hat("hat_headphones", "Retro Headphones", 500, [
        {"t": "cyl", "p": [0.85, -0.35, 0], "s": [0.72, 0.28, 0.72],
         "c": "#1b2a35", "r": [0, 0, 1.5708]},
        {"t": "cyl", "p": [-0.85, -0.35, 0], "s": [0.72, 0.28, 0.72],
         "c": "#1b2a35", "r": [0, 0, 1.5708]},
        {"t": "box", "p": [0, 0.28, 0], "s": [1.75, 0.2, 0.24], "c": "#2f3640"},
        {"t": "box", "p": [0.86, 0.05, 0], "s": [0.2, 0.5, 0.22], "c": "#2f3640"},
        {"t": "box", "p": [-0.86, 0.05, 0], "s": [0.2, 0.5, 0.22], "c": "#2f3640"},
    ], "Playing an eleven hour loop of the lobby theme.", "uncommon", 12),

    _hat("hat_antlers", "Forest Antlers", 700, [
        {"t": "cyl", "p": [0.42, 0.5, 0], "s": [0.14, 1.0, 0.14], "c": "#6b4a2a"},
        {"t": "cyl", "p": [-0.42, 0.5, 0], "s": [0.14, 1.0, 0.14], "c": "#6b4a2a"},
        {"t": "cyl", "p": [0.72, 0.86, 0.1], "s": [0.11, 0.6, 0.11], "c": "#6b4a2a",
         "r": [0, 0, -0.7]},
        {"t": "cyl", "p": [-0.72, 0.86, 0.1], "s": [0.11, 0.6, 0.11], "c": "#6b4a2a",
         "r": [0, 0, 0.7]},
        {"t": "cyl", "p": [0.32, 1.02, -0.2], "s": [0.1, 0.5, 0.1], "c": "#6b4a2a",
         "r": [0.6, 0, 0]},
        {"t": "cyl", "p": [-0.32, 1.02, -0.2], "s": [0.1, 0.5, 0.1], "c": "#6b4a2a",
         "r": [0.6, 0, 0]},
    ], "Shed by something enormous in the northern woods.", "rare", 13),

    _hat("hat_halo", "Ring of Light", 2000, [
        {"t": "torus", "p": [0, 0.95, 0], "s": [1.5, 0.16, 1.5], "c": "#fff2a8",
         "mat": "neon"},
    ], "Awarded to those who never once used the report button.", "legendary", 14),

    _hat("hat_bandana", "Faded Bandana", 150, [
        {"t": "box", "p": [0, -0.05, 0], "s": [1.56, 0.4, 1.56], "c": "#b83a3a"},
        {"t": "box", "p": [0, -0.1, -0.85], "s": [0.5, 0.3, 0.5], "c": "#a32f2f",
         "r": [0.5, 0, 0]},
    ], "Worn by the veterans of the old server.", "common", 15),

    _hat("hat_pirate", "Pirate Tricorn", 800, [
        {"t": "cyl", "p": [0, 0.16, 0], "s": [2.2, 0.2, 1.9], "c": "#2b2118"},
        {"t": "cyl", "p": [0, 0.52, 0], "s": [1.4, 0.7, 1.4], "c": "#3a2c20"},
        {"t": "box", "p": [0, 0.34, 0.85], "s": [1.1, 0.5, 0.12], "c": "#f2f3f3",
         "decal": "skull"},
        {"t": "box", "p": [0.6, 0.45, -0.5], "s": [0.12, 0.6, 0.5], "c": "#c94f4f",
         "r": [0.3, 0.4, 0]},
    ], "Captain of a ship that sank in 2007.", "rare", 16),

    _hat("hat_spikes", "Mohawk Spikes", 650, [
        {"t": "cone", "p": [0, 0.55, 0.55], "s": [0.3, 0.9, 0.3], "c": "#19c8d8"},
        {"t": "cone", "p": [0, 0.72, 0.2], "s": [0.32, 1.2, 0.32], "c": "#19c8d8"},
        {"t": "cone", "p": [0, 0.72, -0.2], "s": [0.32, 1.2, 0.32], "c": "#19c8d8"},
        {"t": "cone", "p": [0, 0.55, -0.55], "s": [0.3, 0.9, 0.3], "c": "#19c8d8"},
        {"t": "box", "p": [0, 0.05, 0], "s": [1.5, 0.2, 1.4], "c": "#1b2a35"},
    ], "Ninety percent hair gel by volume.", "uncommon", 17),

    _hat("hat_teacup", "Teacup", 400, [
        {"t": "cyl", "p": [0, 0.06, 0], "s": [1.4, 0.1, 1.4], "c": "#f2f3f3"},
        {"t": "cyl", "p": [0, 0.42, 0], "s": [1.0, 0.7, 1.0], "c": "#f2f3f3"},
        {"t": "cyl", "p": [0, 0.62, 0], "s": [0.86, 0.12, 0.86], "c": "#8a5a2b"},
        {"t": "torus", "p": [0.62, 0.4, 0], "s": [0.44, 0.1, 0.44], "c": "#f2f3f3",
         "r": [0, 1.5708, 0]},
    ], "Perfectly balanced. Do not run.", "uncommon", 18),

    _hat("hat_astro", "Astro Dome", 1300, [
        {"t": "sph", "p": [0, 0.15, 0], "s": [1.9, 1.9, 1.9], "c": "#bfe9ff",
         "alpha": 0.45},
        {"t": "cyl", "p": [0, -0.35, 0], "s": [1.85, 0.3, 1.85], "c": "#d8dde2"},
        {"t": "box", "p": [0.85, 0.2, 0.4], "s": [0.2, 0.2, 0.2], "c": "#f5c518",
         "mat": "neon"},
    ], "Certified for vacuum, lava and awkward silences.", "rare", 19),

    _hat("hat_traffic_cone", "Traffic Cone", 90, [
        {"t": "cone", "p": [0, 0.62, 0], "s": [1.35, 1.3, 1.35], "c": "#e2621b"},
        {"t": "box", "p": [0, 0.05, 0], "s": [1.7, 0.12, 1.7], "c": "#e2621b"},
        {"t": "cyl", "p": [0, 0.62, 0], "s": [1.02, 0.2, 1.02], "c": "#f2f3f3"},
    ], "Borrowed. Definitely borrowed.", "common", 20),
]

# -------------------------------------------------------------------- faces
# Faces are drawn procedurally onto the texture atlas by the client
# (static/js/engine/textures.js) using this compact shape list.
def _face(item_id, name, price, shapes, desc, order=0, rarity="common"):
    return {"id": item_id, "name": name, "slot": "face", "price": price,
            "rarity": rarity, "description": desc, "sort_order": order,
            "data": {"shapes": shapes}}


FACES: List[Dict[str, Any]] = [
    _face("face_smile", "Smile", 0, [
        {"k": "ellipse", "x": -0.22, "y": -0.16, "w": 0.11, "h": 0.16, "c": "#1a1a1a"},
        {"k": "ellipse", "x": 0.22, "y": -0.16, "w": 0.11, "h": 0.16, "c": "#1a1a1a"},
        {"k": "arc", "x": 0, "y": 0.06, "r": 0.30, "a0": 0.08, "a1": 0.42,
         "w": 0.055, "c": "#1a1a1a"},
    ], "The default. Timeless.", 1),

    _face("face_grin", "Cheeky Grin", 120, [
        {"k": "ellipse", "x": -0.22, "y": -0.16, "w": 0.11, "h": 0.16, "c": "#1a1a1a"},
        {"k": "ellipse", "x": 0.22, "y": -0.16, "w": 0.11, "h": 0.16, "c": "#1a1a1a"},
        {"k": "arc", "x": 0.02, "y": 0.02, "r": 0.34, "a0": 0.05, "a1": 0.45,
         "w": 0.06, "c": "#1a1a1a"},
        {"k": "rect", "x": 0.03, "y": 0.12, "w": 0.30, "h": 0.07, "c": "#ffffff"},
    ], "Up to something. Definitely up to something.", 2),

    _face("face_cool", "Shades", 380, [
        {"k": "rect", "x": 0, "y": -0.16, "w": 0.74, "h": 0.06, "c": "#1a1a1a"},
        {"k": "rect", "x": -0.24, "y": -0.14, "w": 0.28, "h": 0.20, "c": "#12161c"},
        {"k": "rect", "x": 0.24, "y": -0.14, "w": 0.28, "h": 0.20, "c": "#12161c"},
        {"k": "rect", "x": -0.30, "y": -0.19, "w": 0.10, "h": 0.04, "c": "#7fd8ff"},
        {"k": "arc", "x": 0, "y": 0.10, "r": 0.24, "a0": 0.10, "a1": 0.40,
         "w": 0.05, "c": "#1a1a1a"},
    ], "Instantly 40% more mysterious.", 3, "uncommon"),

    _face("face_stoic", "Stoic", 90, [
        {"k": "rect", "x": -0.22, "y": -0.16, "w": 0.13, "h": 0.15, "c": "#1a1a1a"},
        {"k": "rect", "x": 0.22, "y": -0.16, "w": 0.13, "h": 0.15, "c": "#1a1a1a"},
        {"k": "rect", "x": 0, "y": 0.16, "w": 0.34, "h": 0.05, "c": "#1a1a1a"},
    ], "Has seen things. Says nothing.", 4),

    _face("face_wink", "Wink", 160, [
        {"k": "ellipse", "x": -0.22, "y": -0.16, "w": 0.11, "h": 0.16, "c": "#1a1a1a"},
        {"k": "arc", "x": 0.22, "y": -0.10, "r": 0.13, "a0": 0.55, "a1": 0.95,
         "w": 0.05, "c": "#1a1a1a"},
        {"k": "arc", "x": 0, "y": 0.06, "r": 0.30, "a0": 0.08, "a1": 0.42,
         "w": 0.055, "c": "#1a1a1a"},
    ], ";)", 5),

    _face("face_shock", "Shock", 200, [
        {"k": "ellipse", "x": -0.23, "y": -0.18, "w": 0.15, "h": 0.20, "c": "#ffffff"},
        {"k": "ellipse", "x": -0.23, "y": -0.16, "w": 0.08, "h": 0.10, "c": "#1a1a1a"},
        {"k": "ellipse", "x": 0.23, "y": -0.18, "w": 0.15, "h": 0.20, "c": "#ffffff"},
        {"k": "ellipse", "x": 0.23, "y": -0.16, "w": 0.08, "h": 0.10, "c": "#1a1a1a"},
        {"k": "ellipse", "x": 0, "y": 0.16, "w": 0.20, "h": 0.24, "c": "#1a1a1a"},
    ], "Just watched the cart reach the final checkpoint.", 6),

    _face("face_angry", "Furious", 240, [
        {"k": "rect", "x": -0.22, "y": -0.22, "w": 0.24, "h": 0.06, "c": "#1a1a1a",
         "rot": 0.35},
        {"k": "rect", "x": 0.22, "y": -0.22, "w": 0.24, "h": 0.06, "c": "#1a1a1a",
         "rot": -0.35},
        {"k": "ellipse", "x": -0.22, "y": -0.08, "w": 0.11, "h": 0.13, "c": "#1a1a1a"},
        {"k": "ellipse", "x": 0.22, "y": -0.08, "w": 0.11, "h": 0.13, "c": "#1a1a1a"},
        {"k": "arc", "x": 0, "y": 0.32, "r": 0.26, "a0": 0.58, "a1": 0.92,
         "w": 0.06, "c": "#1a1a1a"},
    ], "Someone captured the flag again.", 7),

    _face("face_derp", "Derp", 140, [
        {"k": "ellipse", "x": -0.24, "y": -0.19, "w": 0.17, "h": 0.19, "c": "#ffffff"},
        {"k": "ellipse", "x": -0.20, "y": -0.15, "w": 0.07, "h": 0.09, "c": "#1a1a1a"},
        {"k": "ellipse", "x": 0.24, "y": -0.16, "w": 0.15, "h": 0.17, "c": "#ffffff"},
        {"k": "ellipse", "x": 0.28, "y": -0.20, "w": 0.06, "h": 0.08, "c": "#1a1a1a"},
        {"k": "arc", "x": 0.02, "y": 0.08, "r": 0.24, "a0": 0.06, "a1": 0.40,
         "w": 0.05, "c": "#1a1a1a"},
        {"k": "ellipse", "x": 0.16, "y": 0.24, "w": 0.12, "h": 0.10, "c": "#e26b6b"},
    ], "Nobody is home and that is fine.", 8),

    _face("face_robot", "Circuit Face", 520, [
        {"k": "rect", "x": -0.22, "y": -0.14, "w": 0.22, "h": 0.14, "c": "#19f0d8"},
        {"k": "rect", "x": 0.22, "y": -0.14, "w": 0.22, "h": 0.14, "c": "#19f0d8"},
        {"k": "rect", "x": 0, "y": 0.16, "w": 0.46, "h": 0.12, "c": "#12161c"},
        {"k": "rect", "x": -0.14, "y": 0.16, "w": 0.05, "h": 0.12, "c": "#19f0d8"},
        {"k": "rect", "x": 0, "y": 0.16, "w": 0.05, "h": 0.12, "c": "#19f0d8"},
        {"k": "rect", "x": 0.14, "y": 0.16, "w": 0.05, "h": 0.12, "c": "#19f0d8"},
    ], "BEEP. Acquiring targets.", 9, "uncommon"),

    _face("face_cat", "Cat Face", 300, [
        {"k": "ellipse", "x": -0.22, "y": -0.14, "w": 0.09, "h": 0.20, "c": "#1a1a1a"},
        {"k": "ellipse", "x": 0.22, "y": -0.14, "w": 0.09, "h": 0.20, "c": "#1a1a1a"},
        {"k": "rect", "x": 0, "y": 0.10, "w": 0.10, "h": 0.06, "c": "#e08aa8"},
        {"k": "arc", "x": -0.10, "y": 0.08, "r": 0.14, "a0": 0.0, "a1": 0.5,
         "w": 0.045, "c": "#1a1a1a"},
        {"k": "arc", "x": 0.10, "y": 0.08, "r": 0.14, "a0": 0.0, "a1": 0.5,
         "w": 0.045, "c": "#1a1a1a"},
        {"k": "rect", "x": -0.36, "y": 0.06, "w": 0.24, "h": 0.03, "c": "#1a1a1a"},
        {"k": "rect", "x": 0.36, "y": 0.06, "w": 0.24, "h": 0.03, "c": "#1a1a1a"},
    ], ":3", 10, "uncommon"),
]

# ------------------------------------------------------------------ clothing
def _shirt(item_id, name, price, data, desc, order=0, rarity="common"):
    return {"id": item_id, "name": name, "slot": "shirt", "price": price,
            "rarity": rarity, "description": desc, "sort_order": order,
            "data": data}


SHIRTS: List[Dict[str, Any]] = [
    _shirt("shirt_none", "No Shirt", 0, {"torso": None, "arms": None},
           "Just you and your natural block finish.", 0),
    _shirt("shirt_tee_red", "Red Tee", 120,
           {"torso": "#c4281c", "arms": "#c4281c", "sleeves": 0.45,
            "decal": "logo_block"},
           "Standard issue starter shirt.", 1),
    _shirt("shirt_hoodie_blue", "Blue Hoodie", 260,
           {"torso": "#2f5fa8", "arms": "#2f5fa8", "hood": True,
            "stripe": "#e8e8e8"},
           "Comfortable. Slightly too warm for the desert map.", 2),
    _shirt("shirt_tux", "Tuxedo Jacket", 640,
           {"torso": "#1b2a35", "arms": "#1b2a35", "decal": "tux"},
           "Black tie only.", 3, "uncommon"),
    _shirt("shirt_hivis", "Hi-Vis Vest", 220,
           {"torso": "#e9f21a", "arms": "#d7c59a", "sleeves": 0.0,
            "stripe": "#c8cbcd"},
           "Cannot be missed, even at render distance.", 4),
    _shirt("shirt_stripes", "Referee Stripes", 300,
           {"torso": "#f2f3f3", "arms": "#f2f3f3", "stripes": 6,
            "stripe": "#1b2a35"},
           "You are the law now.", 5),
    _shirt("shirt_burger", "Burger Crew Uniform", 350,
           {"torso": "#e2621b", "arms": "#f2f3f3", "sleeves": 0.4,
            "decal": "burger"},
           "Employee of the month, seven months running.", 6, "uncommon"),
    _shirt("shirt_soldier", "Field Jacket", 480,
           {"torso": "#4a5a34", "arms": "#4a5a34", "decal": "chevron",
            "stripe": "#2f3a20"},
           "Standard issue for the Fortress campaigns.", 7, "uncommon"),
    _shirt("shirt_hawaiian", "Hawaiian Shirt", 400,
           {"torso": "#19a7c8", "arms": "#19a7c8", "decal": "flowers"},
           "Permanently on holiday.", 8),
    _shirt("shirt_void", "Void Robes", 1100,
           {"torso": "#2a0a4a", "arms": "#3d1266", "decal": "sigil",
            "stripe": "#8b3fd6"},
           "Woven from something that should not be woven.", 9, "rare"),
]


def _pants(item_id, name, price, data, desc, order=0, rarity="common"):
    return {"id": item_id, "name": name, "slot": "pants", "price": price,
            "rarity": rarity, "description": desc, "sort_order": order,
            "data": data}


PANTS: List[Dict[str, Any]] = [
    _pants("pants_none", "No Pants", 0, {"legs": None},
           "Bold. Legally questionable.", 0),
    _pants("pants_jeans", "Blue Jeans", 140, {"legs": "#3d5a80", "cuff": "#2c4160"},
           "They go with everything.", 1),
    _pants("pants_cargo", "Cargo Trousers", 220, {"legs": "#6b6a4a", "pocket": True},
           "Fourteen pockets. All empty.", 2),
    _pants("pants_shorts", "Summer Shorts", 160,
           {"legs": "#d3592b", "length": 0.55, "skin": "#d7c59a"},
           "Built for the beach map.", 3),
    _pants("pants_tux", "Tuxedo Trousers", 560, {"legs": "#1b2a35", "stripe": "#f2f3f3"},
           "Matches the jacket, obviously.", 4, "uncommon"),
    _pants("pants_camo", "Camo Trousers", 380, {"legs": "#4a5a34", "camo": True},
           "You literally cannot see these.", 5, "uncommon"),
    _pants("pants_neon", "Neon Runners", 700, {"legs": "#12161c", "stripe": "#19f0d8",
                                               "glow": True},
           "Leaves a faint trail in dark rooms.", 6, "rare"),
]

# ---------------------------------------------------------------------- back
BACK_ITEMS: List[Dict[str, Any]] = [
    {"id": "back_backpack", "name": "Explorer Backpack", "slot": "back",
     "price": 300, "rarity": "common", "sort_order": 1,
     "description": "Holds exactly one sandwich and a map.",
     "data": {"parts": [
         {"t": "box", "p": [0, 0.1, -0.55], "s": [1.3, 1.5, 0.7], "c": "#6b4a2a"},
         {"t": "box", "p": [0, -0.4, -0.95], "s": [1.0, 0.5, 0.2], "c": "#4a3320"},
         {"t": "box", "p": [0, 0.55, -0.6], "s": [0.4, 0.2, 0.5], "c": "#4a3320"},
     ]}},
    {"id": "back_wings", "name": "Feather Wings", "slot": "back",
     "price": 1400, "rarity": "rare", "sort_order": 2,
     "description": "Purely decorative. Gravity is undefeated.",
     "data": {"parts": [
         {"t": "box", "p": [0.95, 0.5, -0.5], "s": [1.6, 0.9, 0.16], "c": "#f2f3f3",
          "r": [0, -0.5, 0.35]},
         {"t": "box", "p": [-0.95, 0.5, -0.5], "s": [1.6, 0.9, 0.16], "c": "#f2f3f3",
          "r": [0, 0.5, -0.35]},
         {"t": "box", "p": [1.5, 0.0, -0.75], "s": [1.2, 0.7, 0.14], "c": "#e2e6ea",
          "r": [0, -0.6, 0.5]},
         {"t": "box", "p": [-1.5, 0.0, -0.75], "s": [1.2, 0.7, 0.14], "c": "#e2e6ea",
          "r": [0, 0.6, -0.5]},
     ]}},
    {"id": "back_jetpack", "name": "Rusted Jetpack", "slot": "back",
     "price": 1600, "rarity": "rare", "sort_order": 3,
     "description": "Ignition sold separately.",
     "data": {"parts": [
         {"t": "cyl", "p": [0.42, 0.05, -0.55], "s": [0.55, 1.5, 0.55], "c": "#a3392b"},
         {"t": "cyl", "p": [-0.42, 0.05, -0.55], "s": [0.55, 1.5, 0.55], "c": "#a3392b"},
         {"t": "cyl", "p": [0.42, -0.85, -0.55], "s": [0.35, 0.35, 0.35], "c": "#4a4a4a"},
         {"t": "cyl", "p": [-0.42, -0.85, -0.55], "s": [0.35, 0.35, 0.35], "c": "#4a4a4a"},
         {"t": "box", "p": [0, 0.3, -0.5], "s": [0.5, 0.4, 0.3], "c": "#6d6e6c"},
     ]}},
    {"id": "back_cape", "name": "Hero Cape", "slot": "back",
     "price": 900, "rarity": "uncommon", "sort_order": 4,
     "description": "Billows even indoors.",
     "data": {"parts": [
         {"t": "box", "p": [0, -0.2, -0.62], "s": [1.9, 2.6, 0.12], "c": "#8b1a1a",
          "r": [0.12, 0, 0]},
         {"t": "box", "p": [0, 1.0, -0.58], "s": [2.0, 0.3, 0.14], "c": "#f5c518"},
     ]}},
]

# ------------------------------------------------------------------- usables
def _usable(item_id, name, price, stats, parts, desc, order=0,
            rarity="common", default=False):
    return {"id": item_id, "name": name, "slot": "usable", "price": price,
            "rarity": rarity, "description": desc, "sort_order": order,
            "is_default": default,
            "data": {"stats": stats, "parts": parts}}


USABLES: List[Dict[str, Any]] = [
    _usable("use_pistol", "Basic Pistol", 0, {
        "kind": "hitscan", "damage": 24, "headshot": 2.0, "rpm": 320,
        "mag": 12, "reload": 1.4, "spread": 0.9, "pellets": 1, "range": 260,
        "auto": False, "sound": "pistol", "recoil": 1.1, "reserve": 96,
    }, [
        {"t": "box", "p": [0, 0, 0.35], "s": [0.22, 0.28, 1.0], "c": "#31363c"},
        {"t": "box", "p": [0, -0.32, -0.05], "s": [0.2, 0.55, 0.34], "c": "#22262b"},
        {"t": "box", "p": [0, 0.14, 0.62], "s": [0.1, 0.1, 0.4], "c": "#6d6e6c"},
    ], "Reliable, unglamorous, always in your bag.", 1, "common", True),

    _usable("use_shotgun", "Basic Shotgun", 0, {
        "kind": "hitscan", "damage": 9, "headshot": 1.5, "rpm": 72,
        "mag": 6, "reload": 2.4, "spread": 5.4, "pellets": 8, "range": 70,
        "auto": False, "sound": "shotgun", "recoil": 3.4, "reserve": 42,
        "falloff": 0.55,
    }, [
        {"t": "box", "p": [0, 0, 0.55], "s": [0.26, 0.3, 1.7], "c": "#5a3a22"},
        {"t": "cyl", "p": [0.07, 0.06, 0.95], "s": [0.14, 1.6, 0.14],
         "c": "#31363c", "r": [1.5708, 0, 0]},
        {"t": "cyl", "p": [-0.07, 0.06, 0.95], "s": [0.14, 1.6, 0.14],
         "c": "#31363c", "r": [1.5708, 0, 0]},
        {"t": "box", "p": [0, -0.3, -0.25], "s": [0.24, 0.5, 0.5], "c": "#4a2f18"},
    ], "Two barrels of extremely direct conversation.", 2, "common", True),

    _usable("use_stick", "Basic Stick", 0, {
        "kind": "melee", "damage": 30, "headshot": 1.4, "rpm": 96,
        "range": 9.5, "arc": 0.55, "sound": "swing", "knockback": 12,
    }, [
        {"t": "cyl", "p": [0, 0, 0.7], "s": [0.16, 1.9, 0.16], "c": "#7c503a",
         "r": [1.5708, 0, 0]},
        {"t": "box", "p": [0.05, 0.06, 1.35], "s": [0.14, 0.14, 0.4], "c": "#6b4229",
         "r": [0, 0.3, 0]},
    ], "A stick. It is a good stick.", 3, "common", True),

    _usable("use_smg", "Rapid SMG", 900, {
        "kind": "hitscan", "damage": 13, "headshot": 1.8, "rpm": 780,
        "mag": 30, "reload": 1.9, "spread": 2.6, "pellets": 1, "range": 180,
        "auto": True, "sound": "smg", "recoil": 0.7, "reserve": 180,
    }, [
        {"t": "box", "p": [0, 0, 0.5], "s": [0.24, 0.3, 1.3], "c": "#22262b"},
        {"t": "box", "p": [0, -0.34, 0.1], "s": [0.2, 0.7, 0.3], "c": "#31363c"},
        {"t": "box", "p": [0, -0.28, -0.15], "s": [0.18, 0.5, 0.3], "c": "#1b2a35"},
        {"t": "cyl", "p": [0, 0.05, 1.15], "s": [0.11, 0.5, 0.11], "c": "#6d6e6c",
         "r": [1.5708, 0, 0]},
    ], "Empties a magazine faster than you can regret it.", 4, "uncommon"),

    _usable("use_rifle", "Ranger Rifle", 1200, {
        "kind": "hitscan", "damage": 42, "headshot": 2.2, "rpm": 150,
        "mag": 10, "reload": 2.2, "spread": 0.35, "pellets": 1, "range": 400,
        "auto": False, "sound": "rifle", "recoil": 2.0, "reserve": 80,
    }, [
        {"t": "box", "p": [0, 0, 0.7], "s": [0.22, 0.28, 2.1], "c": "#3a2c20"},
        {"t": "cyl", "p": [0, 0.06, 1.6], "s": [0.1, 1.0, 0.1], "c": "#31363c",
         "r": [1.5708, 0, 0]},
        {"t": "box", "p": [0, 0.26, 0.55], "s": [0.14, 0.16, 0.6], "c": "#22262b"},
        {"t": "box", "p": [0, -0.3, -0.1], "s": [0.2, 0.5, 0.4], "c": "#4a3320"},
    ], "Accurate to a fault. Yours especially.", 5, "uncommon"),

    _usable("use_sniper", "Longshot", 1800, {
        "kind": "hitscan", "damage": 92, "headshot": 2.5, "rpm": 46,
        "mag": 5, "reload": 3.0, "spread": 0.05, "pellets": 1, "range": 900,
        "auto": False, "sound": "sniper", "recoil": 4.5, "reserve": 40,
        "scope": 4.0, "charge": 0.0,
    }, [
        {"t": "box", "p": [0, 0, 0.9], "s": [0.22, 0.3, 2.6], "c": "#1f2a20"},
        {"t": "cyl", "p": [0, 0.06, 2.2], "s": [0.1, 1.4, 0.1], "c": "#22262b",
         "r": [1.5708, 0, 0]},
        {"t": "cyl", "p": [0, 0.32, 0.8], "s": [0.16, 0.9, 0.16], "c": "#12161c",
         "r": [1.5708, 0, 0]},
        {"t": "box", "p": [0, -0.32, -0.15], "s": [0.2, 0.55, 0.5], "c": "#2a3524"},
    ], "One shot. Then a long, thoughtful pause.", 6, "rare"),

    _usable("use_rocket", "Blast Launcher", 2500, {
        "kind": "projectile", "damage": 88, "splash": 9.0, "splash_damage": 62,
        "rpm": 55, "mag": 4, "reload": 3.2, "speed": 78, "range": 500,
        "auto": False, "sound": "rocket", "recoil": 5.0, "reserve": 24,
        "self_damage": 0.45, "knockback": 34,
    }, [
        {"t": "cyl", "p": [0, 0.05, 0.75], "s": [0.42, 2.6, 0.42], "c": "#2f6b3a",
         "r": [1.5708, 0, 0]},
        {"t": "box", "p": [0, -0.3, 0.05], "s": [0.2, 0.5, 0.4], "c": "#22262b"},
        {"t": "box", "p": [0, 0.34, 0.5], "s": [0.14, 0.2, 0.7], "c": "#1b2a35"},
        {"t": "cyl", "p": [0, 0.05, 2.0], "s": [0.5, 0.3, 0.5], "c": "#22262b",
         "r": [1.5708, 0, 0]},
    ], "Rocket jumping is a feature, not a bug.", 7, "rare"),

    _usable("use_sword", "Blockblade", 1000, {
        "kind": "melee", "damage": 55, "headshot": 1.3, "rpm": 78,
        "range": 11.0, "arc": 0.7, "sound": "sword", "knockback": 16,
    }, [
        {"t": "box", "p": [0, 0, 1.3], "s": [0.16, 0.4, 2.4], "c": "#d8dde2",
         "mat": "metal"},
        {"t": "box", "p": [0, 0, 0.1], "s": [0.7, 0.18, 0.2], "c": "#f5c518",
         "mat": "metal"},
        {"t": "cyl", "p": [0, 0, -0.25], "s": [0.18, 0.6, 0.18], "c": "#4a2f18",
         "r": [1.5708, 0, 0]},
    ], "Sharpened on the edge of a baseplate.", 8, "uncommon"),

    _usable("use_medkit", "Field Medkit", 700, {
        "kind": "support", "heal": 34, "rpm": 40, "range": 14.0,
        "sound": "heal", "self_heal": 24, "mag": 4, "reload": 4.0, "reserve": 8,
    }, [
        {"t": "box", "p": [0, 0, 0.3], "s": [0.7, 0.5, 0.9], "c": "#f2f3f3"},
        {"t": "box", "p": [0, 0.26, 0.3], "s": [0.24, 0.06, 0.6], "c": "#c4281c"},
        {"t": "box", "p": [0, 0.26, 0.3], "s": [0.6, 0.06, 0.24], "c": "#c4281c"},
        {"t": "box", "p": [0, 0.3, 0.0], "s": [0.3, 0.14, 0.1], "c": "#a3a2a5"},
    ], "Aim at a friend. Press fire. Be thanked.", 9, "uncommon"),

    _usable("use_buildhammer", "Tycoon Hammer", 450, {
        "kind": "melee", "damage": 22, "headshot": 1.2, "rpm": 110,
        "range": 8.5, "arc": 0.5, "sound": "swing", "knockback": 8,
        "build_bonus": 0.05,
    }, [
        {"t": "cyl", "p": [0, 0, 0.55], "s": [0.14, 1.5, 0.14], "c": "#6b4a2a",
         "r": [1.5708, 0, 0]},
        {"t": "box", "p": [0, 0.05, 1.25], "s": [0.7, 0.34, 0.34], "c": "#8f9296",
         "mat": "metal"},
    ], "Grants a small bonus to Burger Tycoon income while held.", 10, "uncommon"),
]

ALL_ITEMS: List[Dict[str, Any]] = HATS + FACES + SHIRTS + PANTS + BACK_ITEMS + USABLES

DEFAULT_EQUIPPED = {
    "face": "face_smile",
    "hat": "",
    "shirt": "shirt_none",
    "pants": "pants_none",
    "back": "",
}

# Items every new account is granted for free.
STARTER_ITEMS = ["use_pistol", "use_shotgun", "use_stick", "face_smile",
                 "shirt_none", "pants_none"]

DEFAULT_HOTBAR = ["use_pistol", "use_shotgun", "use_stick", "", ""]

ITEMS_BY_ID: Dict[str, Dict[str, Any]] = {it["id"]: it for it in ALL_ITEMS}


def get(item_id: str):
    return ITEMS_BY_ID.get(item_id)


def by_slot(slot: str) -> List[Dict[str, Any]]:
    return [it for it in ALL_ITEMS if it["slot"] == slot]
