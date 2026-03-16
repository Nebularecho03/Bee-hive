package main

import (
	"bufio"
	"fmt"
	"strings"

	"bee-swarm/src/swarm"
)

// repl provides a small shell-like interface for interacting with the swarm.
func repl(b *Bee) {
	scanner := bufio.NewScanner(b.stdin)
	fmt.Println("bee-shell: type 'help' for commands")
	for {
		fmt.Print("bee> ")
		if !scanner.Scan() {
			return
		}
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		switch fields[0] {
		case "help":
			printHelp()
		case "quit", "exit":
			return
		case "start":
			if err := b.Start(); err != nil {
				fmt.Printf("start error: %v\n", err)
			}
		case "identity":
			fmt.Printf("id=%s codename=%s started=%t\n", b.id, b.codename, b.started)
		case "list":
			if err := b.Send(swarm.Message{Type: "list"}); err != nil {
				fmt.Println(err)
			}
		case "broadcast":
			msg := strings.TrimSpace(strings.TrimPrefix(line, "broadcast"))
			msg = strings.TrimSpace(msg)
			if msg == "" {
				fmt.Println("usage: broadcast <message>")
				continue
			}
			if err := b.Send(swarm.Message{Type: "broadcast", Payload: msg}); err != nil {
				fmt.Println(err)
			}
		case "send":
			if len(fields) < 3 {
				fmt.Println("usage: send <id> <message>")
				continue
			}
			to := fields[1]
			msg := strings.TrimSpace(strings.TrimPrefix(line, "send"))
			msg = strings.TrimSpace(strings.TrimPrefix(msg, to))
			msg = strings.TrimSpace(msg)
			if err := b.Send(swarm.Message{Type: "send", To: to, Payload: msg}); err != nil {
				fmt.Println(err)
			}
		case "ping":
			if len(fields) != 2 {
				fmt.Println("usage: ping <id>")
				continue
			}
			to := fields[1]
			if err := b.Send(swarm.Message{Type: "send", To: to, Payload: "ping"}); err != nil {
				fmt.Println(err)
			}
		case "whoami":
			fmt.Printf("bee-shell connected=%t\n", b.started)
		case "commands":
			b.PrintCommands()
		case "reload":
			if err := b.ReloadCommands(); err != nil {
				fmt.Printf("reload error: %v\n", err)
			}
		default:
			if b.TryCustom(line) {
				continue
			}
			fmt.Println("unknown command; type 'help'")
		}
	}
}

func printHelp() {
	fmt.Println("commands:")
	fmt.Println("  help                show this help")
	fmt.Println("  start               connect to queen and register")
	fmt.Println("  identity            show id/codename")
	fmt.Println("  list                list connected bees")
	fmt.Println("  send <id> <msg>      send message to a bee")
	fmt.Println("  broadcast <msg>      send message to all bees")
	fmt.Println("  ping <id>            send a ping message")
	fmt.Println("  commands            list custom commands")
	fmt.Println("  reload              reload custom commands")
	fmt.Println("  whoami              shell status")
	fmt.Println("  quit/exit           close the shell")
}
