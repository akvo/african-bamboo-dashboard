package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func newServer(t *testing.T) *httptest.Server {
	t.Helper()
	s, err := load(writeTree(t, fixture()))
	if err != nil {
		t.Fatal(err)
	}
	srv := httptest.NewServer(s)
	t.Cleanup(srv.Close)
	return srv
}

// call sends a request as admin:pw unless auth is false and returns
// the status and raw body.
func call(t *testing.T, srv *httptest.Server, method, path, body string, auth bool) (int, []byte) {
	t.Helper()
	req, _ := http.NewRequest(method, srv.URL+path, strings.NewReader(body))
	if auth {
		req.SetBasicAuth("admin", "pw")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, b
}

func decode(t *testing.T, b []byte) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatalf("bad json %q: %v", b, err)
	}
	return m
}

func TestAuth(t *testing.T) {
	srv := newServer(t)
	for _, path := range []string{"/me/", "/api/v2/assets/aTest/", "/api/v2/assets/aTest/data.json", "/nope"} {
		if code, _ := call(t, srv, "GET", path, "", false); code != 401 {
			t.Errorf("%s without auth: %d, want 401", path, code)
		}
	}
	req, _ := http.NewRequest("GET", srv.URL+"/me/", nil)
	req.SetBasicAuth("admin", "wrong")
	resp, _ := http.DefaultClient.Do(req)
	if resp.StatusCode != 401 {
		t.Errorf("wrong password: %d, want 401", resp.StatusCode)
	}
}

func TestMe(t *testing.T) {
	code, b := call(t, newServer(t), "GET", "/me", "", true)
	m := decode(t, b)
	// The app reads the display name from extra_details, as real Kobo
	// returns it (kobo_client.verify_credentials).
	extra, _ := m["extra_details"].(map[string]any)
	if code != 200 || m["username"] != "admin" || m["email"] != "admin@test.local" || extra["name"] != "Admin" {
		t.Fatalf("%d %s", code, b)
	}
}

func TestAssetDetail(t *testing.T) {
	srv := newServer(t)
	code, b := call(t, srv, "GET", "/api/v2/assets/aTest/?format=json", "", true)
	m := decode(t, b)
	content, _ := m["content"].(map[string]any)
	if code != 200 || m["uid"] != "aTest" || m["name"] != "Test form" || content["survey"] == nil {
		t.Fatalf("%d %s", code, b)
	}
	if code, _ := call(t, srv, "GET", "/api/v2/assets/nope/", "", true); code != 404 {
		t.Errorf("unknown asset: %d, want 404", code)
	}
	if code, _ := call(t, srv, "POST", "/api/v2/assets/aTest/", "", true); code != 404 {
		t.Errorf("POST asset: %d, want 404", code)
	}
}

func TestUnknownPath(t *testing.T) {
	srv := newServer(t)
	for _, p := range []string{"/", "/api/v1/x", "/api/v2/assets/aTest/data/other/"} {
		if code, _ := call(t, srv, "GET", p, "", true); code != 404 {
			t.Errorf("%s: %d, want 404", p, code)
		}
	}
}

func page(t *testing.T, srv *httptest.Server, query string) map[string]any {
	t.Helper()
	code, b := call(t, srv, "GET", "/api/v2/assets/aTest/data.json"+query, "", true)
	if code != 200 {
		t.Fatalf("data.json: %d %s", code, b)
	}
	return decode(t, b)
}

func results(m map[string]any) []map[string]any {
	var out []map[string]any
	for _, r := range m["results"].([]any) {
		out = append(out, r.(map[string]any))
	}
	return out
}

func TestPaging(t *testing.T) {
	srv := newServer(t)
	p1 := page(t, srv, "?limit=2&start=0&sort=%7B%22_id%22%3A1%7D")
	r1 := results(p1)
	if p1["count"].(float64) != 3 || len(r1) != 2 || r1[0]["_id"].(float64) != 1 || r1[1]["_id"].(float64) != 2 {
		t.Fatalf("page 1: %v", p1)
	}
	next, _ := p1["next"].(string)
	if !strings.HasPrefix(next, "http://") || !strings.Contains(next, "start=2") || p1["previous"] != nil {
		t.Fatalf("page 1 links: next=%v previous=%v", p1["next"], p1["previous"])
	}
	p2 := page(t, srv, "?limit=2&start=2")
	if r2 := results(p2); len(r2) != 1 || r2[0]["_id"].(float64) != 3 || p2["next"] != nil {
		t.Fatalf("page 2: %v", p2)
	}
	if r := results(page(t, srv, "?start=10")); len(r) != 0 {
		t.Fatalf("past the end: %v", r)
	}
	// An exactly full last page must end the client's loop.
	if p := page(t, srv, "?limit=3"); p["next"] != nil || len(results(p)) != 3 {
		t.Fatalf("exact page: %v", p)
	}
}

func TestAttachments(t *testing.T) {
	srv := newServer(t)
	att := results(page(t, srv, ""))[0]["_attachments"].([]any)[0].(map[string]any)
	for _, k := range []string{"download_url", "download_large_url", "download_medium_url", "download_small_url"} {
		if u, _ := att[k].(string); !strings.HasPrefix(u, srv.URL+"/api/v2/assets/aTest/data/1/attachments/att1/") {
			t.Errorf("%s = %v", k, att[k])
		}
	}
	path := strings.TrimPrefix(att["download_medium_url"].(string), srv.URL)
	req, _ := http.NewRequest("GET", srv.URL+path, nil)
	req.SetBasicAuth("admin", "pw")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	b, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 || string(b) != "JPEGBYTES" || resp.Header.Get("Content-Type") != "image/jpeg" {
		t.Fatalf("attachment: %d %q %s", resp.StatusCode, b, resp.Header.Get("Content-Type"))
	}
	for _, p := range []string{"/api/v2/assets/aTest/data/1/attachments/nope/", "/api/v2/assets/aTest/data/9/attachments/att1/"} {
		if code, _ := call(t, srv, "GET", p, "", true); code != 404 {
			t.Errorf("%s: %d, want 404", p, code)
		}
	}
}

func TestValidationStatus(t *testing.T) {
	srv := newServer(t)
	body := `{"payload":{"submission_ids":["1",2],"validation_status.uid":"validation_status_approved"}}`
	code, b := call(t, srv, "PATCH", "/api/v2/assets/aTest/data/validation_statuses/", body, true)
	if code != 200 || decode(t, b)["detail"] != "2 submissions have been updated" {
		t.Fatalf("%d %s", code, b)
	}
	r := results(page(t, srv, ""))
	for i, want := range []string{"validation_status_approved", "validation_status_approved", ""} {
		vs, _ := r[i]["_validation_status"].(map[string]any)
		if got, _ := vs["uid"].(string); got != want {
			t.Errorf("_id %v status %q, want %q", r[i]["_id"], got, want)
		}
	}
	if vs := r[0]["_validation_status"].(map[string]any); vs["label"] != "Approved" {
		t.Errorf("status fields: %v", vs)
	}
}

func TestValidationStatusRejectsBadInput(t *testing.T) {
	srv := newServer(t)
	cases := map[string]string{
		"unknown id": `{"payload":{"submission_ids":["3","99"],"validation_status.uid":"validation_status_approved"}}`,
		"bad uid":    `{"payload":{"submission_ids":["3"],"validation_status.uid":"approved"}}`,
		"no ids":     `{"payload":{"submission_ids":[],"validation_status.uid":"validation_status_approved"}}`,
		"not json":   `{`,
	}
	for name, body := range cases {
		if code, b := call(t, srv, "PATCH", "/api/v2/assets/aTest/data/validation_statuses/", body, true); code != 400 {
			t.Errorf("%s: %d %s, want 400", name, code, b)
		}
	}
	// "unknown id" must not have touched _id 3.
	if vs := results(page(t, srv, ""))[2]["_validation_status"]; vs != nil {
		t.Errorf("_id 3 changed: %v", vs)
	}
}

func TestBulk(t *testing.T) {
	srv := newServer(t)
	body := `{"payload":{"submission_ids":["2"],"data":{"q1":"edited","new/field":"x"}}}`
	code, b := call(t, srv, "PATCH", "/api/v2/assets/aTest/data/bulk/", body, true)
	m := decode(t, b)
	if code != 200 || m["successes"].(float64) != 1 || m["failures"].(float64) != 0 {
		t.Fatalf("%d %s", code, b)
	}
	sub := results(page(t, srv, ""))[1]
	if sub["q1"] != "edited" || sub["new/field"] != "x" || sub["_uuid"] != "u2" {
		t.Fatalf("not merged: %v", sub)
	}
	bad := `{"payload":{"submission_ids":["2","99"],"data":{"q1":"nope"}}}`
	if code, _ := call(t, srv, "PATCH", "/api/v2/assets/aTest/data/bulk/", bad, true); code != 400 {
		t.Errorf("unknown id: %d, want 400", code)
	}
	if code, _ := call(t, srv, "PATCH", "/api/v2/assets/aTest/data/bulk/", `{"payload":{"submission_ids":["2"]}}`, true); code != 400 {
		t.Errorf("missing data: %d, want 400", code)
	}
	if sub := results(page(t, srv, ""))[1]; sub["q1"] != "edited" {
		t.Fatalf("rejected request changed data: %v", sub)
	}
}
