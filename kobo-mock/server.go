package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
)

var statusLabels = map[string]string{
	"validation_status_on_hold":      "On Hold",
	"validation_status_approved":     "Approved",
	"validation_status_not_approved": "Not Approved",
}

// ServeHTTP holds the store lock for the whole request; backend and
// worker call concurrently.
// ponytail: one global lock, fine for a few dev requests.
func (s *store) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	log.Printf("%s %s", r.Method, r.URL.RequestURI())
	s.mu.Lock()
	defer s.mu.Unlock()
	s.route(w, r)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func detail(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"detail": msg})
}

func (s *store) route(w http.ResponseWriter, r *http.Request) {
	name, pass, _ := r.BasicAuth()
	u, ok := s.users[name]
	if !ok || u.Password != pass {
		detail(w, http.StatusUnauthorized, "Invalid username/password.")
		return
	}
	p := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	if len(p) == 1 && p[0] == "me" && r.Method == http.MethodGet {
		writeJSON(w, http.StatusOK, map[string]any{
			"username": u.Username, "email": u.Email,
			"extra_details": map[string]string{"name": u.Name},
		})
		return
	}
	if len(p) < 4 || p[0] != "api" || p[1] != "v2" || p[2] != "assets" {
		detail(w, http.StatusNotFound, "Not found.")
		return
	}
	a, ok := s.assets[p[3]]
	if !ok {
		detail(w, http.StatusNotFound, "Not found.")
		return
	}
	rest := strings.Join(p[4:], "/")
	switch {
	case rest == "" && r.Method == http.MethodGet:
		out := map[string]any{"uid": a.uid}
		for k, v := range a.detail {
			out[k] = v
		}
		writeJSON(w, http.StatusOK, out)
	case rest == "data.json" && r.Method == http.MethodGet:
		s.list(w, r, a)
	case rest == "data/validation_statuses" && r.Method == http.MethodPatch:
		s.validate(w, r, a)
	case rest == "data/bulk" && r.Method == http.MethodPatch:
		s.bulk(w, r, a)
	case len(p) == 8 && p[4] == "data" && p[6] == "attachments" && r.Method == http.MethodGet:
		serveAttachment(w, a, p[5], p[7])
	default:
		detail(w, http.StatusNotFound, "Not found.")
	}
}

func intParam(r *http.Request, key string, def int) int {
	n, err := strconv.Atoi(r.URL.Query().Get(key))
	if err != nil || n < 0 {
		return def
	}
	return n
}

func pageURL(r *http.Request, start, limit int) string {
	return fmt.Sprintf("http://%s%s?limit=%d&start=%d", r.Host, r.URL.Path, limit, start)
}

func (s *store) list(w http.ResponseWriter, r *http.Request, a *asset) {
	start := intParam(r, "start", 0)
	limit := intParam(r, "limit", 100)
	if limit == 0 {
		limit = 100
	}
	total := len(a.submissions)
	start = min(start, total)
	end := min(start+limit, total)
	results := make([]map[string]any, 0, end-start)
	for _, sub := range a.submissions[start:end] {
		results = append(results, withURLs(sub, r.Host, a.uid))
	}
	var next any
	if end < total {
		next = pageURL(r, end, limit)
	}
	// "previous" is never read by the app.
	writeJSON(w, http.StatusOK, map[string]any{
		"count": total, "next": next, "previous": nil, "results": results,
	})
}

// withURLs copies a submission and fills each attachment's download
// URLs from the request host, so data files never hold a hostname.
func withURLs(sub map[string]any, host, uid string) map[string]any {
	out := make(map[string]any, len(sub))
	for k, v := range sub {
		out[k] = v
	}
	atts := attachments(sub)
	if len(atts) == 0 {
		return out
	}
	list := make([]any, 0, len(atts))
	for _, att := range atts {
		c := make(map[string]any, len(att)+4)
		for k, v := range att {
			c[k] = v
		}
		base := fmt.Sprintf("http://%s/api/v2/assets/%s/data/%s/attachments/%v/",
			host, uid, idKey(sub["_id"]), att["uid"])
		for _, k := range []string{"download_url", "download_large_url", "download_medium_url", "download_small_url"} {
			c[k] = base
		}
		list = append(list, c)
	}
	out["_attachments"] = list
	return out
}

func serveAttachment(w http.ResponseWriter, a *asset, id, attUID string) {
	sub, ok := a.byID[id]
	if !ok {
		detail(w, http.StatusNotFound, "Not found.")
		return
	}
	for _, att := range attachments(sub) {
		if idKey(att["uid"]) != attUID {
			continue
		}
		name, _ := att["media_file_basename"].(string)
		b, err := os.ReadFile(a.attachmentPath(name))
		if err != nil {
			detail(w, http.StatusNotFound, "Not found.")
			return
		}
		if mt, _ := att["mimetype"].(string); mt != "" {
			w.Header().Set("Content-Type", mt)
		}
		w.Write(b)
		return
	}
	detail(w, http.StatusNotFound, "Not found.")
}

func decodePayload(r *http.Request) (map[string]any, bool) {
	var body struct {
		Payload map[string]any `json:"payload"`
	}
	dec := json.NewDecoder(r.Body)
	dec.UseNumber()
	if err := dec.Decode(&body); err != nil || body.Payload == nil {
		return nil, false
	}
	return body.Payload, true
}

// targets resolves submission_ids all-or-nothing: one unknown id
// rejects the whole request, as real Kobo does.
func targets(w http.ResponseWriter, a *asset, payload map[string]any) ([]map[string]any, bool) {
	ids, _ := payload["submission_ids"].([]any)
	if len(ids) == 0 {
		detail(w, http.StatusBadRequest, "submission_ids is required")
		return nil, false
	}
	out := make([]map[string]any, 0, len(ids))
	for _, id := range ids {
		sub, ok := a.byID[idKey(id)]
		if !ok {
			detail(w, http.StatusBadRequest, "One or more submission ids are invalid")
			return nil, false
		}
		out = append(out, sub)
	}
	return out, true
}

func (s *store) validate(w http.ResponseWriter, r *http.Request, a *asset) {
	payload, ok := decodePayload(r)
	if !ok {
		detail(w, http.StatusBadRequest, "Invalid payload")
		return
	}
	uid, _ := payload["validation_status.uid"].(string)
	label, ok := statusLabels[uid]
	if !ok {
		detail(w, http.StatusBadRequest, "Invalid validation status")
		return
	}
	subs, ok := targets(w, a, payload)
	if !ok {
		return
	}
	for _, sub := range subs {
		sub["_validation_status"] = map[string]any{"uid": uid, "label": label}
	}
	detail(w, http.StatusOK, fmt.Sprintf("%d submissions have been updated", len(subs)))
}

// bulk keeps _uuid unchanged on edit. Real Kobo issues a new one, but
// the app keys submissions on _id, so manual dev does not notice.
func (s *store) bulk(w http.ResponseWriter, r *http.Request, a *asset) {
	payload, ok := decodePayload(r)
	data, isMap := payload["data"].(map[string]any)
	if !ok || !isMap {
		detail(w, http.StatusBadRequest, "Invalid payload")
		return
	}
	subs, ok := targets(w, a, payload)
	if !ok {
		return
	}
	for _, sub := range subs {
		for k, v := range data {
			sub[k] = v
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"count": len(subs), "successes": len(subs), "failures": 0,
	})
}
