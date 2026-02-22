"""Demo FastAPI app with AI integration — triggers multiple detection patterns."""

from fastapi import FastAPI
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key="sk-demo1234567890abcdefghijklmnopqrstuvwxyz1234")


@app.post("/chat")
async def chat(message: str):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": message}]
    )
    return {"response": response.choices[0].message.content}


@app.post("/embed")
async def embed(text: str):
    response = client.embeddings.create(model="text-embedding-ada-002", input=text)
    return {"embedding": response.data[0].embedding}
