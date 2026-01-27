import pandas as pd
from sqlalchemy import create_engine, text

# Database URL from .env
DATABASE_URL = "mysql+pymysql://root:MYSQLrootpass555@localhost:3306/chatbot"

def check_dates():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Get sample dates
            print("\n--- Sample Dates ---")
            query = text("SELECT date FROM footwear_3_month_salesin_1 LIMIT 10")
            result = conn.execute(query)
            for row in result:
                print(f"'{row[0]}'")
                
            # Check min and max date
            print("\n--- Date Range ---")
            # We treat them as strings first to see what MIN/MAX text gives, 
            # or try to cast if we knew the format. Let's just grab string min/max for now
            # effectively finding earliest/latest if format starts with Year. 
            # If format is MM/DD/YYYY, string sort is useless for range but shows us format.
            query = text("SELECT MIN(date), MAX(date) FROM footwear_3_month_salesin_1")
            result = conn.execute(query).fetchone()
            print(f"Min (Lexicographical): {result[0]}")
            print(f"Max (Lexicographical): {result[1]}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_dates()
