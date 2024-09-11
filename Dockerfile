FROM python:3.11-slim AS builder
COPY ./requirements.txt /home
RUN pip install -r /home/requirements.txt

FROM python:3.11-slim
EXPOSE 8000
RUN mkdir /app
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY ./app /app
ENTRYPOINT ["python", "-u", "/app/main.py"]
