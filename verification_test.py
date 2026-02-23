import openai

ALIBABA_URL = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation'

# xAI Grok test
client = openai.OpenAI(api_key="xai-12345678901234567890", base_url="https://api.x.ai/v1")
response = client.chat.completions.create(model="grok-1.5-vision-preview", messages=[{"role": "user", "content": "Hello!"}])

# Alibaba Qwen test
client2 = openai.OpenAI(api_key="sk-12345678901234567890123456789012", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
response2 = client2.chat.completions.create(model="qwen-max", messages=[{"role": "user", "content": "Hi!"}])

response3 = client.chat.completions.create(model="qwen-coder", messages=[{"role": "user", "content": "Code!"}])

deepseek_api_key = "sk-09876543210987654321098765432109"
client_deepseek = openai.OpenAI(api_key=deepseek_api_key)
