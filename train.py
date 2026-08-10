from model import pipeline

# Train all ML models
print("Training models...")
pipeline.load_and_train()

# Save the trained models, TF-IDF vectorizer and metrics
print("Saving trained models...")
pipeline.save_model("models/pretrained_model_01.pkl")

print("Training completed successfully.")
print("Model saved as model.pkl")