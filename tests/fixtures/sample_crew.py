from crewai import Agent, Crew
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4", api_key="sk-demo1234567890abcdefghijklmnopqrstuvwxyz5678")
agent = Agent(role="Researcher", goal="Research", backstory="Expert", llm=llm)
crew = Crew(agents=[agent], tasks=[], verbose=True)
crew.kickoff()
