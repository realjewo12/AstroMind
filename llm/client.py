import os
from dotenv import load_dotenv
from langchain_ibm import WatsonxLLM
from pydantic.v1 import SecretStr

load_dotenv()

_required_vars = ["WATSONX_API_KEY", "WATSONX_PROJECT_ID", "WATSONX_URL", "WATSONX_MODEL_ID"]
_missing = [k for k in _required_vars if not os.getenv(k)]
if _missing:
    raise EnvironmentError(f"Missing required environment variables: {_missing}")

_llm_instance: WatsonxLLM | None = None

def get_llm() -> WatsonxLLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = WatsonxLLM(
            model_id=os.environ["WATSONX_MODEL_ID"],
            project_id=os.environ["WATSONX_PROJECT_ID"],
            url=SecretStr(os.environ["WATSONX_URL"]),
            apikey=SecretStr(os.environ["WATSONX_API_KEY"]),
            params={
                "decoding_method": "greedy",
                "max_new_tokens": 512,
                "temperature": 0.3,
            },
        )
    return _llm_instance