package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"sync"
)

type user struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Name     string `json:"name"`
	Email    string `json:"email"`
}

type asset struct {
	uid         string
	dir         string
	detail      map[string]any
	submissions []map[string]any // sorted by _id
	byID        map[string]map[string]any
}

// store holds everything served. Writes mutate the submission maps in
// place, so mu guards every read and write after load.
type store struct {
	mu     sync.Mutex
	users  map[string]user
	assets map[string]*asset
}

func readJSON(path string, v any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	dec := json.NewDecoder(bytes.NewReader(b))
	// Numbers stay json.Number so ids and coordinates round-trip
	// byte for byte.
	dec.UseNumber()
	if err := dec.Decode(v); err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	return nil
}

// idKey lets "100001" and 100001 address the same submission: the
// app sends kobo_id strings, Kobo stores numbers.
func idKey(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case json.Number:
		return t.String()
	}
	return fmt.Sprint(v)
}

func lessID(a, b string) bool {
	fa, errA := strconv.ParseFloat(a, 64)
	fb, errB := strconv.ParseFloat(b, 64)
	if errA == nil && errB == nil {
		return fa < fb
	}
	return a < b
}

func load(dir string) (*store, error) {
	s := &store{users: map[string]user{}, assets: map[string]*asset{}}
	var users []user
	if err := readJSON(filepath.Join(dir, "users.json"), &users); err != nil {
		return nil, err
	}
	for _, u := range users {
		if u.Username == "" || u.Password == "" {
			return nil, fmt.Errorf("users.json: every user needs username and password")
		}
		s.users[u.Username] = u
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		a, err := loadAsset(filepath.Join(dir, e.Name()), e.Name())
		if err != nil {
			return nil, err
		}
		s.assets[a.uid] = a
	}
	return s, nil
}

func loadAsset(dir, uid string) (*asset, error) {
	a := &asset{uid: uid, dir: dir, byID: map[string]map[string]any{}}
	assetPath := filepath.Join(dir, "asset.json")
	if err := readJSON(assetPath, &a.detail); err != nil {
		return nil, err
	}
	if _, ok := a.detail["content"].(map[string]any); !ok {
		return nil, fmt.Errorf("%s: missing \"content\" object", assetPath)
	}
	subsPath := filepath.Join(dir, "submissions.json")
	if err := readJSON(subsPath, &a.submissions); err != nil {
		return nil, err
	}
	for i, sub := range a.submissions {
		for _, k := range []string{"_id", "_uuid", "_submission_time"} {
			if v, ok := sub[k]; !ok || v == nil || v == "" {
				return nil, fmt.Errorf("%s: record %d missing %s", subsPath, i, k)
			}
		}
		id := idKey(sub["_id"])
		if _, dup := a.byID[id]; dup {
			return nil, fmt.Errorf("%s: duplicate _id %s", subsPath, id)
		}
		a.byID[id] = sub
		for _, att := range attachments(sub) {
			name, _ := att["media_file_basename"].(string)
			if _, err := os.Stat(a.attachmentPath(name)); name == "" || err != nil {
				return nil, fmt.Errorf("%s: _id %s: attachment %q not in attachments/", subsPath, id, name)
			}
		}
	}
	sort.SliceStable(a.submissions, func(i, j int) bool {
		return lessID(idKey(a.submissions[i]["_id"]), idKey(a.submissions[j]["_id"]))
	})
	return a, nil
}

// attachmentPath keeps only the base name, so a basename like
// "../../users.json" cannot escape attachments/.
func (a *asset) attachmentPath(name string) string {
	return filepath.Join(a.dir, "attachments", filepath.Base(name))
}

func attachments(sub map[string]any) []map[string]any {
	list, _ := sub["_attachments"].([]any)
	out := make([]map[string]any, 0, len(list))
	for _, v := range list {
		if m, ok := v.(map[string]any); ok {
			out = append(out, m)
		}
	}
	return out
}
