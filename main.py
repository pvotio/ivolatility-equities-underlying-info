import os
import sys
import struct
import logging
import datetime
import pyodbc
import pandas as pd

from azure.identity import DefaultAzureCredential
from sqlalchemy import create_engine
from urllib.parse import quote_plus

import ivolatility as ivol

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pyodbc_attrs(access_token: str) -> dict:
    """
    Format the Azure AD access token for pyodbc's SQL_COPT_SS_ACCESS_TOKEN.
    """
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    enc_token = access_token.encode('utf-16-le')
    token_struct = struct.pack('=i', len(enc_token)) + enc_token
    return {SQL_COPT_SS_ACCESS_TOKEN: token_struct}

def main():
    # 1) Load environment variables
    api_key     = os.getenv("IVOL_API_KEY", "")
    load_date   = os.getenv("LOAD_DATE", "")  # e.g. "2021-12-24"
    db_server   = os.getenv("DB_SERVER", "")
    db_name     = os.getenv("DB_NAME", "")
    table_name  = os.getenv("TARGET_TABLE")

    if not api_key:
        logging.error("IVOL_API_KEY is not set. Exiting.")
        sys.exit(1)

    # Default LOAD_DATE to “yesterday” if not provided
    if not load_date:
        load_date = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    if not db_server or not db_name:
        logging.error("DB_SERVER or DB_NAME not set. Exiting.")
        sys.exit(1)

    if not table_name:
        logging.error("TARGET_TABLE not set. Exiting.")
        sys.exit(1)

    logging.info(f"Using LOAD_DATE={load_date}, inserting into table={table_name}")

    # 2) Configure iVolatility API
    try:
        ivol.setLoginParams(apiKey=api_key)
        getMarketData = ivol.setMethod('/equities/underlying-info')
    except Exception as e:
        logging.error(f"Failed to configure iVol API: {e}")
        sys.exit(1)

    # 3) Fetch data
    try:
        logging.info(f"Fetching data from iVol for date={load_date}...")
        marketData = getMarketData(date=load_date)  # returns a pandas DataFrame
    except Exception as e:
        logging.error(f"Error fetching data from iVol: {e}")
        sys.exit(1)

    if marketData.empty:
        logging.warning("No data returned. Exiting with no insert.")
        return

    logging.info(f"Fetched {len(marketData)} rows from iVol.")

    # 4) Get Azure AD token for SQL
    logging.info("Obtaining Azure AD token using DefaultAzureCredential...")
    try:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        token_obj = credential.get_token("https://database.windows.net/.default")
        access_token = token_obj.token
        logging.info("Successfully obtained access token for Azure SQL.")
    except Exception as ex:
        logging.error(f"Failed to obtain SQL access token: {ex}")
        sys.exit(1)

    attrs = get_pyodbc_attrs(access_token)
    odbc_conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={db_server};"
        f"DATABASE={db_name};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )

    # 5) Build the SQLAlchemy engine
    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_conn_str)}",
        connect_args={'attrs_before': attrs}
    )

    # 6) Delete old rows for this date
    #
    #   Adjust "[Start date]" to match your actual column name(s).
    #
    delete_sql = f"DELETE FROM {table_name} WHERE [Start date] = ?"
    logging.info(f"Deleting existing rows for date={load_date} in {table_name}...")

    try:
        with pyodbc.connect(odbc_conn_str, attrs_before=attrs) as conn:
            cur = conn.cursor()
            cur.execute(delete_sql, [load_date])
            conn.commit()
        logging.info(f"Deleted old rows for date={load_date} in {table_name}.")
    except Exception as ex:
        logging.error(f"Error deleting old rows: {ex}")
        sys.exit(1)

    # 7) Insert new data
    try:
        # Ensure the DataFrame has the "Start date" column
        if "Start date" not in marketData.columns:
            marketData["Start date"] = load_date

        # Use if_exists="fail" to ensure we do NOT create the table
        # If the table doesn't exist, or columns don't match, this will raise an error
        marketData.to_sql(
            name=table_name,  # If table_name includes schema, e.g. "etl.ivolatility_underlying_info", it might be best to pass schema=... instead
            con=engine,
            if_exists='fail',  # never create a table, fail if missing
            index=False
        )
        logging.info(f"Inserted {len(marketData)} rows into {table_name}.")
    except Exception as e:
        logging.error(f"Error inserting data into {table_name}: {e}")
        sys.exit(1)

    logging.info("ETL job completed successfully.")

if __name__ == "__main__":
    main()
