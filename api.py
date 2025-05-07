import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from analysis_engine import recommend_assessment_api_format

app = FastAPI(
    title="SHL Assessment Recommender API",
    description="API for recommending SHL assessments based on job requirements",
    version="1.0.0"
)

#  CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Model
class QueryRequest(BaseModel):
    query: str

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Recommendation endpoint
@app.post("/recommend")
async def recommend(request: QueryRequest):
    query = request.query
    if not query or query.strip() == "":
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        # API-formatted recommendation function
        result = recommend_assessment_api_format(query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("api:app", host="127.0.0.1", port=port, reload=True)