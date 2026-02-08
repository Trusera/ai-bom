from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, [], None)
executor = AgentExecutor(agent=agent, tools=[], verbose=True)
