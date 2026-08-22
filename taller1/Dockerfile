FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY modelo1/random_forest.pkl modelo1/random_forest.pkl
COPY ["modelo 2/penguin_gmm.pkl", "modelo 2/penguin_gmm.pkl"]

EXPOSE 8989

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8989"]
