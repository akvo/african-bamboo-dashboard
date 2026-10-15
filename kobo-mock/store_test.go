package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// writeTree creates files (path -> content) under a temp dir.
func writeTree(t *testing.T, files map[string]string) string {
	t.Helper()
	dir := t.TempDir()
	for name, body := range files {
		p := filepath.Join(dir, name)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

// fixture is a valid data dir: one user, one asset, three
// submissions stored out of _id order, one image on _id 1.
func fixture() map[string]string {
	return map[string]string{
		"users.json": `[{"username":"admin","password":"pw",
			"name":"Admin","email":"admin@test.local"}]`,
		"aTest/asset.json": `{"name":"Test form",
			"content":{"survey":[{"type":"text","name":"q1"}],"choices":[]}}`,
		"aTest/submissions.json": `[
			{"_id":3,"_uuid":"u3","_submission_time":"2026-01-03T00:00:00","q1":"c"},
			{"_id":1,"_uuid":"u1","_submission_time":"2026-01-01T00:00:00","q1":"a",
			 "_attachments":[{"uid":"att1","media_file_basename":"photo.jpg",
			   "mimetype":"image/jpeg","question_xpath":"photo"}]},
			{"_id":2,"_uuid":"u2","_submission_time":"2026-01-02T00:00:00","q1":"b"}]`,
		"aTest/attachments/photo.jpg": "JPEGBYTES",
	}
}

// with returns a copy of base with path set to body, or removed
// when body is empty.
func with(base map[string]string, path, body string) map[string]string {
	out := map[string]string{}
	for k, v := range base {
		out[k] = v
	}
	if body == "" {
		delete(out, path)
	} else {
		out[path] = body
	}
	return out
}

func TestLoadValid(t *testing.T) {
	s, err := load(writeTree(t, fixture()))
	if err != nil {
		t.Fatal(err)
	}
	a := s.assets["aTest"]
	if a == nil || len(a.submissions) != 3 || s.users["admin"].Email != "admin@test.local" {
		t.Fatalf("unexpected store: %+v", s)
	}
	for i, want := range []string{"1", "2", "3"} {
		if got := idKey(a.submissions[i]["_id"]); got != want {
			t.Errorf("submission %d has _id %s, want %s", i, got, want)
		}
	}
}

func TestLoadErrors(t *testing.T) {
	cases := map[string]struct {
		files map[string]string
		want  string
	}{
		"bad json":           {with(fixture(), "aTest/asset.json", `{`), "asset.json"},
		"no users file":      {with(fixture(), "users.json", ""), "users.json"},
		"user no password":   {with(fixture(), "users.json", `[{"username":"x"}]`), "users.json"},
		"missing content":    {with(fixture(), "aTest/asset.json", `{"name":"x"}`), "content"},
		"no submissions":     {with(fixture(), "aTest/submissions.json", ""), "submissions.json"},
		"missing _id":        {with(fixture(), "aTest/submissions.json", `[{"_uuid":"u","_submission_time":"t"}]`), "_id"},
		"missing _uuid":      {with(fixture(), "aTest/submissions.json", `[{"_id":1,"_submission_time":"t"}]`), "_uuid"},
		"duplicate _id":      {with(fixture(), "aTest/submissions.json", `[{"_id":1,"_uuid":"a","_submission_time":"t"},{"_id":"1","_uuid":"b","_submission_time":"t"}]`), "duplicate _id 1"},
		"missing image":      {with(fixture(), "aTest/attachments/photo.jpg", ""), "photo.jpg"},
		"traversal basename": {with(fixture(), "aTest/submissions.json", `[{"_id":1,"_uuid":"a","_submission_time":"t","_attachments":[{"uid":"x","media_file_basename":"../../users.json"}]}]`), "not in attachments/"},
	}
	for name, c := range cases {
		t.Run(name, func(t *testing.T) {
			_, err := load(writeTree(t, c.files))
			if err == nil || !strings.Contains(err.Error(), c.want) {
				t.Fatalf("err = %v, want it to mention %q", err, c.want)
			}
		})
	}
}

func TestLoadEmptySubmissions(t *testing.T) {
	s, err := load(writeTree(t, with(fixture(), "aTest/submissions.json", "[]")))
	if err != nil || len(s.assets["aTest"].submissions) != 0 {
		t.Fatalf("err = %v", err)
	}
}
