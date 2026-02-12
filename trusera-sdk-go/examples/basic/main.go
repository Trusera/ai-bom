package main

import (
	"fmt"
	"log"
	"time"

	"github.com/Trusera/trusera-sdk-go"
)

func main() {
	// Create a Trusera client
	client := trusera.NewClient(
		"your-api-key",
		trusera.WithAgentID("my-agent-123"),
		trusera.WithFlushInterval(10*time.Second),
	)
	defer client.Close()

	// Track a tool call event
	toolEvent := trusera.NewEvent(trusera.EventToolCall, "calculator").
		WithPayload("operation", "multiply").
		WithPayload("args", []int{5, 7}).
		WithPayload("result", 35)

	client.Track(toolEvent)
	fmt.Println("Tracked tool call event")

	// Track an LLM invocation
	llmEvent := trusera.NewEvent(trusera.EventLLMInvoke, "gpt-4").
		WithPayload("model", "gpt-4-turbo").
		WithPayload("prompt_tokens", 150).
		WithPayload("completion_tokens", 75).
		WithPayload("total_cost", 0.0045).
		WithMetadata("user_id", "user-456")

	client.Track(llmEvent)
	fmt.Println("Tracked LLM invocation event")

	// Track a data access event
	dataEvent := trusera.NewEvent(trusera.EventDataAccess, "database_query").
		WithPayload("query", "SELECT * FROM users WHERE role = 'admin'").
		WithPayload("rows_returned", 3).
		WithPayload("database", "postgres").
		WithMetadata("sensitivity", "high")

	client.Track(dataEvent)
	fmt.Println("Tracked data access event")

	// Track a decision event
	decisionEvent := trusera.NewEvent(trusera.EventDecision, "approve_purchase").
		WithPayload("amount", 1500.00).
		WithPayload("approved", true).
		WithPayload("confidence", 0.95).
		WithPayload("reasoning", "User has sufficient credit and good history")

	client.Track(decisionEvent)
	fmt.Println("Tracked decision event")

	// Manually flush events (optional - will auto-flush on interval or batch size)
	if err := client.Flush(); err != nil {
		log.Printf("Failed to flush events: %v", err)
	}

	fmt.Println("All events tracked successfully")
}
