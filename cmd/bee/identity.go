package main

import (
	"crypto/rand"
	"encoding/hex"
	"math/big"
	"time"
)

var adjectives = []string{
	"amber", "brisk", "calm", "dawn", "ember", "frost", "glade", "honey",
	"ivory", "jolly", "keen", "lunar", "moss", "nova", "opal", "quill",
	"rust", "sage", "tide", "ultra", "vivid", "wisp", "young", "zeal",
}

var nouns = []string{
	"bee", "ant", "wasp", "moth", "owl", "fox", "lynx", "deer",
	"hawk", "crab", "wolf", "hare", "seal", "crow", "bear", "swan",
	"pike", "ibis", "orca", "yak", "koala", "otter", "eagle", "viper",
}

func newID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func newCodename() string {
	adj := pick(adjectives)
	noun := pick(nouns)
	return adj + "-" + noun
}

func pick(list []string) string {
	if len(list) == 0 {
		return "unknown"
	}
	n, err := rand.Int(rand.Reader, big.NewInt(int64(len(list))))
	if err != nil {
		// Fallback: time-based index.
		idx := time.Now().UnixNano() % int64(len(list))
		return list[idx]
	}
	return list[n.Int64()]
}
