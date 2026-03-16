package main

import (
	"flag"
	"log"
)

func main() {
	id := flag.String("id", "", "bee id (optional, auto if empty)")
	codename := flag.String("codename", "", "bee codename (optional, auto if empty)")
	queen := flag.String("queen", "127.0.0.1:9000", "queen address")
	commandsPath := flag.String("commands", defaultCommandsPath(), "custom commands JSON path")
	flag.Parse()

	finalID := *id
	if finalID == "" {
		finalID = nowID()
	}
	finalCodename := *codename
	if finalCodename == "" {
		finalCodename = newCodename()
	}

	bee := NewBee(finalID, finalCodename, *queen, *commandsPath)
	if err := bee.ReloadCommands(); err != nil {
		log.Printf("load commands: %v", err)
	}

	repl(bee)
}
