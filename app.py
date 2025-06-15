import streamlit as st
import pandas as pd
import sqlite3
import json
import csv
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from datetime import datetime
import io
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows

# Import the extraction functions
from html_processor import extract_full_property_info_css_selector, flatten_property_info, extract_detailed_property_features

def main():
    st.set_page_config(
        page_title="Property HTML Data Extractor",
        page_icon="🏠",
        layout="wide"
    )
    
    st.title("🏠 Property HTML Data Extractor")
    st.markdown("Upload HTML files and optionally combine with previous data to extract property information.")
    
    # Initialize session state for storing processed data
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = pd.DataFrame()
    
    # Create two columns for file uploads
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Upload HTML Files")
        uploaded_html_files = st.file_uploader(
            "Choose HTML files", 
            type=['html', 'htm'], 
            accept_multiple_files=True,
            key="html_files"
        )
        
        if uploaded_html_files:
            st.success(f"Uploaded {len(uploaded_html_files)} HTML file(s)")
    
    with col2:
        st.subheader("📊 Upload Previous Data (Optional)")
        uploaded_data_file = st.file_uploader(
            "Choose CSV or XLSX file with previous extractions", 
            type=['csv', 'xlsx', 'xls'],
            key="data_file"
        )
        
        if uploaded_data_file:
            st.success(f"Uploaded previous data: {uploaded_data_file.name}")
    
    # Processing options
    st.subheader("⚙️ Processing Options")
    extraction_method = st.radio(
        "Choose extraction method:",
        ["Full Property Info (CSS Selector)", "Detailed Property Features"],
        horizontal=True
    )
    
    # Process button
    if st.button("🚀 Process Files", type="primary", use_container_width=True):
        if uploaded_html_files:
            process_all_data(uploaded_html_files, uploaded_data_file, extraction_method)
        else:
            st.error("Please upload at least one HTML file to process.")
    
    # Display results if data exists
    if not st.session_state.processed_data.empty:
        display_results()

def process_all_data(html_files, data_file, extraction_method):
    """Process HTML files and combine with previous data if provided."""
    
    # Load previous data if provided
    previous_data = pd.DataFrame()
    if data_file is not None:
        try:
            if data_file.name.endswith('.csv'):
                previous_data = pd.read_csv(data_file)
            else:  # Excel file
                previous_data = pd.read_excel(data_file)
            st.info(f"Loaded {len(previous_data)} records from previous data file.")
        except Exception as e:
            st.error(f"Error loading previous data: {str(e)}")
            previous_data = pd.DataFrame()
    
    # Process HTML files
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_records = []
    total_files = len(html_files)
    
    for i, uploaded_file in enumerate(html_files):
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
            
            processed_records.append(flattened_data)
            
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        
        # Update progress
        progress_bar.progress((i + 1) / total_files)
    
    # Convert processed records to DataFrame
    new_data = pd.DataFrame(processed_records) if processed_records else pd.DataFrame()
    
    # Combine with previous data
    if not previous_data.empty and not new_data.empty:
        # Align columns - add missing columns with NaN
        all_columns = set(previous_data.columns) | set(new_data.columns)
        for col in all_columns:
            if col not in previous_data.columns:
                previous_data[col] = None
            if col not in new_data.columns:
                new_data[col] = None
        
        # Reorder columns to match
        column_order = sorted(all_columns)
        previous_data = previous_data[column_order]
        new_data = new_data[column_order]
        
        # Combine data
        combined_data = pd.concat([previous_data, new_data], ignore_index=True)
        st.session_state.processed_data = combined_data
        
        status_text.text(f"✅ Processing complete! Combined {len(previous_data)} previous records with {len(new_data)} new records.")
        
    elif not new_data.empty:
        st.session_state.processed_data = new_data
        status_text.text(f"✅ Processing complete! Processed {len(new_data)} new records.")
        
    elif not previous_data.empty:
        st.session_state.processed_data = previous_data
        status_text.text(f"✅ Loaded {len(previous_data)} records from previous data.")
        
    else:
        st.error("No data was processed successfully.")

def display_results():
    """Display the processed data and download options."""
    
    st.subheader(f"📊 Results ({len(st.session_state.processed_data)} records)")
    
    # Display filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if 'extraction_method' in st.session_state.processed_data.columns:
            methods = st.session_state.processed_data['extraction_method'].dropna().unique()
            if len(methods) > 1:
                method_filter = st.selectbox(
                    "Filter by extraction method:",
                    ['All'] + list(methods)
                )
            else:
                method_filter = 'All'
        else:
            method_filter = 'All'
    
    with col2:
        location_columns = [col for col in st.session_state.processed_data.columns if 'location' in col.lower()]
        if location_columns:
            location_col = location_columns[0]
            locations = st.session_state.processed_data[location_col].dropna().unique()
            if len(locations) > 1:
                location_filter = st.selectbox(
                    "Filter by location:",
                    ['All'] + list(locations)
                )
            else:
                location_filter = 'All'
        else:
            location_filter = 'All'
    
    with col3:
        # Show/hide columns option
        show_all_columns = st.checkbox("Show all columns", value=False)
    
    # Apply filters
    filtered_data = st.session_state.processed_data.copy()
    
    if method_filter != 'All' and 'extraction_method' in filtered_data.columns:
        filtered_data = filtered_data[filtered_data['extraction_method'] == method_filter]
    
    if location_filter != 'All' and location_columns:
        filtered_data = filtered_data[filtered_data[location_columns[0]] == location_filter]
    
    # Select columns to display
    if not show_all_columns:
        # Show only the most relevant columns
        important_columns = [
            'filename', 'processed_date', 'source_url', 'price', 'location', 
            'property_type', 'rooms', 'bathrooms', 'size_built_sqm', 'size_useful_sqm',
            'ad_info_price', 'ad_info_location', 'ad_info_typology'
        ]
        display_columns = [col for col in important_columns if col in filtered_data.columns]
        if not display_columns:  # Fallback to first 10 columns
            display_columns = filtered_data.columns[:10].tolist()
        display_data = filtered_data[display_columns]
    else:
        display_data = filtered_data
    
    # Display the data table
    st.dataframe(display_data, use_container_width=True, height=400)
    
    # Data management section
    st.subheader("🔧 Data Management")
    
    col1, col2, col3 = st.columns(3)
        
    with col1:
        # Show duplicate info
        total_rows = len(st.session_state.processed_data)
        if total_rows > 0:
            # Check for duplicates based on source_url or filename
            duplicate_columns = []
            if 'source_url' in st.session_state.processed_data.columns:
                duplicate_columns.append('source_url')
            elif 'filename' in st.session_state.processed_data.columns:
                duplicate_columns.append('filename')
            
            if duplicate_columns:
                duplicates = st.session_state.processed_data.duplicated(subset=duplicate_columns, keep=False).sum()
                st.metric("Duplicate Rows", duplicates)

    with col2:
        # Remove duplicates button
        if st.button("🔄 Remove Duplicates", use_container_width=True):
            remove_duplicates()

    with col3:
        # Clear data button
        if st.button("🗑️ Clear All Data", use_container_width=True):
            st.session_state.processed_data = pd.DataFrame()
            st.rerun()
    


    # Download section
    st.subheader("💾 Download Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV download
        csv_buffer = io.StringIO()
        filtered_data.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        st.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f"property_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Excel download
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            filtered_data.to_excel(writer, sheet_name='Property Data', index=False)
        excel_data = excel_buffer.getvalue()
        
        st.download_button(
            label="📊 Download as XLSX",
            data=excel_data,
            file_name=f"property_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    # Show summary statistics
    if len(filtered_data) > 0:
        st.subheader("📈 Summary Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Records", len(filtered_data))
        
        with col2:
            if 'extraction_method' in filtered_data.columns:
                unique_methods = filtered_data['extraction_method'].nunique()
                st.metric("Extraction Methods", unique_methods)
        
        with col3:
            if location_columns:
                unique_locations = filtered_data[location_columns[0]].nunique()
                st.metric("Unique Locations", unique_locations)
        
        with col4:
            if 'filename' in filtered_data.columns:
                unique_files = filtered_data['filename'].nunique()
                st.metric("Source Files", unique_files)
        
        # Price statistics if available
        price_columns = [col for col in filtered_data.columns if 'price' in col.lower() and filtered_data[col].notna().any()]
        if price_columns:
            st.subheader("💰 Price Analysis")
            for price_col in price_columns[:2]:  # Show max 2 price columns
                if filtered_data[price_col].notna().any():
                    # Try to extract numeric values from price strings
                    price_series = filtered_data[price_col].astype(str)
                    numeric_prices = pd.to_numeric(
                        price_series.str.extract(r'([\d,\.]+)')[0].str.replace(',', '').str.replace('.', ''), 
                        errors='coerce'
                    )
                    
                    if numeric_prices.notna().any():
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric(f"Avg {price_col}", f"{numeric_prices.mean():.0f}")
                        with col2:
                            st.metric(f"Median {price_col}", f"{numeric_prices.median():.0f}")
                        with col3:
                            st.metric(f"Min {price_col}", f"{numeric_prices.min():.0f}")
                        with col4:
                            st.metric(f"Max {price_col}", f"{numeric_prices.max():.0f}")

def remove_duplicates():
    """Remove duplicate rows from the processed data."""
    if st.session_state.processed_data.empty:
        st.warning("No data to process for duplicate removal.")
        return
    
    original_count = len(st.session_state.processed_data)
    
    # Define columns to check for duplicates (in order of preference)
    duplicate_check_columns = []
    
    # First priority: source_url (most reliable identifier)
    if 'source_url' in st.session_state.processed_data.columns:
        duplicate_check_columns = ['source_url']
    # Second priority: filename (if no source_url)
    elif 'filename' in st.session_state.processed_data.columns:
        duplicate_check_columns = ['filename']
    # Third priority: combination of key fields
    else:
        potential_columns = ['price', 'location', 'property_type', 'rooms', 'bathrooms', 'size_built_sqm']
        available_columns = [col for col in potential_columns if col in st.session_state.processed_data.columns]
        if available_columns:
            duplicate_check_columns = available_columns[:3]  # Use first 3 available columns
    
    if not duplicate_check_columns:
        # Last resort: check all columns
        st.session_state.processed_data = st.session_state.processed_data.drop_duplicates()
    else:
        # Remove duplicates based on selected columns, keeping the first occurrence
        st.session_state.processed_data = st.session_state.processed_data.drop_duplicates(
            subset=duplicate_check_columns, 
            keep='first'
        ).reset_index(drop=True)
    
    new_count = len(st.session_state.processed_data)
    removed_count = original_count - new_count
    
    if removed_count > 0:
        st.success(f"✅ Removed {removed_count} duplicate row(s). {new_count} unique records remaining.")
        st.rerun()
    else:
        st.info("ℹ️ No duplicate rows found.")

if __name__ == "__main__":
    main()