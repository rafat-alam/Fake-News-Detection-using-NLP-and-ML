import joblib
import pandas as pd
import re
import string
import warnings
from typing import Dict, Optional

# NLTK
import nltk
from nltk.corpus import stopwords

# Scikit-Learn
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, PassiveAggressiveClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.tree import DecisionTreeClassifier

# Suppress warning messages during model training
warnings.filterwarnings('ignore')

# Download stopwords from NLTK
nltk.download('stopwords', quiet=True)

stop_words = set(stopwords.words('english'))

def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()                                                   # Converts text to lowercase
    text = re.sub(r'https?://\S+|www\.\S+', '', text)                     # Removes URLs
    text = re.sub(r'<.*?>+', '', text)                                    # Removes HTML tags
    text = re.sub(r'[%s]' % re.escape(string.punctuation), '', text)      # Removes punctuation
    text = re.sub(r'\n', ' ', text)                                       # Removes newlines
    text = re.sub(r'\w*\d\w*', '', text)                                  # Removes numbers
    words = text.split()                                                  # Splits text into words
    words = [w for w in words if w not in stop_words and len(w) > 2]      # Removes stopwords and short words
    return " ".join(words)                                                # Joins words back into text

class ModelPipeline:
    def __init__(self):
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.trained_models: Dict = {}
        self.model_metrics: Dict = {}

    def load_and_train(self):
        true_df = pd.read_csv('dataset/True.csv')                          # Loads True news dataset
        false_df = pd.read_csv('dataset/Fake.csv')                         # Loads Fake news dataset

        true_df['label'] = 1                                               # Assigns label 1 to True news
        false_df['label'] = 0                                              # Assigns label 0 to Fake news

        data = pd.concat([true_df, false_df], axis=0).sample(frac=1, random_state=42).reset_index(drop=True)       # Concatenates and shuffles the dataset
        data = data.dropna(subset=['text', 'title']).copy()                                                        # Removes rows with missing values in text or title
        data['full_content'] = data['title'].fillna('') + " " + data['text'].fillna('')                            # Concatenates title and text
        data['cleaned_content'] = data['full_content'].apply(clean_text)                                           # Cleans the text

        self.tfidf_vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))              # Creates a TF-IDF vectorizer
        X = self.tfidf_vectorizer.fit_transform(data['cleaned_content'])                            # Transforms the text data into TF-IDF vectors
        y = data['label'].values                                                                    # Extracts the labels

        # Split the data into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Define the models to be trained
        raw_models = {
            'naive_bayes': ('Multinomial Naive Bayes', MultinomialNB()),
            'logistic_regression': ('Logistic Regression', LogisticRegression()),
            'passive_aggressive': ('Passive Aggressive Classifier', PassiveAggressiveClassifier()),
            'decision_tree': ('Decision Tree', DecisionTreeClassifier()),
            'random_forest': ('Random Forest', RandomForestClassifier())
        }

        # Train the models
        for key, (display_name, model) in raw_models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            
            acc = float(accuracy_score(y_test, y_pred))
            prec = float(precision_score(y_test, y_pred))
            rec = float(recall_score(y_test, y_pred))
            f1 = float(f1_score(y_test, y_pred))

            self.trained_models[key] = (display_name, model)
            self.model_metrics[key] = {
                'model_name': display_name,
                'accuracy': round(acc, 5),
                'precision': round(prec, 5),
                'recall': round(rec, 5),
                'f1_score': round(f1, 5),
            }

    def predict(self, title: str, text: str, model_key: str = 'logistic_regression') -> Dict:
        if not model_key:
            model_key = "logistic_regression"

        model_key = model_key.lower()

        if self.tfidf_vectorizer is None:
            raise ValueError("Models are not initialized yet.")

        if model_key not in self.trained_models:
            raise KeyError(f"Model '{model_key}' not found. Available options: {list(self.trained_models.keys())}")

        display_name, selected_model = self.trained_models[model_key]

        cleaned = clean_text(title + " " + text)
        if not cleaned:
            raise ValueError("Input text contains no valid words after preprocessing.")

        # Predict using the selected model
        vectorized = self.tfidf_vectorizer.transform([cleaned])
        prediction_val = int(selected_model.predict(vectorized)[0])

        # Calculate confidence
        confidence_val = None
        if hasattr(selected_model, "predict_proba"):
            probs = selected_model.predict_proba(vectorized)[0]
            confidence_val = round(float(max(probs)), 5)

        # Determine the result label
        result_label = "REAL NEWS" if prediction_val == 1 else "FAKE NEWS"

        # Return the result
        return {
            "prediction": result_label,
            "label": prediction_val,
            "confidence": confidence_val,
            "model_used": display_name,
            "cleaned_text": cleaned
        }

    # Save the trained models, TF-IDF vectorizer and metrics
    def save_model(self, path="model.pkl"):
        joblib.dump({
            "tfidf_vectorizer": self.tfidf_vectorizer,
            "trained_models": self.trained_models,
            "model_metrics": self.model_metrics
        }, path)

    # Load the previously trained models, TF-IDF vectorizer and metrics
    def load_model(self, path="model.pkl"):
        saved_data = joblib.load(path)

        self.tfidf_vectorizer = saved_data["tfidf_vectorizer"]
        self.trained_models = saved_data["trained_models"]
        self.model_metrics = saved_data["model_metrics"]

# Global singleton instance
pipeline = ModelPipeline()
