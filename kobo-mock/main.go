// Command kobo-mock is a local stand-in for the KoboToolbox API
// endpoints the dashboard uses. Data is read once from /data; writes
// live in memory until restart.
package main

import (
	"log"
	"net/http"
)

func main() {
	s, err := load("/data")
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("loaded %d users, %d assets; listening on :8090", len(s.users), len(s.assets))
	log.Fatal(http.ListenAndServe(":8090", s))
}
