#!/usr/bin/env python3
"""
TrackWrestling Scraper using Selenium + BeautifulSoup
Based on proven method that has worked before
"""

import json
import re
from datetime import datetime
from typing import Dict, List
import logging
import os
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def scrape_trackwrestling(team_id: str, season_id: str) -> Dict:
    """Scrape using Selenium + BeautifulSoup"""
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from bs4 import BeautifulSoup
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Run: pip install selenium beautifulsoup4")
        return create_empty_data(team_id, season_id)
    
    main_url = f"https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId={season_id}&gbId=36&pageName=TeamSchedule.jsp;teamId={team_id}"
    
    logger.info("="*60)
    logger.info("Selenium + BeautifulSoup Scraper")
    logger.info(f"URL: {main_url}")
    logger.info("="*60)
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run without opening browser window
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = None
    try:
        logger.info("Starting Chrome...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(60)
        
        logger.info("Loading page...")
        driver.get(main_url)
        
        logger.info("Waiting for page to load...")
        time.sleep(5)  # Wait for JavaScript to execute
        
        # Wait for iframe to appear
        try:
            logger.info("Waiting for iframe...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            logger.info("✓ iframe found")
        except:
            logger.info("No iframe found, checking main page")
        
        # Get page source
        page_source = driver.page_source
        logger.info(f"Got page source: {len(page_source)} bytes")
        
        # Save for debugging
        with open('/tmp/selenium_page.html', 'w', encoding='utf-8') as f:
            f.write(page_source)
        logger.info("Saved to /tmp/selenium_page.html")
        
        # Check for iframes
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        logger.info(f"Found {len(iframes)} iframes")
        
        schedule = []
        
        # Try main page first
        logger.info("Checking main page for data...")
        schedule = extract_schedule_from_html(page_source, "main page")
        
        # If no data, try each iframe
        if not schedule and iframes:
            for idx, iframe in enumerate(iframes):
                logger.info(f"Switching to iframe {idx}...")
                try:
                    driver.switch_to.frame(iframe)
                    time.sleep(2)  # Wait for frame content to load
                    
                    frame_source = driver.page_source
                    logger.info(f"Frame {idx} source: {len(frame_source)} bytes")
                    
                    # Save frame source
                    with open(f'/tmp/selenium_frame_{idx}.html', 'w', encoding='utf-8') as f:
                        f.write(frame_source)
                    logger.info(f"Saved to /tmp/selenium_frame_{idx}.html")
                    
                    schedule = extract_schedule_from_html(frame_source, f"iframe {idx}")
                    
                    if schedule:
                        logger.info(f"✓ Found data in iframe {idx}!")
                        break
                    
                    # Switch back to main content
                    driver.switch_to.default_content()
                    
                except Exception as e:
                    logger.warning(f"Error with iframe {idx}: {e}")
                    driver.switch_to.default_content()
        
        data = {
            'metadata': {
                'team_id': team_id,
                'season_id': season_id,
                'last_updated': datetime.now().isoformat(),
                'team_name': 'Shawnee High School'
            },
            'roster': [],
            'schedule': schedule,
            'results': []
        }
        
        return data
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_data(team_id, season_id)
        
    finally:
        if driver:
            driver.quit()
            logger.info("Browser closed")

def extract_schedule_from_html(html: str, source: str) -> List[Dict]:
    """Extract schedule data from HTML"""
    from bs4 import BeautifulSoup
    
    logger.info(f"Extracting from {source}...")
    
    # Check for initDataGrid
    if 'initDataGrid' not in html:
        logger.info(f"✗ No 'initDataGrid' in {source}")
        return []
    
    logger.info(f"✓ Found 'initDataGrid' in {source}")
    
    # Extract data blob
    pattern = r'initDataGrid\([^"]*"(\[\[.*?\]\])"'
    match = re.search(pattern, html, re.DOTALL)
    
    if not match:
        logger.warning("Found 'initDataGrid' but couldn't extract data")
        return []
    
    data_blob = match.group(1)
    logger.info(f"✓ Data blob: {len(data_blob)} characters")
    
    try:
        data = json.loads(data_blob)
        logger.info(f"✓ Parsed: {len(data)} entries")
        
        schedule = []
        
        for idx, row in enumerate(data):
            if not row or len(row) < 10:
                continue
            
            try:
                # Extract data from row
                event_name = row[2] if len(row) > 2 else ""
                date_str = row[3] if len(row) > 3 else ""
                time_str = row[4] if len(row) > 4 else ""
                home_away = row[12] if len(row) > 12 else ""
                location = row[16] if len(row) > 16 else ""
                opponent_name = row[19] if len(row) > 19 else ""
                
                # Format date: 20251213 -> December 13, 2025
                if date_str and len(date_str) == 8:
                    year = date_str[0:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                             'July', 'August', 'September', 'October', 'November', 'December']
                    month_name = months[int(month)]
                    formatted_date = f"{month_name} {int(day)}, {year}"
                else:
                    formatted_date = date_str
                
                # Format time: 0900 -> 9:00 AM
                if time_str and len(time_str) >= 4:
                    try:
                        hour = int(time_str[0:2])
                        minute = time_str[2:4]
                        am_pm = "AM" if hour < 12 else "PM"
                        if hour > 12:
                            hour -= 12
                        elif hour == 0:
                            hour = 12
                        formatted_time = f"{hour}:{minute} {am_pm}"
                    except:
                        formatted_time = time_str if time_str else "TBD"
                else:
                    formatted_time = "TBD"
                
                # Opponent
                opponent = opponent_name if opponent_name else event_name
                
                # Location
                if home_away == "H":
                    match_location = "Shawnee High School"
                elif location:
                    match_location = location
                else:
                    match_location = "TBD"
                
                match = {
                    'date': formatted_date,
                    'opponent': opponent,
                    'location': match_location,
                    'time': formatted_time,
                    'result': 'TBD'
                }
                
                schedule.append(match)
                logger.info(f"  {idx+1}. {formatted_date} - {opponent}")
                
            except Exception as e:
                logger.warning(f"Error parsing row {idx}: {e}")
                continue
        
        return schedule
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON error: {e}")
        return []
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return []

def create_empty_data(team_id: str, season_id: str) -> Dict:
    """Create empty data structure"""
    return {
        'metadata': {
            'team_id': team_id,
            'season_id': season_id,
            'last_updated': datetime.now().isoformat(),
            'team_name': 'Shawnee High School'
        },
        'roster': [],
        'schedule': [],
        'results': []
    }

def main():
    """Main function"""
    TEAM_ID = "768996150"
    SEASON_ID = "1560212138"
    
    logger.info("Starting scraper...")
    data = scrape_trackwrestling(TEAM_ID, SEASON_ID)
    
    # Save to file
    output_file = 'data/wrestling_data.json'
    os.makedirs('data', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info("="*60)
    logger.info("COMPLETE")
    logger.info("="*60)
    logger.info(f"File: {output_file}")
    logger.info(f"Schedule: {len(data['schedule'])} matches")
    logger.info("="*60)
    
    if data['schedule']:
        print("\n✓ SUCCESS!")
        print("\nFirst 5 matches:")
        for match in data['schedule'][:5]:
            print(f"  {match['date']}")
            print(f"    vs {match['opponent']}")
            print(f"    @ {match['location']}, {match['time']}")
            print()
    else:
        print("\n✗ NO SCHEDULE FOUND")
        print("Check /tmp/selenium_*.html files")

if __name__ == "__main__":
    main()
