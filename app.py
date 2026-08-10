from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from contextlib import asynccontextmanager
from model import pipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to load and train ML models on application startup."""
    pipeline.load_and_train()
    yield

# Initialize FastAPI App with Lifespan
app = FastAPI(
    title="Fake News Detection API",
    description="FastAPI service powered by NLP and Machine Learning for real-time fake news classification.",
    version="1.0.0",
    lifespan=lifespan
)

# Input Schema for /predict
class NewsPredictionRequest(BaseModel):
    text: str = Field(..., description="The news article title or text body to analyze", min_length=3)
    model: Optional[str] = Field("logistic_regression", description="Classifier model choice: 'logistic_regression', 'passive_aggressive', 'naive_bayes', 'decision_tree', or 'random_forest'")

# Output Schema for /predict
class NewsPredictionResponse(BaseModel):
    prediction: str
    label: int
    confidence: Optional[float]
    model_used: str
    cleaned_text: str

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Fake News Detection FastAPI Service is running.",
        "available_models": list(pipeline.trained_models.keys()),
        "metrics_url": "/metrics",
    }

@app.get("/metrics")
def get_metrics():
    return {"metrics": pipeline.model_metrics}

@app.post("/predict", response_model=NewsPredictionResponse)
def predict_news(request: NewsPredictionRequest):
    try:
        result = pipeline.predict(text=request.text, model_key=request.model)
        return NewsPredictionResponse(**result)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
