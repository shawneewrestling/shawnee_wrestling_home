#!/usr/bin/env python3
"""
TrackWrestling Frame Scraper
Finds the iframe and scrapes data from the actual frame source
"""

import json
import re
from datetime import datetime
from typing import Dict, List
import logging
import os
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrackWrestlingFrameScraper:
    """Scraper that follows iframes to get data"""
    
    def __init__(self, team_id: str, season_id: str):
        self.team_id = team_id
        self.season_id = season_id
        self.base_url = "https://www.trackwrestling.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    
    def find_frame_url(self, main_url: str) -> str:
        """Find the iframe URL that contains the actual data"""
        logger.info(f"Fetching main page: {main_url}")
        
        try:
            response = self.session.get(main_url, timeout=30)
            html = response.text
            
            # Look for iframe or frame tags
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try iframe first
            iframes = soup.find_all('iframe')
            logger.info(f"Found {len(iframes)} iframes")
            
            for iframe in iframes:
                src = iframe.get('src', '')
                if src:
                    logger.info(f"  iframe src: {src}")
                    # Make absolute URL
                    if src.startswith('/'):
                        return self.base_url + src
                    elif src.startswith('http'):
                        return src
            
            # Try frame tags (older framesets)
            frames = soup.find_all('frame')
            logger.info(f"Found {len(frames)} frames")
            
            for frame in frames:
                src = frame.get('src', '')
                name = frame.get('name', '')
                logger.info(f"  frame name={name} src: {src}")
                
                # Look for mainFrame or similar
                if 'main' in name.lower() or 'content' in name.lower():
                    if src:
                        if src.startswith('/'):
                            return self.base_url + src
                        elif src.startswith('http'):
                            return src
            
            # If no frames found, check if data is directly in page
            if 'initDataGrid' in html:
                logger.info("Data found directly in main page")
                return main_url
            
            logger.warning("No frames found and no data in main page")
            return main_url
            
        except Exception as e:
            logger.error(f"Error finding frame: {e}")
            return main_url
    
    def extract_data_blob(self, html: str) -> str:
        """Extract the JavaScript data array from initDataGrid() call"""
        # Look for: initDataGrid(1000, false, "[[\"data\",\"here\"]]"
        pattern = r'initDataGrid\([^"]*"(\[\[.*?\]\])"'
        
        match = re.search(pattern, html, re.DOTALL)
        if match:
            data_str = match.group(1)
            logger.info(f"✓ Found data blob: {len(data_str)} characters")
            return data_str
        else:
            logger.warning("✗ No initDataGrid data found")
            return ""
    
    def parse_schedule_blob(self, data_str: str) -> List[Dict]:
        """Parse the schedule data array"""
        if not data_str:
            return []
        
        try:
            data = json.loads(data_str)
            logger.info(f"Parsed {len(data)} entries from blob")
            
            schedule = []
            
            for idx, row in enumerate(data):
                if not row or len(row) < 10:
                    continue
                
                try:
                    # Extract fields based on TrackWrestling structure
                    event_name = row[2] if len(row) > 2 else ""
                    date_str = row[3] if len(row) > 3 else ""
                    time_str = row[4] if len(row) > 4 else ""
                    home_away = row[12] if len(row) > 12 else ""
                    location = row[16] if len(row) > 16 else ""
                    opponent_name = row[19] if len(row) > 19 else ""
                    
                    # Format date: 20251213 -> 12/13/2025
                    if date_str and len(date_str) == 8:
                        year = date_str[0:4]
                        month = date_str[4:6]
                        day = date_str[6:8]
                        formatted_date = f"{month}/{day}/{year}"
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
                            formatted_time = time_str
                    else:
                        formatted_time = "TBD"
                    
                    # Determine opponent
                    opponent = opponent_name if opponent_name else event_name
                    
                    # Determine location
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
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Data blob: {data_str[:200]}...")
            return []
        except Exception as e:
            logger.error(f"Error parsing schedule: {e}")
            return []
    
    def scrape_schedule(self) -> List[Dict]:
        """Scrape schedule by following frames"""
        logger.info("="*60)
        logger.info("SCRAPING SCHEDULE (Frame Method)")
        logger.info("="*60)
        
        # Initial URL
        main_url = f"https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId={self.season_id}&gbId=36&pageName=TeamSchedule.jsp;teamId={self.team_id}"
        
        # Find the frame URL
        frame_url = self.find_frame_url(main_url)
        logger.info(f"Frame URL: {frame_url}")
        
        # Fetch the frame content
        try:
            response = self.session.get(frame_url, timeout=30)
            html = response.text
            logger.info(f"Got frame content: {len(html)} bytes")
            
            # Save for debugging
            with open('/tmp/frame_content.html', 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info("Saved to /tmp/frame_content.html")
            
        except Exception as e:
            logger.error(f"Error fetching frame: {e}")
            return []
        
        # Extract data blob
        data_blob = self.extract_data_blob(html)
        if not data_blob:
            logger.error("No data blob found in frame")
            return []
        
        # Parse schedule
        schedule = self.parse_schedule_blob(data_blob)
        logger.info(f"✓ Extracted {len(schedule)} matches")
        
        return schedule
    
    def scrape_all(self) -> Dict:
        """Scrape all data"""
        data = {
            'metadata': {
                'team_id': self.team_id,
                'season_id': self.season_id,
                'last_updated': datetime.now().isoformat(),
                'team_name': 'Shawnee High School'
            },
            'roster': [],
            'schedule': self.scrape_schedule(),
            'results': []
        }
        
        return data


def main():
    """Main function"""
    TEAM_ID = "768996150"
    SEASON_ID = "1560212138"
    
    logger.info("="*60)
    logger.info("TrackWrestling Frame Scraper")
    logger.info("="*60)
    
    scraper = TrackWrestlingFrameScraper(TEAM_ID, SEASON_ID)
    data = scraper.scrape_all()
    
    # Save to file
    output_file = 'data/wrestling_data.json'
    os.makedirs('data', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info("="*60)
    logger.info("COMPLETE!")
    logger.info("="*60)
    logger.info(f"Saved to: {output_file}")
    logger.info(f"Schedule: {len(data['schedule'])} matches")
    logger.info("="*60)
    
    if data['schedule']:
        print("\n✓ SUCCESS - Schedule populated!")
        print("\nFirst 5 matches:")
        for match in data['schedule'][:5]:
            print(f"  {match['date']} - {match['opponent']} @ {match['location']}, {match['time']}")
    else:
        print("\n✗ NO SCHEDULE DATA")
        print("Check /tmp/frame_content.html to see what was returned")


if __name__ == "__main__":
    main()
