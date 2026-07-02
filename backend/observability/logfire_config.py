import logfire
import os

def init_logfire():
    logfire.configure(token=os.environ["LOGFIRE_TOKEN"], service_name="property-intel")
    # Auto-instrument FastAPI, OpenAI, and HTTP calls
    logfire.instrument_openai()
    logfire.instrument_pydantic()
