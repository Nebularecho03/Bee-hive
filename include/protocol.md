# Bee Swarm Protocol (TCP, JSON lines)

Each TCP message is one JSON object per line.

Fields:
- type: message type
- from: sender id
- to: target id
- payload: string message
- peers: list of peer ids
- ts: RFC3339Nano timestamp (added by sender if missing)

Types:
- register: first message from a bee, requires from
- registered: queen response to successful register
- send: bee to queen, requires to and payload
- broadcast: bee to queen, payload sent to all other bees
- list: bee to queen, request peers list
- peers: queen to bee, list of connected ids
- message: queen to bee, forwarded message
- error: queen to bee, error message
