import json
import csv
from bs4 import BeautifulSoup
from bs4.element import NavigableString

def extract_full_property_info_css_selector(html_content, page_url=None):
    """
    Extracts property information using CSS selectors to find the
    utag_data script tag, and also extracts details from other sections
    like 'Características básicas', 'Equipamiento', and 'Certificado energético'.
    It also extracts the canonical URL from the <link rel="canonical"> tag.
    Includes fallback to string search for utag_data.

    Args:
        html_content: HTML content string.
        page_url: Original page URL (optional, will be overridden if canonical URL is found).

    Returns:
        Dictionary of property information.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    property_info = {
        'characteristics': {},
        'ad_info': {},
        'details': {'basic_features': [], 'equipment': [], 'energy_certificate': {}},
        'source_url': page_url # Initialize with provided page_url, will be updated if canonical is found
    }

    # 0. Extract canonical URL
    canonical_link_tag = soup.find('link', rel='canonical')
    if canonical_link_tag and canonical_link_tag.get('href'):
        property_info['source_url'] = canonical_link_tag['href']

    # 1. Try CSS selector to find script tag (more direct)
    script_tags_css = soup.select('script') # Select all script tags

    utag_data_script_tag = None
    for tag in script_tags_css:
        if tag.string and "var utag_data" in tag.string:
            utag_data_script_tag = tag
            break # Stop once found

    if not utag_data_script_tag: # 2. Fallback to original string search if CSS fails
        utag_data_script_tag = soup.find('script', string=lambda text: isinstance(text, NavigableString) and "utag_data" in text)
        if not utag_data_script_tag: # Even simpler fallback
             utag_data_script_tag = soup.find('script', string=lambda text:  "utag_data" in text if text else False)

    if utag_data_script_tag:
        script_content = utag_data_script_tag.string
        if script_content:
            start_index = script_content.find('var utag_data = ')
            if start_index != -1:
                start_index += len('var utag_data = ')
                end_index = script_content.find(';', start_index)
                if end_index != -1:
                    try:
                        utag_data_json_str = script_content[start_index:end_index]
                        utag_data = json.loads(utag_data_json_str)

                        if "ad" in utag_data and isinstance(utag_data["ad"], dict) and "characteristics" in utag_data["ad"]:
                            characteristics = utag_data["ad"]["characteristics"]
                            property_info['characteristics'] = {k: characteristics[k] for k in characteristics}

                        if "ad" in utag_data and isinstance(utag_data["ad"], dict):
                            ad_data = utag_data["ad"]
                            property_info['ad_info']['id'] = ad_data.get("id", None)
                            property_info['ad_info']['operation'] = ad_data.get("operation", None)
                            property_info['ad_info']['typology'] = ad_data.get("typology", None)
                            property_info['ad_info']['price'] = ad_data.get("price", None)
                            property_info['ad_info']['builtType'] = ad_data.get("builtType", None)

                            if "address" in ad_data and isinstance(ad_data["address"], dict):
                                address_data = ad_data["address"]
                                location_parts = []
                                if address_data.get("locationLevel") == "6":
                                    if address_data.get("municipalityId"):
                                        location_parts.append(address_data.get("municipalityId").split('-')[-1])
                                    if address_data.get("provinceId"):
                                        location_parts.append(address_data.get("provinceId").split('-')[-1])
                                property_info['ad_info']['location'] = ", ".join(location_parts) if location_parts else None

                            if "condition" in ad_data and isinstance(ad_data["condition"], dict):
                                property_info['ad_info']['condition'] = {k: ad_data["condition"][k] for k in ad_data["condition"]}

                            if "media" in ad_data and isinstance(ad_data["media"], dict):
                                property_info['ad_info']['media'] = {k: ad_data["media"][k] for k in ad_data["media"]}

                            if "owner" in ad_data and isinstance(ad_data["owner"], dict):
                                property_info['ad_info']['owner'] = {k: ad_data["owner"][k] for k in ad_data["owner"]}

                            if "agency" in ad_data and isinstance(ad_data["agency"], dict):
                                property_info['ad_info']['agency'] = {k: ad_data["agency"][k] for k in ad_data["agency"]}

                    except json.JSONDecodeError:
                        print("Error decoding JSON from script content (utag_data).")

    # Extract details from other sections
    details_property_div = soup.find('div', class_='details-property')
    if details_property_div:
        # Características básicas
        basic_features_div = details_property_div.find('div', class_='details-property-feature-one')
        if basic_features_div:
            basic_features_list = basic_features_div.find('div', class_='details-property_features').find_all('li')
            property_info['details']['basic_features'] = [li.text.strip() for li in basic_features_list]

        # Equipamiento
        equipment_div = details_property_div.find('div', class_='details-property-feature-two')
        if equipment_div:
            equipment_lists = equipment_div.find_all('div', class_='details-property_features')
            if len(equipment_lists) > 0: # Equipamiento list is usually the first
                equipment_list = equipment_lists[0].find_all('li')
                property_info['details']['equipment'] = [li.text.strip() for li in equipment_list]

            if len(equipment_lists) > 1: # Certificado energético list is usually the second
                energy_certificate_list = equipment_lists[1].find_all('li')
                for li in energy_certificate_list:
                    span_elements = li.find_all('span')
                    if len(span_elements) == 2:
                        label = span_elements[0].text.strip()
                        rating_class = span_elements[1].get('class')
                        rating = None
                        if rating_class:
                            rating_parts = rating_class[0].split('-') # class is like icon-energy-c-c
                            if len(rating_parts) >= 3:
                                rating = rating_parts[2].upper() # Get the rating letter, e.g., 'C'
                        if "Consumo" in label:
                            property_info['details']['energy_certificate']['consumption_rating'] = rating
                        elif "Emisiones" in label:
                            property_info['details']['energy_certificate']['emissions_rating'] = rating
    return property_info

def flatten_property_info(property_info):
    """
    Flattens the nested property information dictionary into a single-level dictionary
    suitable for CSV writing.
    """
    flattened_info = {}
    for section, data in property_info.items():
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list): # Flatten lists, e.g., basic_features, equipment
                    for i, item in enumerate(value):
                        flattened_info[f'{section}_{key}_{i}'] = item
                elif isinstance(value, dict): # Flatten nested dictionaries, e.g., energy_certificate
                     for nested_key, nested_value in value.items():
                         flattened_info[f'{section}_{key}_{nested_key}'] = nested_value
                else:
                    flattened_info[f'{section}_{key}'] = value
        elif isinstance(data, list): # Flatten top-level lists if any
            for i, item in enumerate(data):
                flattened_info[f'{section}_{i}'] = item
        else: # For simple key-value pairs at the top level (e.g., source_url)
            flattened_info[section] = data
    return flattened_info

def extract_detailed_property_features(html_content, page_url=None):
    """
    Extracts detailed property features from HTML content, focusing on
    'Características básicas', 'Equipamiento', and 'Certificado energético'
    within the 'details-property' div. Extracts data into a dictionary
    suitable for CSV conversion, handling variable lists and missing values.

    Args:
        html_content: HTML content string.
        page_url: Original page URL (optional, included in output).

    Returns:
        Dictionary of detailed property features, flattened for CSV.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # 0. Extract canonical URL
    canonical_link_tag = soup.find('link', rel='canonical')
    if canonical_link_tag and canonical_link_tag.get('href'):
        page_url = canonical_link_tag['href']

    property_features = {
        'source_url': page_url,
        'property_type': None,
        'floors': None,
        'size_built_sqm': None,
        'size_useful_sqm': None,
        'rooms': None,
        'bathrooms': None,
        'plot_size_sqm': None,
        'terrace': 'No',  # Default values, will be updated if found
        'balcony': 'No',
        'parking': 'No',
        'condition': None,
        'built_in_wardrobes': 'No',
        'storage_room': 'No',
        'orientation': None,
        'built_year': None,
        'heating_type': None,
        'garden': 'No', # Default values for Equipamiento
        'swimming_pool': 'No',
        'energy_consumption_rating': None, # Energy certificate
        'energy_emissions_rating': None,
        'price': None, # Price
        'location': None, # Location
        'ad_update_date': None, # Ad update date
        'advertiser_name': None # Advertiser name
    }

    # Extract Price
    price_span = soup.find('span', class_='info-data-price')
    if price_span:
        price_text = price_span.text.strip()
        property_features['price'] = price_text

    # Extract Location
    location_span = soup.find('span', class_='main-info__title-minor')
    if location_span:
        location_text = location_span.text.strip()
        property_features['location'] = location_text

    # Extract Ad Update Date
    date_update_section = soup.find('section', class_='details-box date-update-block')
    if date_update_section:
        date_update_p = date_update_section.find('p', class_='date-update-text')
        if date_update_p:
            date_update_text = date_update_p.text.strip()
            property_features['ad_update_date'] = date_update_text

    # Extract Advertiser Name
    advertiser_container = soup.find('div', class_='advertiser-name-container')
    if advertiser_container:
        advertiser_link = advertiser_container.find('a', class_='about-advertiser-name')
        if advertiser_link:
            advertiser_name = advertiser_link.text.strip()
            property_features['advertiser_name'] = advertiser_name
    else: # If 'advertiser-name-container' not found, try 'particular'
        particular_span = soup.find('span', class_='particular')
        if particular_span:
            # Extract text directly within 'particular' span, ignoring child tags
            advertiser_name_parts = []
            for child in particular_span.contents:
                if isinstance(child, NavigableString): # Check if it's text and not a tag
                    advertiser_name_parts.append(child.strip())
            advertiser_name = ' '.join(advertiser_name_parts).strip() # Join parts and strip again
            if advertiser_name: # Only assign if not empty
                 property_features['advertiser_name'] = f"PARTICULAR: {advertiser_name}"

    # Try to extract size from info-features div first (before details-property)
    info_features_div = soup.find('div', class_='info-features')
    if info_features_div:
        size_span = info_features_div.find('span') # Size is usually the first span
        if size_span:
            size_text = size_span.text.strip()
            if 'm²' in size_text:
                property_features['size_built_sqm'] = size_text.split(' m²')[0].replace('.','').replace(',','.')

    details_property_div = soup.find('div', class_='details-property')
    if not details_property_div:
        return property_features # Return defaults if main section is not found

    # Características básicas
    basic_features_div = details_property_div.find('div', class_='details-property-feature-one')
    if basic_features_div:
        basic_features_list = basic_features_div.find('div', class_='details-property_features').find_all('li')
        for item in basic_features_list:
            text = item.text.strip()
            if 'Casa o chalet independiente' in text:
                property_features['property_type'] = 'Casa o chalet independiente'
            elif 'planta' in text and 'plantas' not in text:
                property_features['floors'] = text.split(' ')[0]
            elif 'plantas' in text:
                property_features['floors'] = text.split(' ')[0]
            elif 'm² construidos' in text and 'm² útiles' in text:
                parts = text.split(',')
                for part in parts:
                    if 'm² útiles' in part:
                        property_features['size_useful_sqm'] = part.split(' m²')[0].replace(' m² útiles','').strip().replace('.','').replace(',','.')
                    elif 'm² construidos' in part:
                        property_features['size_built_sqm'] = part.split(' m²')[0].replace(' m² construidos','').strip().replace('.','').replace(',','.')
            elif 'habitaciones' in text:
                property_features['rooms'] = text.split(' ')[0]
            elif 'baño' in text and 'baños' not in text:
                property_features['bathrooms'] = text.split(' ')[0]
            elif 'baños' in text:
                property_features['bathrooms'] = text.split(' ')[0]
            elif 'Parcela de' in text and 'm²' in text:
                property_features['plot_size_sqm'] = text.split(' ')[2].replace('m²','').replace('.','').replace(',','.')
            elif 'Terraza' in text:
                property_features['terrace'] = 'Yes'
            elif 'balcón' in text or 'Balcón' in text:
                property_features['balcony'] = 'Yes'
            elif 'garaje' in text:
                property_features['parking'] = 'Yes'
            elif 'Segunda mano' in text:
                property_features['condition'] = text.replace('Segunda mano/','').replace('/buen estado','')
            elif 'Armarios empotrados' in text:
                property_features['built_in_wardrobes'] = 'Yes'
            elif 'Trastero' in text:
                property_features['storage_room'] = 'Yes'
            elif 'Orientación' in text:
                property_features['orientation'] = text.replace('Orientación ','')
            elif 'Construido en' in text:
                property_features['built_year'] = text.split(' ')[-1]
            elif 'No dispone de calefacción' in text:
                property_features['heating_type'] = 'No dispone de calefacción'
            elif 'Calefacción individual' in text:
                property_features['heating_type'] = 'Calefacción individual'

    # Equipamiento
    equipment_div = details_property_div.find('div', class_='details-property-feature-two')
    if equipment_div:
        equipment_lists = equipment_div.find_all('div', class_='details-property_features')
        if len(equipment_lists) > 0:
            equipment_list = equipment_lists[0].find_all('li')
            for item in equipment_list:
                text = item.text.strip()
                if 'Jardín' in text:
                    property_features['garden'] = 'Yes'
                elif 'Piscina' in text:
                    property_features['swimming_pool'] = 'Yes'

        if len(equipment_lists) > 1:
            energy_certificate_list = equipment_lists[1].find_all('li')
            for li in energy_certificate_list:
                span_elements = li.find_all('span')
                if len(span_elements) == 2:
                    label = span_elements[0].text.strip()
                    rating_class = span_elements[1].get('class')
                    rating = None
                    if rating_class:
                        rating_parts = rating_class[0].split('-')
                        if len(rating_parts) >= 3:
                            rating = rating_parts[2].upper()
                    if "Consumo" in label:
                        property_features['energy_consumption_rating'] = rating
                    elif "Emisiones" in label:
                        property_features['energy_emissions_rating'] = rating

    return property_features