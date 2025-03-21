ivolatility-equities-underlying-info

This repository contains a Python-based ETL job for retrieving iVolatility equities/underlying information via their API and loading it into an Azure SQL database. It supports authentication via Azure Managed Identity and can be containerized for deployment in Kubernetes or other Docker-based environments.

Repository: pvotio/ivolatility-equities-underlying-info

Table of Contents

Overview
Features
Prerequisites
Project Structure
Setup & Usage
Local Testing
Docker Build & Run
Kubernetes CronJob
Environment Variables
Contributing
License
Overview

This ETL script:

Connects to the iVolatility API endpoint "/equities/underlying-info" using an API key.
Fetches market data for a specified date (defaulting to “yesterday”).
Uses Managed Identity via DefaultAzureCredential to connect securely to an Azure SQL database (i.e., no password stored in code).
Deletes old rows for the specified date in a target table.
Inserts the new data returned by the iVolatility API.
You can run this script locally, in Docker, or schedule it in AKS using a Kubernetes CronJob.

Features

Secure Azure SQL Auth: Uses Azure AD tokens (managed identity).
Retries: Basic fetch logic (you can expand with advanced retry/backoff if needed).
Date Flexibility: Defaults to “yesterday” if no date is supplied.
Deletes & Re-Inserts: Ensures clean data for the specified date.
Docker & K8s Ready: Container-friendly design for easy deployment.
Prerequisites

Python 3.9+ (if running locally without Docker).
Azure SQL Database with an identity configured and user created for that identity:
CREATE USER [YourAksManagedIdentityName] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [YourAksManagedIdentityName];
ALTER ROLE db_datawriter ADD MEMBER [YourAksManagedIdentityName];
Docker (if containerizing the application).
iVolatility account & API key.
(Optional) Azure CLI or AKS for managed identity usage and container orchestration.
Project Structure

ivolatility-equities-underlying-info/
├── etl_ivol.py         # Main Python script (ETL logic)
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build configuration
├── README.md           # Project documentation (this file)
└── .gitignore          # (Optional) Git ignore patterns
Setup & Usage

Local Testing
Clone the repository:
git clone https://github.com/pvotio/ivolatility-equities-underlying-info.git
cd ivolatility-equities-underlying-info
Install dependencies (assuming you have Python 3.9+ and pip):
pip install -r requirements.txt
Set environment variables and run:
export IVOL_API_KEY="YOUR_IVOL_API_KEY"
export DB_SERVER="your-sql-server.database.windows.net"
export DB_NAME="YourDatabase"
export TARGET_TABLE="etl.ivolatility_underlying_info"
# Optional:
# export LOAD_DATE="2025-03-20"

python etl_ivol.py
The script fetches data for the given date (default: yesterday), connects to Azure SQL via managed identity (or other credentials if properly configured), deletes old rows, and inserts new rows.
Docker Build & Run
Build the Docker image:
docker build -t ivol-etl:latest .
Run the container, passing environment variables:
docker run --rm \
  -e IVOL_API_KEY="YOUR_IVOL_API_KEY" \
  -e DB_SERVER="your-sql-server.database.windows.net" \
  -e DB_NAME="YourDatabase" \
  -e TARGET_TABLE="etl.ivolatility_underlying_info" \
  ivol-etl:latest
If running in Azure with managed identity, ensure your environment supports DefaultAzureCredential.
Locally, you may rely on tools like az login or set a user/password approach (not included here by default).
Kubernetes CronJob
You can schedule this ETL job to run daily in AKS with a CronJob. An example YAML:

apiVersion: batch/v1
kind: CronJob
metadata:
  name: ivol-etl-job
spec:
  schedule: "0 5 * * *"  # 5 AM UTC
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
                #   value: "2025-03-20"   # If you want to set a static date
Managed Identity Setup: Ensure your AKS node (system-assigned) or Pod (user-assigned) identity is configured and added as a user in your Azure SQL DB.
Secrets: Store your iVolatility API key in a K8S Secret (e.g., ivol-secret) rather than putting it directly in the YAML.
Environment Variables

Variable	Description	Required	Default
IVOL_API_KEY	Your iVolatility API key.	Yes	—
DB_SERVER	Hostname of your Azure SQL server (e.g., myserver.database.windows.net).	Yes	—
DB_NAME	Name of the database (e.g. MyDatabase).	Yes	—
TARGET_TABLE	Target table name (default etl.ivolatility_underlying_info).	No	etl.ivolatility_underlying_info
LOAD_DATE	Date to fetch (format YYYY-MM-DD). If not provided, defaults to “yesterday” (UTC).	No	“yesterday”
Contributing

Contributions are welcome! To contribute:

Fork the repository and create a new branch for your feature or bugfix.
Make changes, write tests if applicable, and ensure the code passes.
Submit a pull request with a clear description of your changes.
Please note that this project is released with a Contributor Code of Conduct. By participating in this project, you agree to abide by its terms.

License

Apache License 2.0

Copyright 2023 pvotio

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at 

   http://www.apache.org/licenses/LICENSE-2.0 

Unless required by applicable law or agreed to in writing, software 
distributed under the License is distributed on an "AS IS" BASIS, 
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
See the License for the specific language governing permissions and 
limitations under the License.
