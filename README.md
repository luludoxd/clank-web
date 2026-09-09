# CLANk Web

A web version of the CLANk YouTube bot detector.

## Run locally

1. Install Python 3.11+.
2. In this folder run:
   `pip install -r requirements.txt`
3. Run:
   `python app.py`
4. Open `http://127.0.0.1:5000`

The YouTube API key is supplied with each analysis request and is not stored by this app.

## Deploy

This project is designed for a Python web host that can run Flask/Gunicorn.
