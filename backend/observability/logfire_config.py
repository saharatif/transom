import logfire
import os


def init_logfire():
    """Configure Logfire observability. The token is optional: a demo
    deployment without a Logfire account runs with export disabled
    instead of crashing at startup (previously a bare os.environ[...]
    KeyError took the whole app down).
    """
    token = os.environ.get("LOGFIRE_TOKEN")
    if token:
        logfire.configure(token=token, service_name="property-intel")
    else:
        logfire.configure(send_to_logfire=False, service_name="property-intel")
    # Auto-instrument OpenAI and Pydantic either way — spans are simply
    # not exported when send_to_logfire is off.
    logfire.instrument_openai()
    logfire.instrument_pydantic()
