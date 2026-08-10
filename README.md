<div align="center">

<img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/scikit--learn-1.6-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white"/>
<img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
<img src="https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white"/>

# 🔍 Fake News Detection API

**A production-ready REST API that classifies news articles as Real or Fake using Natural Language Processing and Machine Learning — powered by FastAPI and scikit-learn.**

[**🚀 Live Demo**](https://fake-news-detection-using-nlp-and-ml.onrender.com) · [**📖 Swagger UI**](https://fake-news-detection-using-nlp-and-ml.onrender.com/docs) · [**📊 ReDoc**](https://fake-news-detection-using-nlp-and-ml.onrender.com/redoc)

</div>

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [ML Models & Accuracy](#-ml-models--accuracy)
- [NLP Pipeline](#-nlp-pipeline)
- [API Reference](#-api-reference)
  - [GET /](#-get-)
  - [GET /metrics](#-get-metrics)
  - [POST /predict](#-post-predict)
- [Error Handling](#-error-handling)
- [Local Setup](#-local-setup)
- [Docker Setup](#-docker-setup)
- [Dataset](#-dataset)
- [Tech Stack](#-tech-stack)
- [License](#-license)

---

## 🧠 Overview

This project builds a **Fake News Detection system** that leverages:

- **TF-IDF Vectorization** for converting text to feature vectors
- **5 trained Machine Learning classifiers** for prediction
- A clean **FastAPI** REST interface for real-time inference
- **Docker** containerization for consistent deployments
- **Render** cloud hosting for production availability

The API accepts a news article's **title** and **body text**, processes them through a pre-trained NLP pipeline, and returns a prediction of **REAL NEWS** or **FAKE NEWS** along with a confidence score.

---

## ✨ Features

- ✅ **5 ML Models** — choose your preferred classifier per request
- ✅ **Confidence Scores** — probabilistic confidence where supported
- ✅ **Full Text Preprocessing** — URL removal, stopword filtering, punctuation stripping
- ✅ **Live Metrics Endpoint** — compare model accuracy, precision, recall, and F1-score
- ✅ **Swagger UI** — interactive browser-based API documentation
- ✅ **Docker Ready** — one-command container deployment
- ✅ **Non-root Container** — security-hardened Docker image
- ✅ **Auto-loaded Model** — pre-trained model loads on startup via FastAPI lifespan

---

## 📁 Project Structure

```
Fake-News-Detection-using-NLP/
│
├── app.py                      # FastAPI application & API endpoints
├── model.py                    # ML pipeline: preprocessing, training, prediction
├── train.py                    # Script to train and save the model
│
├── models/
│   └── pretrained_model_01.pkl # Saved model bundle (TF-IDF + classifiers + metrics)
│
├── dataset/
│   ├── True.csv                # Real news dataset (~53 MB)
│   └── Fake.csv                # Fake news dataset (~62 MB)
│
├── fakenews_detection.ipynb    # Exploratory Jupyter notebook
├── Dockerfile                  # Docker container configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## 📊 ML Models & Accuracy

All models are trained on the combined **True.csv + Fake.csv** dataset (~44,000 articles), with an 80/20 train/test split. Metrics are available live at [/metrics](https://fake-news-detection-using-nlp-and-ml.onrender.com/metrics).

| Model Key             | Model Name                    | Accuracy  | Precision | Recall    | F1-Score  |
|-----------------------|-------------------------------|-----------|-----------|-----------|-----------|
| `logistic_regression` | Logistic Regression           | 99.087%   | 98.702%   | 99.393%   | 99.046%   |
| `passive_aggressive`  | Passive Aggressive Classifier | 99.588%   | 99.510%   | 99.627%   | 99.568%   |
| `decision_tree`       | Decision Tree                 | 99.488%   | 99.279%   | 99.650%   | 99.464%   |
| `random_forest`       | Random Forest                 | **99.733%** | **99.512%** | **99.930%** | **99.720%** |
| `naive_bayes`         | Multinomial Naive Bayes       | 94.543%   | 93.912%   | 94.701%   | 94.305%   |

> 🏆 **Best Overall:** `random_forest` — highest accuracy and precision
> ⚡ **Fastest:** `naive_bayes` — lightweight, but lowest accuracy
> 🎯 **Default:** `logistic_regression` — excellent balance of speed and accuracy

---

## 🔬 NLP Pipeline

Every prediction goes through the following text preprocessing steps before vectorization:

```
Raw Input (title + text)
        │
        ▼
1. Lowercase conversion
        │
        ▼
2. URL removal          (https://, www.)
        │
        ▼
3. HTML tag stripping   (<br>, <p>, etc.)
        │
        ▼
4. Punctuation removal
        │
        ▼
5. Newline normalization
        │
        ▼
6. Number/alphanumeric removal
        │
        ▼
7. Stopword removal     (NLTK English stopwords)
        │
        ▼
8. Short word filtering (len ≤ 2)
        │
        ▼
TF-IDF Vectorization    (max_features=5000, ngram_range=(1,2))
        │
        ▼
ML Classifier → REAL NEWS / FAKE NEWS
```

---

## 📡 API Reference

**Base URL:** `https://fake-news-detection-using-nlp-and-ml.onrender.com`

---

### ✅ `GET /`

Health check and service status.

**Request**

```http
GET / HTTP/1.1
Host: fake-news-detection-using-nlp-and-ml.onrender.com
```

**Response** `200 OK`

```json
{
  "status": "online",
  "message": "Fake News Detection FastAPI Service is running.",
  "available_models": [
    "naive_bayes",
    "logistic_regression",
    "passive_aggressive",
    "decision_tree",
    "random_forest"
  ],
  "metrics_url": "/metrics"
}
```

**cURL Example**

```bash
curl https://fake-news-detection-using-nlp-and-ml.onrender.com/
```

---

### 📈 `GET /metrics`

Returns the evaluation metrics for all trained classifiers.

**Request**

```http
GET /metrics HTTP/1.1
Host: fake-news-detection-using-nlp-and-ml.onrender.com
```

**Response** `200 OK`

```json
{
  "metrics": {
    "naive_bayes": {
      "model_name": "Multinomial Naive Bayes",
      "accuracy": 0.94543,
      "precision": 0.93912,
      "recall": 0.94701,
      "f1_score": 0.94305
    },
    "logistic_regression": {
      "model_name": "Logistic Regression",
      "accuracy": 0.99087,
      "precision": 0.98702,
      "recall": 0.99393,
      "f1_score": 0.99046
    },
    "passive_aggressive": {
      "model_name": "Passive Aggressive Classifier",
      "accuracy": 0.99588,
      "precision": 0.9951,
      "recall": 0.99627,
      "f1_score": 0.99568
    },
    "decision_tree": {
      "model_name": "Decision Tree",
      "accuracy": 0.99488,
      "precision": 0.99279,
      "recall": 0.9965,
      "f1_score": 0.99464
    },
    "random_forest": {
      "model_name": "Random Forest",
      "accuracy": 0.99733,
      "precision": 0.99512,
      "recall": 0.9993,
      "f1_score": 0.9972
    }
  }
}
```

**cURL Example**

```bash
curl https://fake-news-detection-using-nlp-and-ml.onrender.com/metrics
```

---

### 🔮 `POST /predict`

Classifies a news article as **REAL** or **FAKE**.

**Request**

```http
POST /predict HTTP/1.1
Host: fake-news-detection-using-nlp-and-ml.onrender.com
Content-Type: application/json
```

**Request Body Schema**

| Field   | Type     | Required | Default               | Description                                        |
|---------|----------|----------|-----------------------|----------------------------------------------------|
| `title` | `string` | ✅ Yes   | —                     | The news article headline (min 3 chars)            |
| `text`  | `string` | ✅ Yes   | —                     | The full body text of the article (min 3 chars)    |
| `model` | `string` | ❌ No    | `logistic_regression` | Classifier to use (see available model keys below) |

**Available `model` values:**
- `logistic_regression` *(default)*
- `passive_aggressive`
- `decision_tree`
- `random_forest`
- `naive_bayes`

---

#### 🟢 Example: Real News Detection

**Request Body**

```json
{
  "title": "NASA announces successful Mars rover landing",
  "text": "NASA's Perseverance rover successfully landed on Mars on February 18, 2021. The rover touched down in the Jezero Crater and is now transmitting data back to scientists at JPL. This mission aims to search for signs of ancient microbial life and collect rock samples.",
  "model": "random_forest"
}
```

**cURL**

```bash
curl -X POST https://fake-news-detection-using-nlp-and-ml.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{
    "title": "NASA announces successful Mars rover landing",
    "text": "NASAs Perseverance rover successfully landed on Mars on February 18, 2021. The rover touched down in the Jezero Crater and is now transmitting data back to scientists at JPL.",
    "model": "random_forest"
  }'
```

**Response** `200 OK`

```json
{
  "prediction": "REAL NEWS",
  "label": 1,
  "confidence": 0.97842,
  "model_used": "Random Forest",
  "cleaned_text": "nasa announces successful mars rover landing perseverance rover successfully landed mars february rover touched jezero crater transmitting data scientists jpl mission aims search signs ancient microbial life collect rock samples"
}
```

---

#### 🔴 Example: Fake News Detection

**Request Body**

```json
{
  "title": "Scientists confirm the moon is made of cheese, NASA coverup exposed",
  "text": "Whistleblowers inside NASA have confirmed what conspiracy theorists have been saying for decades. Secret documents leaked online prove that the Apollo missions were faked and the government has been hiding the truth about lunar composition since 1969.",
  "model": "logistic_regression"
}
```

**cURL**

```bash
curl -X POST https://fake-news-detection-using-nlp-and-ml.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Scientists confirm the moon is made of cheese, NASA coverup exposed",
    "text": "Whistleblowers inside NASA have confirmed what conspiracy theorists have been saying for decades. Secret documents leaked online prove that the Apollo missions were faked.",
    "model": "logistic_regression"
  }'
```

**Response** `200 OK`

```json
{
  "prediction": "FAKE NEWS",
  "label": 0,
  "confidence": 0.96231,
  "model_used": "Logistic Regression",
  "cleaned_text": "scientists confirm moon made cheese nasa coverup exposed whistleblowers nasa confirmed conspiracy theorists saying decades secret documents leaked online prove apollo missions faked government hiding truth lunar composition"
}
```

---

#### 🔵 Example: Using Passive Aggressive Classifier

```bash
curl -X POST https://fake-news-detection-using-nlp-and-ml.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senate passes new infrastructure bill",
    "text": "The United States Senate passed the bipartisan Infrastructure Investment and Jobs Act with a vote of 69 to 30. The $1.2 trillion bill includes funding for roads, bridges, broadband internet, and clean energy.",
    "model": "passive_aggressive"
  }'
```

**Response** `200 OK`

```json
{
  "prediction": "REAL NEWS",
  "label": 1,
  "confidence": null,
  "model_used": "Passive Aggressive Classifier",
  "cleaned_text": "senate passes new infrastructure bill united states senate passed bipartisan infrastructure investment jobs act vote trillion bill includes funding roads bridges broadband internet clean energy"
}
```

> **Note:** `confidence` is `null` for `passive_aggressive` and `decision_tree` since these models do not support `predict_proba`.

---

**Response Body Schema**

| Field          | Type            | Description                                                      |
|----------------|-----------------|------------------------------------------------------------------|
| `prediction`   | `string`        | Classification result: `"REAL NEWS"` or `"FAKE NEWS"`           |
| `label`        | `integer`       | Numeric label: `1` = Real, `0` = Fake                           |
| `confidence`   | `float\|null`  | Max class probability (null if model does not support `predict_proba`) |
| `model_used`   | `string`        | Full display name of the classifier used                         |
| `cleaned_text` | `string`        | The preprocessed text that was fed to the model                  |

---

## ⚠️ Error Handling

**400 Bad Request — Invalid Model Key**

```json
{
  "detail": "'svm' not found. Available options: ['naive_bayes', 'logistic_regression', 'passive_aggressive', 'decision_tree', 'random_forest']"
}
```

**400 Bad Request — Empty Text After Preprocessing**

```json
{
  "detail": "Input text contains no valid words after preprocessing."
}
```

**422 Unprocessable Entity — Validation Error**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "title"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

**500 Internal Server Error**

```json
{
  "detail": "Internal server error: <error description>"
}
```

---

## 🛠️ Local Setup

### Prerequisites

- Python 3.10+ (Python 3.13 recommended)
- `pip` package manager
- Dataset files: `dataset/True.csv` and `dataset/Fake.csv`

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Fake-News-Detection-using-NLP.git
cd Fake-News-Detection-using-NLP
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Train the Model

> Skip this step if `models/pretrained_model_01.pkl` already exists.

```bash
python train.py
```

Expected output:

```
Training models...
Saving trained models...
Training completed successfully.
Model saved as model.pkl
```

### 5. Run the API Server

```bash
uvicorn app:app --host 127.0.0.1 --port 10000 --reload
```

The API will be available at:

| Page        | URL                              |
|-------------|----------------------------------|
| API Root    | http://127.0.0.1:10000/          |
| Swagger UI  | http://127.0.0.1:10000/docs      |
| ReDoc       | http://127.0.0.1:10000/redoc     |
| Metrics     | http://127.0.0.1:10000/metrics   |

---

## 🐳 Docker Setup

### Build the Image

```bash
docker build -t fake-news-detection .
```

### Run the Container

```bash
docker run -p 10000:10000 fake-news-detection
```

### Run with Custom Port

```bash
docker run -e PORT=8080 -p 8080:8080 fake-news-detection
```

### Docker Details

| Property     | Value                |
|--------------|----------------------|
| Base Image   | `python:3.13-slim`   |
| Working Dir  | `/app`               |
| Exposed Port | `10000`              |
| Runs as      | Non-root (`appuser`) |
| Port Override| `$PORT` env variable |

---

## 📦 Dataset

The model is trained on the [Fake and Real News Dataset](https://www.kaggle.com/clmentbisaillon/fake-and-real-news-dataset) from Kaggle.

| File       | Content             | Size    | Label |
|------------|---------------------|---------|-------|
| `True.csv` | Real news articles  | ~53 MB  | `1`   |
| `Fake.csv` | Fake news articles  | ~62 MB  | `0`   |

> The dataset is **not included** in this repository due to size. Download it from Kaggle and place both CSV files in the `dataset/` directory before training.

**Columns used:** `title`, `text`

---

## 🧰 Tech Stack

| Layer                | Technology                           |
|----------------------|--------------------------------------|
| Language             | Python 3.13                          |
| Web Framework        | FastAPI                              |
| ASGI Server          | Uvicorn                              |
| ML Library           | scikit-learn                         |
| NLP                  | NLTK (stopwords), TF-IDF Vectorizer  |
| Data Processing      | pandas, NumPy                        |
| Model Serialization  | joblib                               |
| Containerization     | Docker                               |
| Hosting              | Render                               |
| API Docs             | Swagger UI, ReDoc (FastAPI built-in) |

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

Made with ❤️ using Python, FastAPI, and scikit-learn

**⭐ Star this repo if you found it useful!**

</div>
