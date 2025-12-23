# API Routes
from fastapi import APIRouter
from app.graphs.main_graph import build_graph

router = APIRouter()
graph = build_graph()

@router.post("/greet")
def greet(user_input: str):
    result = graph.invoke({
        "user_input": user_input
    })

    return {
        "response": result["response"]
    }
