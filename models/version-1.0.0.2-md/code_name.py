import random
import time

_ADJECTIVES = [
    "amber",
    "brisk",
    "calm",
    "copper",
    "dawn",
    "ember",
    "fleet",
    "golden",
    "hollow",
    "ivory",
    "lively",
    "merry",
    "nova",
    "quiet",
    "rapid",
    "silent",
    "swift",
    "vivid",
    "warm",
    "zephyr",
]

_NOUNS = [
    "arch",
    "brook",
    "cairn",
    "delta",
    "ember",
    "forge",
    "glade",
    "harbor",
    "isle",
    "javelin",
    "keel",
    "lantern",
    "mesa",
    "nexus",
    "orb",
    "prairie",
    "quartz",
    "ridge",
    "summit",
    "thicket",
]


def now_id():
    """Short ID based on current UTC time."""
    return str(int(time.time() * 1000))


def new_codename(rng=None):
    """Return a readable codename like 'amber-harbor'."""
    if rng is None:
        rng = random
    return f"{rng.choice(_ADJECTIVES)}-{rng.choice(_NOUNS)}"
