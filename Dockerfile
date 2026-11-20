FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m compileall -q app.py && python -c "import requests, bs4, flask; print('deps ok')"
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["sh", "-c", "exec gunicorn -b 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120 app:app"]
