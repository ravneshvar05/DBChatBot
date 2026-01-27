import os
import pandas as pd
from sqlalchemy import create_engine, text

# Database URL from .env
DATABASE_URL = "mysql+pymysql://root:MYSQLrootpass555@localhost:3306/chatbot"

def check_subcategories():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Check distinct sub_categories
            query = text("SELECT DISTINCT sub_category FROM footwear_productsin_1 ORDER BY sub_category")
            result = conn.execute(query)
            values = [row[0] for row in result]
            
            print(f"\n--- Distinct Sub-Categories ({len(values)}) ---")
            for v in values:
                print(f"'{v}'")
                
            # Check row count
            count = conn.execute(text("SELECT COUNT(*) FROM footwear_productsin_1")).scalar()
            print(f"\nTotal Rows: {count}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_subcategories()
