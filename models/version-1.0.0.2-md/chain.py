import hashlib
import json


def compute_hash(entry):
    payload = {
        "prev_hash": entry.get("prev_hash", ""),
        "author": entry.get("author", ""),
        "ts": entry.get("ts", ""),
        "data": entry.get("data", {}),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_entry(author, ts, data, prev_hash):
    entry = {
        "author": author,
        "ts": ts,
        "data": data,
        "prev_hash": prev_hash or "",
    }
    entry["hash"] = compute_hash(entry)
    return entry


def validate_entry(entry):
    expected = compute_hash(entry)
    return entry.get("hash") == expected
