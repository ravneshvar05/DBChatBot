
import sys
import os
import traceback
import logging

# Add project root to path
sys.path.append(os.getcwd())

# Configure logging to stdout
logging.basicConfig(level=logging.DEBUG)

def test_sql_service_fail():
    print("--- Diagnostic: Testing SQL Service ---")
    
    try:
        from src.services.sql_service import get_sql_service
        
        print("Initializing Service...")
        service = get_sql_service()
        
        print("Running Query...")
        # Simulating the exact failure case
        response = service.query(
            question="give me the best running shoes", 
            session_id=None
        )
        
        print(f"Result Success: {response.success}")
        if not response.success:
            print(f"Result Error: {response.error}")
            print(f"Result Answer: {response.answer}")
            
    except Exception:
        print("\n❌ CRITICAL EXCEPTION CAUGHT:")
        traceback.print_exc()

if __name__ == "__main__":
    test_sql_service_fail()
