"""Embedding service with vector store — triggers embedding detection."""

import chromadb
from openai import OpenAI

client = OpenAI(api_key="sk-demo1234567890abcdefghijklmnopqrstuvwxyz9012")
chroma_client = chromadb.Client()
collection = chroma_client.create_collection("documents")


def embed_document(text: str, doc_id: str):
    response = client.embeddings.create(model="text-embedding-ada-002", input=text)
    collection.add(embeddings=[response.data[0].embedding], documents=[text], ids=[doc_id])


def search(query: str, n_results: int = 5):
    response = client.embeddings.create(model="text-embedding-ada-002", input=query)
    results = collection.query(query_embeddings=[response.data[0].embedding], n_results=n_results)
    return results
