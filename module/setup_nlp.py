"""Download the required corpus into the project, preserving NLTK path validation."""
from pathlib import Path
import nltk

def main():
    destination = Path(__file__).resolve().parents[1] / 'nltk_data'
    destination.mkdir(exist_ok=True)
    nltk.data.path.insert(0, str(destination))
    if not nltk.download('stopwords', download_dir=str(destination), raise_on_error=True):
        raise RuntimeError('Could not install NLTK stopwords')

if __name__ == '__main__':
    main()
