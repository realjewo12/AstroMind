from llm import prompts
from llm.client import get_llm
from llm.prompts import build_prompt

llm = get_llm()
prompt = build_prompt("Hello, I'm feeling stressed")
response = llm.invoke(prompt)
print(response)