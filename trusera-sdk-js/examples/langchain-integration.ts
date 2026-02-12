/**
 * LangChain.js integration example for Trusera SDK
 * Demonstrates automatic tracking of LLM calls, tool executions, and chains
 *
 * NOTE: This requires the langchain package to be installed:
 * npm install langchain
 */

import { TruseraClient, TruseraLangChainHandler } from "trusera-sdk";

// These imports require the langchain package
// import { ChatOpenAI } from "langchain/chat_models/openai";
// import { AgentExecutor, createOpenAIFunctionsAgent } from "langchain/agents";
// import { DynamicTool } from "langchain/tools";
// import { ChatPromptTemplate } from "langchain/prompts";

async function main() {
  // 1. Create Trusera client
  const client = new TruseraClient({
    apiKey: process.env.TRUSERA_API_KEY || "tsk_your_api_key_here",
    debug: true,
  });

  // 2. Register the agent
  const agentId = await client.registerAgent("langchain-demo", "langchain");
  console.log(`✓ Agent registered: ${agentId}`);

  // 3. Create LangChain callback handler
  const handler = new TruseraLangChainHandler(client);

  console.log("\n--- LangChain Integration Demo ---");
  console.log("Note: This example requires the langchain package to be installed");
  console.log("Uncomment the imports and code below to run the full demo\n");

  /*
  // 4. Create LLM with Trusera handler
  const model = new ChatOpenAI({
    modelName: "gpt-4",
    temperature: 0.7,
    callbacks: [handler], // <-- Add Trusera handler here
  });

  // 5. Simple LLM invocation (will be tracked automatically)
  console.log("--- Simple LLM call ---");
  const response = await model.invoke("What are the top 3 AI security risks?");
  console.log(`Response: ${response.content}`);
  console.log(`Pending events: ${handler.getPendingEventCount()}`);

  // 6. Create tools with tracking
  const calculatorTool = new DynamicTool({
    name: "calculator",
    description: "Performs basic arithmetic operations",
    func: async (input: string) => {
      // This tool execution will be tracked
      const result = eval(input); // Don't use eval in production!
      return String(result);
    },
  });

  const searchTool = new DynamicTool({
    name: "web_search",
    description: "Searches the web for information",
    func: async (query: string) => {
      // Simulate web search
      return `Search results for: ${query}`;
    },
  });

  // 7. Create agent with tools
  const tools = [calculatorTool, searchTool];

  const prompt = ChatPromptTemplate.fromMessages([
    ["system", "You are a helpful AI assistant with access to tools."],
    ["human", "{input}"],
    ["placeholder", "{agent_scratchpad}"],
  ]);

  const agent = await createOpenAIFunctionsAgent({
    llm: model,
    tools,
    prompt,
  });

  const agentExecutor = new AgentExecutor({
    agent,
    tools,
    callbacks: [handler], // <-- Add handler to agent executor
  });

  // 8. Execute agent (all LLM calls, tool calls, and chains will be tracked)
  console.log("\n--- Agent execution (with tool calls) ---");
  const agentResult = await agentExecutor.invoke({
    input: "What is 15 * 42, and then search for information about that number?",
  });

  console.log(`Agent result: ${agentResult.output}`);
  console.log(`Pending events: ${handler.getPendingEventCount()}`);
  */

  // 9. Check tracked events
  console.log(`\n--- Events in queue: ${client.getQueueSize()} ---`);

  // 10. Cleanup
  await client.close();
  console.log("\n✓ Demo complete!");
}

main().catch(console.error);
