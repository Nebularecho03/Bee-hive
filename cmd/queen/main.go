package main

import (
	"bufio"
	"flag"
	"fmt"
	"log"
	"net"
	"sync"

	"bee-swarm/src/swarm"
)

type client struct {
	id   string
	conn net.Conn
	w    *bufio.Writer
	mu   sync.Mutex
}

func (c *client) send(msg swarm.Message) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	return swarm.Send(c.w, msg)
}

var (
	clientsMu sync.RWMutex
	clients   = map[string]*client{}
)

func main() {
	addr := flag.String("addr", ":9000", "listen address")
	flag.Parse()

	ln, err := net.Listen("tcp", *addr)
	if err != nil {
		log.Fatalf("listen: %v", err)
	}
	log.Printf("queen listening on %s", *addr)

	for {
		conn, err := ln.Accept()
		if err != nil {
			log.Printf("accept: %v", err)
			continue
		}
		go handleConn(conn)
	}
}

func handleConn(conn net.Conn) {
	defer conn.Close()

	r := bufio.NewReader(conn)
	w := bufio.NewWriter(conn)

	msg, err := swarm.Recv(r)
	if err != nil {
		log.Printf("register recv: %v", err)
		return
	}
	if msg.Type != "register" || msg.From == "" {
		_ = swarm.Send(w, swarm.Message{Type: "error", Payload: "first message must be register with from"})
		return
	}

	c := &client{id: msg.From, conn: conn, w: w}

	if err := addClient(c); err != nil {
		_ = c.send(swarm.Message{Type: "error", Payload: err.Error()})
		return
	}
	defer removeClient(c.id)

	_ = c.send(swarm.Message{Type: "registered", Payload: fmt.Sprintf("welcome %s", c.id)})
	log.Printf("registered %s", c.id)

	for {
		msg, err := swarm.Recv(r)
		if err != nil {
			log.Printf("recv %s: %v", c.id, err)
			return
		}
		switch msg.Type {
		case "send":
			handleSend(c, msg)
		case "broadcast":
			handleBroadcast(c, msg)
		case "list":
			handleList(c)
		case "heartbeat":
			// no-op
		default:
			_ = c.send(swarm.Message{Type: "error", Payload: "unknown message type"})
		}
	}
}

func addClient(c *client) error {
	clientsMu.Lock()
	defer clientsMu.Unlock()
	if _, exists := clients[c.id]; exists {
		return fmt.Errorf("id already connected")
	}
	clients[c.id] = c
	return nil
}

func removeClient(id string) {
	clientsMu.Lock()
	defer clientsMu.Unlock()
	delete(clients, id)
}

func handleSend(sender *client, msg swarm.Message) {
	if msg.To == "" {
		_ = sender.send(swarm.Message{Type: "error", Payload: "send requires to"})
		return
	}
	clientsMu.RLock()
	target := clients[msg.To]
	clientsMu.RUnlock()
	if target == nil {
		_ = sender.send(swarm.Message{Type: "error", Payload: "target not connected"})
		return
	}
	_ = target.send(swarm.Message{Type: "message", From: sender.id, Payload: msg.Payload})
}

func handleBroadcast(sender *client, msg swarm.Message) {
	clientsMu.RLock()
	defer clientsMu.RUnlock()
	for id, c := range clients {
		if id == sender.id {
			continue
		}
		_ = c.send(swarm.Message{Type: "message", From: sender.id, Payload: msg.Payload})
	}
}

func handleList(sender *client) {
	clientsMu.RLock()
	defer clientsMu.RUnlock()
	peers := make([]string, 0, len(clients))
	for id := range clients {
		peers = append(peers, id)
	}
	_ = sender.send(swarm.Message{Type: "peers", Peers: peers})
}
