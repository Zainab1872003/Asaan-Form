# FastAPI entry point
from fastapi import FastAPI
from app.apis.routes import router

app = FastAPI(title="FYP AI Agent System")

app.include_router(router)

@app.get("/")
def root():
    return {"status": "AI system running"}
