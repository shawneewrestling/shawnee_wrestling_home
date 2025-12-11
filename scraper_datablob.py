#!/usr/bin/env python3
"""
TrackWrestling Data Blob Parser
Extracts schedule from the JavaScript initDataGrid() call in the page source
"""

import json
import re
from datetime import datetime
from typing import Dict, List
import logging
import os
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrackWrestlingDataBlobScraper:
    """Scraper that extracts data from JavaScript blob"""
    
    def __init__(self, team_id: str, season_id: str):
        self.team_id = team_id
        self.season_id = season_id
        self.base_url = "https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    
    def fetch_page(self, page_name: str) -> str:
        """Fetch page and return raw HTML"""
        url = f"{self.base_url}?seasonId={self.season_id}&gbId=36&pageName={page_name};teamId={self.team_id}"
        
        logger.info(f"Fetching: {url}")
        
        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            logger.info(f"Got {len(response.text)} bytes")
            return response.text
        except Exception as e:
            logger.error(f"Error fetching: {e}")
            return ""
    
    def extract_data_blob(self, html: str) -> str:
        """Extract the JavaScript data array from initDataGrid() call"""
        # Look for: initDataGrid(1000, false, "[[\"data\",\"here\"]]"
        pattern = r'initDataGrid\([^"]*"(\[\[.*?\]\])"'
        
        match = re.search(pattern, html, re.DOTALL)
        if match:
            data_str = match.group(1)
            logger.info(f"Found data blob: {len(data_str)} characters")
            return data_str
        else:
            logger.warning("No initDataGrid data found")
            return ""
    
    def parse_schedule_blob(self, data_str: str) -> List[Dict]:
        """Parse the schedule data array"""
        if not data_str:
            return []
        
        try:
            # The data is a JSON array of arrays
            data = json.loads(data_str)
            logger.info(f"Parsed {len(data)} schedule entries")
            
            schedule = []
            
            for row in data:
                if not row or len(row) < 10:
                    continue
                
                # Based on the data structure you provided:
                # row[2] = Event name/description
                # row[3] = Start date (YYYYMMDD format)
                # row[4] = Time (HHMM format)
                # row[12] = Home/Away indicator (H/A)
                # row[16] = Opponent/Location
                
                event_name = row[2] if len(row) > 2 else ""
                date_str = row[3] if len(row) > 3 else ""
                time_str = row[4] if len(row) > 4 else ""
                home_away = row[12] if len(row) > 12 else ""
                location = row[16] if len(row) > 16 else ""
                opponent_name = row[19] if len(row) > 19 else ""
                
                # Parse date from YYYYMMDD to readable format
                if date_str and len(date_str) == 8:
                    try:
                        year = date_str[0:4]
                        month = date_str[4:6]
                        day = date_str[6:8]
                        formatted_date = f"{month}/{day}/{year}"
                    except:
                        formatted_date = date_str
                else:
                    formatted_date = date_str
                
                # Parse time from HHMM to readable format
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
                    formatted_time = time_str or "TBD"
                
                # Determine opponent
                if opponent_name:
                    opponent = opponent_name
                elif "vs" in event_name.lower() or "@" in event_name:
                    opponent = event_name
                else:
                    opponent = event_name
                
                # Determine location
                if home_away == "H":
                    match_location = "Shawnee High School"
                elif home_away == "A" and location:
                    match_location = location
                else:
                    match_location = location or "TBD"
                
                match = {
                    'date': formatted_date,
                    'opponent': opponent,
                    'location': match_location,
                    'time': formatted_time,
                    'result': 'TBD'
                }
                
                schedule.append(match)
                logger.info(f"✓ {formatted_date} - {opponent}")
            
            return schedule
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing schedule: {e}")
            return []
    
    def scrape_schedule(self) -> List[Dict]:
        """Scrape schedule using data blob method"""
        logger.info("="*60)
        logger.info("SCRAPING SCHEDULE (Data Blob Method)")
        logger.info("="*60)
        
        html = self.fetch_page("TeamSchedule.jsp")
        if not html:
            return []
        
        data_blob = self.extract_data_blob(html)
        if not data_blob:
            logger.error("Could not find data blob in page")
            return []
        
        schedule = self.parse_schedule_blob(data_blob)
        logger.info(f"Extracted {len(schedule)} matches")
        
        return schedule
    
    def scrape_roster(self) -> List[Dict]:
        """Scrape roster using data blob method"""
        logger.info("="*60)
        logger.info("SCRAPING ROSTER (Data Blob Method)")
        logger.info("="*60)
        
        html = self.fetch_page("TeamRoster.jsp")
        data_blob = self.extract_data_blob(html)
        
        # Roster parsing would be similar - adjust based on roster data structure
        # For now, return empty array
        return []
    
    def scrape_results(self) -> List[Dict]:
        """Scrape results"""
        logger.info("="*60)
        logger.info("SCRAPING RESULTS")
        logger.info("="*60)
        
        # Results would be parsed similarly from their data blob
        return []
    
    def scrape_all(self) -> Dict:
        """Scrape all data"""
        data = {
            'metadata': {
                'team_id': self.team_id,
                'season_id': self.season_id,
                'last_updated': datetime.now().isoformat(),
                'team_name': 'Shawnee High School'
            },
            'roster': self.scrape_roster(),
            'schedule': self.scrape_schedule(),
            'results': self.scrape_results()
        }
        
        return data


def main():
    """Main function"""
    TEAM_ID = "768996150"
    SEASON_ID = "1560212138"
    
    logger.info("="*60)
    logger.info("TrackWrestling Data Blob Scraper")
    logger.info("="*60)
    
    scraper = TrackWrestlingDataBlobScraper(TEAM_ID, SEASON_ID)
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
    logger.info(f"Roster: {len(data['roster'])} wrestlers")
    logger.info(f"Results: {len(data['results'])} results")
    logger.info("="*60)
    
    # Show first few matches
    if data['schedule']:
        logger.info("\nFirst 3 matches:")
        for match in data['schedule'][:3]:
            logger.info(f"  {match['date']} - {match['opponent']} @ {match['location']}, {match['time']}")


if __name__ == "__main__":
    main()
