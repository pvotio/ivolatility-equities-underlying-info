# ivolatility-equities-underlying-info

This repository contains a Python-based ETL job for retrieving **iVolatility** equities/underlying information via their API and loading it into an **Azure SQL** database. It supports authentication via **Azure Managed Identity** and can be containerized for deployment in **Kubernetes** or other Docker-based environments.

Repository: [pvotio/ivolatility-equities-underlying-info](https://github.com/pvotio/ivolatility-equities-underlying-info)

---

## Table of Contents

1. [Overview](#overview)  
2. [Features](#features)  
3. [Prerequisites](#prerequisites)  
4. [Project Structure](#project-structure)  
5. [Setup & Usage](#setup--usage)  
   - [Local Testing](#local-testing)  
   - [Docker Build & Run](#docker-build--run)  
   - [Kubernetes CronJob](#kubernetes-cronjob)  
6. [Environment Variables](#environment-variables)  
7. [Contributing](#contributing)  
8. [License](#license)  

---

## Overview

This ETL script performs the following tasks:

1. Connects to the **iVolatility** API endpoint `"/equities/underlying-info"` using an API key.  
2. Fetches market data for a specified date (defaulting to “yesterday”).  
3. Uses **Managed Identity** via `DefaultAzureCredential` to securely connect to an **Azure SQL** database.  
4. Deletes old rows for the specified date in a target table.  
5. Inserts the new data returned by the iVolatility API.

You can run this script locally, in Docker, or schedule it in **AKS** using a Kubernetes **CronJob**.

---

## Features

- **Secure Azure SQL Auth**: Utilizes Azure AD tokens (managed identity).  
- **Deletes & Re-Inserts**: Ensures clean data for the specified date.  
- **Docker & K8s Ready**: Container-friendly design for easy deployment.  
- **Date Flexibility**: Defaults to “yesterday” if no date is supplied.

---

## Prerequisites

- **Python 3.9+** (if running locally)  
- **Azure SQL Database** with identity configured:
  ```sql
  CREATE USER [YourAksManagedIdentityName] FROM EXTERNAL PROVIDER;
  ALTER ROLE db_datareader ADD MEMBER [YourAksManagedIdentityName];
  ALTER ROLE db_datawriter ADD MEMBER [YourAksManagedIdentityName];
  ```
- Docker (for containerized deployments)  
- An iVolatility account & API key  
- (Optional) Azure CLI or AKS setup for managed identity support

---

## Project Structure

```
ivolatility-equities-underlying-info/
├── etl_ivol.py         # Main Python script (ETL logic)
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build configuration
├── README.md           # Project documentation
└── .gitignore          # (Optional) Git ignore patterns
```

---

## Setup & Usage

### Local Testing

1. Clone the repository:
   ```bash
   git clone https://github.com/pvotio/ivolatility-equities-underlying-info.git
   cd ivolatility-equities-underlying-info
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables and run:
   ```bash
   export IVOL_API_KEY="YOUR_IVOL_API_KEY"
   export DB_SERVER="your-sql-server.database.windows.net"
   export DB_NAME="YourDatabase"
   export TARGET_TABLE="etl.ivolatility_underlying_info"
   # Optional:
   # export LOAD_DATE="2025-03-20"

   python etl_ivol.py
   ```

---

### Docker Build & Run

1. Build the Docker image:
   ```bash
   docker build -t ivol-etl:latest .
   ```

2. Run the container:
   ```bash
   docker run --rm      -e IVOL_API_KEY="YOUR_IVOL_API_KEY"      -e DB_SERVER="your-sql-server.database.windows.net"      -e DB_NAME="YourDatabase"      -e TARGET_TABLE="etl.ivolatility_underlying_info"      ivol-etl:latest
   ```

> Tip: If using Azure with Managed Identity, ensure your environment supports `DefaultAzureCredential`.

---

### Kubernetes CronJob

An example CronJob to run daily at 5 AM UTC:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ivol-etl-job
spec:
  schedule: "0 5 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: ivol-etl
              image: <your-registry>/ivol-etl:latest
              env:
                - name: IVOL_API_KEY
                  valueFrom:
                    secretKeyRef:
                      name: ivol-secret
                      key: IVOL_API_KEY
                - name: DB_SERVER
                  value: "your-sql-server.database.windows.net"
                - name: DB_NAME
                  value: "YourDatabase"
                - name: TARGET_TABLE
                  value: "etl.ivolatility_underlying_info"
                # - name: LOAD_DATE
                #   value: "2025-03-20"
```

> ✅ **Note**: Use a Kubernetes Secret (e.g. `ivol-secret`) to store your API key securely.

---

## Environment Variables

| Variable       | Description                                                    | Required | Default                          |
|----------------|----------------------------------------------------------------|----------|----------------------------------|
| `IVOL_API_KEY` | Your iVolatility API key.                                      | Yes      | —                                |
| `DB_SERVER`    | Azure SQL server hostname (e.g., `myserver.database.windows.net`). | Yes  | —                                |
| `DB_NAME`      | Target database name.                                          | Yes      | —                                |
| `TARGET_TABLE` | Target table name.                                             | No       | `etl.ivolatility_underlying_info` |
| `LOAD_DATE`    | Date to fetch (format `YYYY-MM-DD`). Defaults to yesterday.   | No       | Yesterday (UTC)                  |

---

## Contributing

Contributions are welcome!

1. Fork the repo and create a feature branch.  
2. Make your changes, write tests if needed.  
3. Submit a pull request with a clear description.

By contributing, you agree to abide by the project's **Contributor Code of Conduct**.

---

## License

**Apache License 2.0**

```
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at:

   http://www.apache.org/licenses/LICENSE-2.0
```

---

**© 2025 pvotio**
