package main

import (
	"bufio"
	"errors"
	"fmt"
	"net"
	"os"
	"strings"
	"sync"
	"time"

	"bee-swarm/src/swarm"
)

type Bee struct {
	id        string
	codename  string
	queenAddr string
	started   bool

	conn  net.Conn
	r     *bufio.Reader
	w     *bufio.Writer
	mu    sync.Mutex
	stdin *os.File

	commandsPath string
	commands     map[string]CustomCommand
}

func NewBee(id, codename, queen, commandsPath string) *Bee {
	return &Bee{
		id:           id,
		codename:     codename,
		queenAddr:    queen,
		stdin:        os.Stdin,
		commandsPath: commandsPath,
		commands:     map[string]CustomCommand{},
	}
}

func (b *Bee) Start() error {
	b.mu.Lock()
	defer b.mu.Unlock()

	if b.started {
		return nil
	}

	conn, err := net.Dial("tcp", b.queenAddr)
	if err != nil {
		return fmt.Errorf("dial: %w", err)
	}
	b.conn = conn
	b.r = bufio.NewReader(conn)
	b.w = bufio.NewWriter(conn)

	if err := swarm.Send(b.w, swarm.Message{Type: "register", From: b.id, Payload: b.codename}); err != nil {
		_ = conn.Close()
		return fmt.Errorf("register: %w", err)
	}
	b.started = true

	go b.readLoop()
	_ = swarm.Send(b.w, swarm.Message{Type: "list"})
	return nil
}

func (b *Bee) Send(msg swarm.Message) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if !b.started || b.w == nil {
		return errors.New("not started: run 'start' first")
	}
	if msg.From == "" {
		msg.From = b.id
	}
	return swarm.Send(b.w, msg)
}

func (b *Bee) readLoop() {
	for {
		msg, err := swarm.Recv(b.r)
		if err != nil {
			fmt.Printf("recv: %v\n", err)
			return
		}
		switch msg.Type {
		case "message":
			fmt.Printf("[%s] %s\n", msg.From, msg.Payload)
		case "peers":
			fmt.Printf("peers: %s\n", strings.Join(msg.Peers, ", "))
		case "registered":
			fmt.Printf("%s\n", msg.Payload)
		case "error":
			fmt.Printf("error: %s\n", msg.Payload)
		default:
			fmt.Printf("%s: %s\n", msg.Type, msg.Payload)
		}
	}
}

func (b *Bee) ReloadCommands() error {
	cmds, err := loadCustomCommands(b.commandsPath)
	if err != nil {
		return err
	}
	b.commands = indexCommands(cmds)
	return nil
}

func (b *Bee) PrintCommands() {
	if len(b.commands) == 0 {
		fmt.Println("no custom commands loaded")
		return
	}
	for name, c := range b.commands {
		fmt.Printf("%s -> %s %s %s\n", name, c.Action, c.To, c.Payload)
	}
}

func (b *Bee) TryCustom(line string) bool {
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return false
	}
	c, ok := b.commands[fields[0]]
	if !ok {
		return false
	}

	args := strings.TrimSpace(strings.TrimPrefix(line, fields[0]))
	payload := strings.ReplaceAll(c.Payload, "{args}", strings.TrimSpace(args))
	payload = strings.ReplaceAll(payload, "{id}", b.id)
	payload = strings.ReplaceAll(payload, "{codename}", b.codename)

	switch c.Action {
	case "list":
		_ = b.Send(swarm.Message{Type: "list"})
	case "broadcast":
		_ = b.Send(swarm.Message{Type: "broadcast", Payload: payload})
	case "send":
		to := c.To
		rest := strings.TrimSpace(args)
		if to == "" {
			parts := strings.Fields(rest)
			if len(parts) == 0 {
				fmt.Println("custom send requires target id")
				return true
			}
			to = parts[0]
			rest = strings.TrimSpace(strings.TrimPrefix(rest, to))
			payload = strings.ReplaceAll(c.Payload, "{args}", strings.TrimSpace(rest))
			payload = strings.ReplaceAll(payload, "{id}", b.id)
			payload = strings.ReplaceAll(payload, "{codename}", b.codename)
		}
		_ = b.Send(swarm.Message{Type: "send", To: to, Payload: payload})
	default:
		fmt.Printf("custom command has unknown action: %s\n", c.Action)
	}
	return true
}

func defaultCommandsPath() string {
	return "configs/bee_commands.json"
}

func nowID() string {
	return fmt.Sprintf("%s-%d", newID(), time.Now().UTC().Unix())
}
