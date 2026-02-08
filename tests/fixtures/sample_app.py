from openai import OpenAI

client = OpenAI(api_key="sk-demo1234567890abcdefghijklmnopqrstuvwxyz1234")
response = client.chat.completions.create(model="gpt-3.5-turbo", messages=[])
