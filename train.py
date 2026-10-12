from model import pipeline
from pathlib import Path

# Train all ML models
print("Training models...")
pipeline.load_and_train()

# Save the trained models, TF-IDF vectorizer and metrics
print("Saving trained models...")
Path('models').mkdir(exist_ok=True)
pipeline.save_model("models/pretrained_model_01.pkl")

print("Training completed successfully.")
