import os
import sys
import struct
import logging
import datetime
import pyodbc
import pandas as pd

from azure.identity import DefaultAzureCredential
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
    load_date   = os.getenv("LOAD_DATE", "")  # e.g., "2021-12-24"
    db_server   = os.getenv("DB_SERVER", "")
    db_name     = os.getenv("DB_NAME", "")
    table_name  = os.getenv("TARGET_TABLE", "ivolatility_underlying_info")

    if not api_key:
        logging.error("IVOL_API_KEY is not set. Exiting.")
        sys.exit(1)

    # Default LOAD_DATE to “yesterday” if not provided
    if not load_date:
        load_date = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    if not db_server or not db_name:
        logging.error("DB_SERVER or DB_NAME not set. Exiting.")
        sys.exit(1)

    logging.info(f"Using LOAD_DATE={load_date}, inserting into table={table_name}")

    # 2) Configure iVolatility API
    try:
        ivol.setLoginParams(apiKey=api_key)
        getMarketData = ivol.setMethod('/equities/underlying-info')
    except Exception as e:
        logging.error(f"Failed to configure iVol API: {e}")
        sys.exit(1)

    # 3) Fetch data from iVolatility
    try:
        logging.info(f"Fetching data from iVol for date={load_date}...")
        marketData = getMarketData(date=load_date)  # returns a Pandas DataFrame
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

    # 5) Delete old rows for this date
    delete_sql = f"DELETE FROM {table_name} WHERE [Start_date] = ?"
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

    # 6) Prepare to insert data in chunks with pyodbc.executemany
    #    We'll rename spaced columns -> underscore columns (if iVol returns them),
    #    then generate a unique integer 'StockID' if missing.

    # Example rename map (if iVol returns columns with spaces):
    rename_map = {
        "Stock ticker": "Stock_ticker",
        "Company name": "Company_name",
        "Exchange MIC": "Exchange_MIC",
        "Exchange name": "Exchange_name",
        "Start date": "Start_date",
        "End date": "End_date",
        "Security type": "Security_type",
        "Opt exchange MIC": "Opt_exchange_MIC",
        "Opt exchange name": "Opt_exchange_name",
        "Start opt date": "Start_opt_date",
        "End opt date": "End_opt_date",
        "Dividend Convention": "Dividend_Convention",
        "BLMB ticker": "BLMB_ticker"
    }
    marketData.rename(columns=rename_map, inplace=True)

    # Ensure these columns exist (create them with None if not present)
    needed_cols = [
        "Status",
        "Stock_ticker",
        "Company_name",
        "Exchange_MIC",
        "Exchange_name",
        "Start_date",
        "End_date",
        "Region",
        "Security_type",
        "ISIN",
        "CUSIP",
        "SEDOL",
        "FIGI",
        "Options",
        "Opt_exchange_MIC",
        "Opt_exchange_name",
        "Start_opt_date",
        "End_opt_date",
        "Dividend_Convention",
        "StockID",
        "BLMB_ticker"
    ]
    for col in needed_cols:
        if col not in marketData.columns:
            marketData[col] = None

    # Because StockID is NOT NULL + PK, we must supply a unique int if the data doesn't have it
    if marketData["StockID"].isnull().any():
        # Example: generate a simple sequence 1..N (for demonstration):
        #   If you do multiple runs, you risk PK conflicts. A real system might prefer:
        #     - a random or a hashed UUID -> int
        #     - or store previously used max ID in a separate table
        # Or better yet, make [StockID] an IDENTITY in SQL. But for a quick fix:
        marketData["StockID"] = range(1, len(marketData) + 1)

    # If there's any leftover columns in the DataFrame not in needed_cols, drop them
    leftover_cols = set(marketData.columns) - set(needed_cols)
    if leftover_cols:
        logging.info(f"Dropping leftover columns: {leftover_cols}")
        marketData.drop(columns=list(leftover_cols), inplace=True)

    # Debug: confirm final columns
    logging.info(f"Final columns for insertion: {list(marketData.columns)}")

    # Insert statement: 21 columns in the exact order we want:
    insert_sql = f"""
    INSERT INTO {table_name} (
        [Status],
        [Stock_ticker],
        [Company_name],
        [Exchange_MIC],
        [Exchange_name],
        [Start_date],
        [End_date],
        [Region],
        [Security_type],
        [ISIN],
        [CUSIP],
        [SEDOL],
        [FIGI],
        [Options],
        [Opt_exchange_MIC],
        [Opt_exchange_name],
        [Start_opt_date],
        [End_opt_date],
        [Dividend_Convention],
        [StockID],
        [BLMB_ticker]
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    chunk_size = 5000
    total_inserted = 0

    # Insert in chunks
    for start_idx in range(0, len(marketData), chunk_size):
        subset = marketData.iloc[start_idx:start_idx+chunk_size]

        # Build list-of-tuples with columns in the exact same order as insert_sql
        data_tuples = list(
            subset[needed_cols].itertuples(index=False, name=None)
        )

        try:
            with pyodbc.connect(odbc_conn_str, attrs_before=attrs) as conn:
                cursor = conn.cursor()
                cursor.fast_executemany = True
                cursor.executemany(insert_sql, data_tuples)
                conn.commit()
            total_inserted += len(data_tuples)
        except Exception as e:
            logging.error(f"Error inserting chunk: {e}")
            sys.exit(1)

    logging.info(f"Inserted {total_inserted} total rows into {table_name}.")
    logging.info("ETL job completed successfully.")

if __name__ == "__main__":
    main()


