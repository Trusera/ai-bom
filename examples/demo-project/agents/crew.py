"""Multi-agent CrewAI setup — triggers agent framework and multi-agent detection."""

from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4", api_key="sk-demo1234567890abcdefghijklmnopqrstuvwxyz5678")

researcher = Agent(
    role="Researcher",
    goal="Research the topic thoroughly",
    backstory="You are an expert researcher.",
    llm=llm,
    allow_delegation=True,
)

writer = Agent(
    role="Writer",
    goal="Write compelling content",
    backstory="You are a skilled writer.",
    llm=llm,
    allow_delegation=False,
)

research_task = Task(description="Research the latest AI trends", agent=researcher)

write_task = Task(description="Write a blog post about AI trends", agent=writer)

crew = Crew(agents=[researcher, writer], tasks=[research_task, write_task], verbose=True)

result = crew.kickoff()
