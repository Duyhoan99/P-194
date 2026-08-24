import os
import sqlite3
import pandas as pd
from pathlib import Path

def setup_mimic_demo_db():
    # Use relative paths for portability, but we're running from P-194
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "mimic-iv-clinical-database-demo-2.2"
    db_path = base_dir / "mimic_demo.db"
    
    if not data_dir.exists():
        print(f"Error: Data directory not found at {data_dir}")
        return
        
    print(f"Creating database at {db_path}")
    conn = sqlite3.connect(db_path)
    
    # Process both hosp and icu directories
    for module in ['hosp', 'icu']:
        module_dir = data_dir / module
        if not module_dir.exists():
            print(f"Warning: Module directory not found at {module_dir}")
            continue
            
        print(f"Processing module: {module}")
        for csv_file in module_dir.glob("*.csv"):
            table_name = csv_file.stem
            print(f"  -> Loading {csv_file.name} into table '{table_name}'...")
            
            try:
                # Read in chunks to handle potentially large files gracefully
                chunksize = 100000
                first_chunk = True
                for chunk in pd.read_csv(csv_file, chunksize=chunksize, low_memory=False):
                    if first_chunk:
                        chunk.to_sql(table_name, conn, if_exists='replace', index=False)
                        first_chunk = False
                    else:
                        chunk.to_sql(table_name, conn, if_exists='append', index=False)
                print(f"     Successfully loaded {table_name}.")
            except Exception as e:
                print(f"     Error loading {csv_file.name}: {e}")

    conn.close()
    print("Database setup complete. You can now connect to mimic_demo.db")

if __name__ == "__main__":
    setup_mimic_demo_db()
