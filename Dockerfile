FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BOUNTY_DATA_DIR=/data
WORKDIR /app
COPY requirements*.txt ./
COPY wheels/ /wheels/
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements-cloud.txt && rm -rf /wheels
COPY app.py run.py manage.py wsgi.py ./
COPY bounty/ ./bounty/
COPY templates/ ./templates/
COPY static/ ./static/
COPY database/ ./database/
USER 10001:10001
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--preload", "--worker-tmp-dir", "/tmp", "--access-logfile", "-", "--error-logfile", "-", "wsgi:create_cloud_app()"]
