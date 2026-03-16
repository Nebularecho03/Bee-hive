package swarm

// Message is a line-delimited JSON message used across TCP connections.
type Message struct {
	Type      string   `json:"type"`
	From      string   `json:"from,omitempty"`
	To        string   `json:"to,omitempty"`
	Payload   string   `json:"payload,omitempty"`
	Peers     []string `json:"peers,omitempty"`
	Timestamp string   `json:"ts,omitempty"`
}
