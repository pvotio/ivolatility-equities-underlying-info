# Start from a small Python base image
FROM python:3.13.2-slim-bullseye

# 1) Install system dependencies (curl, gnupg) + Microsoft ODBC driver
RUN apt-get update && apt-get install -y \
    curl apt-transport-https gnupg && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list \
        > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y \
    msodbcsql18 \
    unixodbc-dev \
    && apt-get clean

# 2) Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Copy the ETL script
COPY main.py .

# 4) Default command
ENTRYPOINT ["python", "main.py"]
