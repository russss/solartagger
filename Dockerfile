FROM python:3.8
RUN pip install poetry
WORKDIR /app
COPY . .
RUN poetry install

ENTRYPOINT ["poetry", "run", "uvicorn", "main:app"]
