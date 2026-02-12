package main

import (
	"fmt"
	"log"

	"github.com/Trusera/trusera-sdk-go"
)

func main() {
	// Create Trusera client and intercepted HTTP client in one call
	client, httpClient, err := trusera.MustRegisterAndIntercept(
		"your-api-key",
		"security-agent",
		"custom",
		trusera.InterceptorOptions{
			Enforcement: trusera.ModeBlock, // Reject blocked requests

			BlockPatterns: []string{
				"malicious.com",
				"phishing.net",
				"internal-admin",
			},

			ExcludePatterns: []string{
				"api.trusera.io",
			},
		},
	)

	if err != nil {
		log.Fatalf("Failed to initialize: %v", err)
	}
	defer client.Close()

	fmt.Println("Agent registered and HTTP client wrapped with block mode")

	// Example 1: Allowed request
	fmt.Println("\n=== Allowed Request ===")
	resp, err := httpClient.Get("https://api.github.com")
	if err != nil {
		log.Printf("Error: %v", err)
	} else {
		fmt.Printf("Success: %s\n", resp.Status)
		resp.Body.Close()
	}

	// Example 2: Blocked request
	fmt.Println("\n=== Blocked Request ===")
	resp, err = httpClient.Get("https://malicious.com/steal-data")
	if err != nil {
		fmt.Printf("Blocked: %v\n", err)
		// This is expected - request was blocked by policy
	} else {
		fmt.Printf("Unexpected success: %s\n", resp.Status)
		resp.Body.Close()
	}

	// Example 3: Another blocked request
	fmt.Println("\n=== Another Blocked Request ===")
	resp, err = httpClient.Get("https://api.example.com/internal-admin/users")
	if err != nil {
		fmt.Printf("Blocked: %v\n", err)
	} else {
		fmt.Printf("Unexpected success: %s\n", resp.Status)
		resp.Body.Close()
	}

	fmt.Println("\n=== Summary ===")
	fmt.Println("Block mode successfully prevented requests to blocked patterns")
	fmt.Println("All events recorded in Trusera for compliance audit")
}
