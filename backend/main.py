from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .observability.logfire_config import init_logfire
import logfire

load_dotenv()
init_logfire()
app = FastAPI(title="Property Intelligence API")
logfire.instrument_fastapi(app)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok"}
