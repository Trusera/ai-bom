package main

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/Trusera/trusera-sdk-go"
)

func main() {
	// Create Trusera client
	client := trusera.NewClient(
		"your-api-key",
		trusera.WithAgentID("web-agent"),
		trusera.WithFlushInterval(30*time.Second),
	)
	defer client.Close()

	// Wrap HTTP client with Trusera interception
	httpClient := trusera.WrapHTTPClient(&http.Client{}, client, trusera.InterceptorOptions{
		Enforcement: trusera.ModeWarn, // Log warnings but allow all requests

		// URLs matching these patterns won't be intercepted
		ExcludePatterns: []string{
			"api.trusera.io",
			"localhost",
		},

		// URLs matching these patterns will trigger policy evaluation
		BlockPatterns: []string{
			"malicious.com",
			"blocked-api.io",
		},
	})

	// Example 1: Normal API request (allowed)
	fmt.Println("\n=== Example 1: Normal API Request ===")
	resp, err := httpClient.Get("https://api.github.com/users/octocat")
	if err != nil {
		log.Printf("Request failed: %v", err)
	} else {
		fmt.Printf("Status: %s\n", resp.Status)
		resp.Body.Close()
	}

	// Example 2: Request to blocked domain (warned in warn mode)
	fmt.Println("\n=== Example 2: Request to Blocked Domain ===")
	resp, err = httpClient.Get("https://malicious.com/data")
	if err != nil {
		log.Printf("Request blocked: %v", err)
	} else {
		fmt.Printf("Status: %s (allowed in warn mode)\n", resp.Status)
		resp.Body.Close()
	}

	// Example 3: POST request with body
	fmt.Println("\n=== Example 3: POST Request ===")
	req, _ := http.NewRequest("POST", "https://httpbin.org/post",
		io.NopCloser(io.Reader(nil)))
	req.Header.Set("Content-Type", "application/json")

	resp, err = httpClient.Do(req)
	if err != nil {
		log.Printf("Request failed: %v", err)
	} else {
		fmt.Printf("Status: %s\n", resp.Status)
		resp.Body.Close()
	}

	// Flush events before exit
	if err := client.Flush(); err != nil {
		log.Printf("Failed to flush events: %v", err)
	}

	fmt.Println("\nAll requests intercepted and logged to Trusera")
}
