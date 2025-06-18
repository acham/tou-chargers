FROM python:3.11.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y graphviz

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY app app

EXPOSE 8000

CMD ["uvicorn", "app.main:fast_app", "--host", "0.0.0.0", "--port", "8000"]
