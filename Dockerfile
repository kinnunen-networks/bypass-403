FROM python:3.10-alpine

WORKDIR /app

# Install Go for httpx
RUN apk add --no-cache go

COPY requirements.txt /app/requirements.txt

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install httpx
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

COPY src/ ./src/
COPY fuzz-data/ ./fuzz-data/

ENTRYPOINT ["python", "-m", "src.main"]
CMD ["python", "-m", "src.main"]