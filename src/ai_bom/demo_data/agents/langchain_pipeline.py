"""LangChain pipeline with tool usage — triggers orchestration detection."""
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import ShellTool
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")

tools = [ShellTool()]

prompt = PromptTemplate.from_template(
    "Answer the user question: {input}\n{agent_scratchpad}"
)

agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
