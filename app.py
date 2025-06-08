import streamlit as st
import pandas as pd
import sqlite3
import json
import csv
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from datetime import datetime
import io

# Import the extraction functions
from html_processor import extract_full_property_info_css_selector, flatten_property_info, extract_detailed_property_features
from database import init_database, insert_property_data, get_all_properties, create_connection

def main():
    st.set_page_config(
        page_title="Property HTML Data Extractor",
        page_icon="🏠",
        layout="wide"
    )
    
    st.title("🏠 Property HTML Data Extractor")
    st.markdown("Upload HTML files to extract property information and store it in a database.")
    
    # Initialize database
    init_database()
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page", ["Upload & Process", "View Data", "Download Data"])
    
    if page == "Upload & Process":
        upload_and_process_page()
    elif page == "View Data":
        view_data_page()
    elif page == "Download Data":
        download_data_page()

def upload_and_process_page():
    st.header("📁 Upload and Process HTML Files")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose HTML files", 
        type=['html', 'htm'], 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.success(f"Uploaded {len(uploaded_files)} file(s)")
        
        # Processing options
        st.subheader("Processing Options")
        extraction_method = st.radio(
            "Choose extraction method:",
            ["Full Property Info (CSS Selector)", "Detailed Property Features"]
        )
        
        if st.button("Process Files", type="primary"):
            process_files(uploaded_files, extraction_method)

def process_files(uploaded_files, extraction_method):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_count = 0
    total_files = len(uploaded_files)
    
    for i, uploaded_file in enumerate(uploaded_files):
        status_text.text(f"Processing {uploaded_file.name}...")
        
        try:
            # Read HTML content
            html_content = uploaded_file.read().decode('utf-8')
            
            # Extract data based on selected method
            if extraction_method == "Full Property Info (CSS Selector)":
                property_data = extract_full_property_info_css_selector(html_content)
                flattened_data = flatten_property_info(property_data)
            else:
                flattened_data = extract_detailed_property_features(html_content)
            
            # Add metadata
            flattened_data['filename'] = uploaded_file.name
            flattened_data['processed_date'] = datetime.now().isoformat()
            flattened_data['extraction_method'] = extraction_method
            
            # Insert into database
            insert_property_data(flattened_data)
            processed_count += 1
            
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        
        # Update progress
        progress_bar.progress((i + 1) / total_files)
    
    status_text.text(f"Processing complete! Successfully processed {processed_count}/{total_files} files.")
    st.success(f"✅ Successfully processed {processed_count} files and stored them in the database.")

def view_data_page():
    st.header("📊 View Stored Data")
    
    # Get data from database
    df = get_all_properties()
    
    if df.empty:
        st.info("No data found in the database. Please upload and process some HTML files first.")
        return
    
    st.subheader(f"Total Records: {len(df)}")
    
    # Display filters
    col1, col2 = st.columns(2)
    
    with col1:
        if 'extraction_method' in df.columns:
            method_filter = st.selectbox(
                "Filter by extraction method:",
                ['All'] + list(df['extraction_method'].unique())
            )
            if method_filter != 'All':
                df = df[df['extraction_method'] == method_filter]
    
    with col2:
        if 'ad_info_location' in df.columns or 'location' in df.columns:
            location_col = 'ad_info_location' if 'ad_info_location' in df.columns else 'location'
            locations = df[location_col].dropna().unique()
            if len(locations) > 0:
                location_filter = st.selectbox(
                    "Filter by location:",
                    ['All'] + list(locations)
                )
                if location_filter != 'All':
                    df = df[df[location_col] == location_filter]
    
    # Display data
    st.dataframe(df, use_container_width=True)
    
    # Show summary statistics
    if not df.empty:
        st.subheader("📈 Summary Statistics")
        
        # Price statistics if available
        price_cols = [col for col in df.columns if 'price' in col.lower()]
        if price_cols:
            for price_col in price_cols:
                if df[price_col].notna().any():
                    st.write(f"**{price_col}:**")
                    # Try to extract numeric values from price strings
                    numeric_prices = pd.to_numeric(df[price_col].astype(str).str.extract(r'([\d,]+)')[0].str.replace(',', ''), errors='coerce')
                    if numeric_prices.notna().any():
                        st.write(f"- Average: {numeric_prices.mean():.2f}")
                        st.write(f"- Median: {numeric_prices.median():.2f}")
                        st.write(f"- Min: {numeric_prices.min():.2f}")
                        st.write(f"- Max: {numeric_prices.max():.2f}")

def download_data_page():
    st.header("💾 Download Data")
    
    # Get data from database
    df = get_all_properties()
    
    if df.empty:
        st.info("No data found in the database. Please upload and process some HTML files first.")
        return
    
    st.subheader(f"Available Records: {len(df)}")
    
    # Download options
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV download
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        st.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f"property_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # JSON download
        json_data = df.to_json(orient='records', indent=2)
        
        st.download_button(
            label="📋 Download as JSON",
            data=json_data,
            file_name=f"property_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    # Preview of data to be downloaded
    st.subheader("📋 Data Preview")
    st.dataframe(df.head(10), use_container_width=True)
    
    if len(df) > 10:
        st.info(f"Showing first 10 rows. Total rows: {len(df)}")

if __name__ == "__main__":
    main()