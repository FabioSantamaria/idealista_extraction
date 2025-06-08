import sqlite3
import pandas as pd
import json
from typing import Dict, Any

DATABASE_NAME = "property_data.db"

def create_connection():
    """Create a database connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def init_database():
    """Initialize the database with the properties table."""
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Create properties table with flexible schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS properties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    processed_date TEXT,
                    extraction_method TEXT,
                    data_json TEXT,
                    source_url TEXT,
                    price TEXT,
                    location TEXT,
                    property_type TEXT,
                    rooms TEXT,
                    bathrooms TEXT,
                    size_built_sqm TEXT,
                    size_useful_sqm TEXT
                )
            ''')
            
            conn.commit()
            print("Database initialized successfully.")
            
        except sqlite3.Error as e:
            print(f"Error initializing database: {e}")
        finally:
            conn.close()

def insert_property_data(property_data: Dict[str, Any]):
    """Insert property data into the database."""
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Convert the entire data dict to JSON for flexible storage
            data_json = json.dumps(property_data)
            
            # Extract common fields for easier querying
            filename = property_data.get('filename', '')
            processed_date = property_data.get('processed_date', '')
            extraction_method = property_data.get('extraction_method', '')
            source_url = property_data.get('source_url', '')
            price = property_data.get('price', property_data.get('ad_info_price', ''))
            location = property_data.get('location', property_data.get('ad_info_location', ''))
            property_type = property_data.get('property_type', property_data.get('ad_info_typology', ''))
            rooms = property_data.get('rooms', '')
            bathrooms = property_data.get('bathrooms', '')
            size_built_sqm = property_data.get('size_built_sqm', '')
            size_useful_sqm = property_data.get('size_useful_sqm', '')
            
            cursor.execute('''
                INSERT INTO properties (
                    filename, processed_date, extraction_method, data_json,
                    source_url, price, location, property_type, rooms,
                    bathrooms, size_built_sqm, size_useful_sqm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                filename, processed_date, extraction_method, data_json,
                source_url, price, location, property_type, rooms,
                bathrooms, size_built_sqm, size_useful_sqm
            ))
            
            conn.commit()
            print(f"Property data inserted successfully for {filename}.")
            
        except sqlite3.Error as e:
            print(f"Error inserting property data: {e}")
        finally:
            conn.close()

def get_all_properties() -> pd.DataFrame:
    """Retrieve all property data from the database as a pandas DataFrame."""
    conn = create_connection()
    if conn is not None:
        try:
            # Get all data and expand JSON fields
            df = pd.read_sql_query("SELECT * FROM properties", conn)
            
            if not df.empty:
                # Expand JSON data into separate columns
                expanded_data = []
                for _, row in df.iterrows():
                    try:
                        json_data = json.loads(row['data_json'])
                        # Combine basic info with expanded JSON data
                        combined_data = {
                            'id': row['id'],
                            'filename': row['filename'],
                            'processed_date': row['processed_date'],
                            'extraction_method': row['extraction_method']
                        }
                        combined_data.update(json_data)
                        expanded_data.append(combined_data)
                    except json.JSONDecodeError:
                        # If JSON parsing fails, use basic data
                        expanded_data.append(row.to_dict())
                
                df = pd.DataFrame(expanded_data)
            
            return df
            
        except sqlite3.Error as e:
            print(f"Error retrieving property data: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    else:
        return pd.DataFrame()