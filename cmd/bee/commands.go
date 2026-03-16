package main

import (
	"encoding/json"
	"fmt"
	"os"
)

type CustomCommand struct {
	Name    string `json:"name"`
	Action  string `json:"action"`
	To      string `json:"to,omitempty"`
	Payload string `json:"payload,omitempty"`
}

func loadCustomCommands(path string) ([]CustomCommand, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cmds []CustomCommand
	if err := json.Unmarshal(b, &cmds); err != nil {
		return nil, fmt.Errorf("parse commands: %w", err)
	}
	return cmds, nil
}

func indexCommands(cmds []CustomCommand) map[string]CustomCommand {
	m := make(map[string]CustomCommand, len(cmds))
	for _, c := range cmds {
		if c.Name == "" {
			continue
		}
		m[c.Name] = c
	}
	return m
}
