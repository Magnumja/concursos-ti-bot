FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY concursos_ti concursos_ti
RUN useradd --create-home bot && mkdir data && chown bot data
USER bot
VOLUME /app/data
CMD ["python", "-m", "concursos_ti", "run"]
