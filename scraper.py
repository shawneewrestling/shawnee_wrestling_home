#!/usr/bin/env python3
"""
TrackWrestling Scraper for Shawnee High School Wrestling
Scrapes roster, schedule, and results data from TrackWrestling
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrackWrestlingScraper:
    """Scraper for TrackWrestling team data"""
    
    def __init__(self, team_id: str, season_id: str):
        self.team_id = team_id
        self.season_id = season_id
        self.base_url = "https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _fetch_page(self, page_name: str) -> Optional[str]:
        """Fetch a page from TrackWrestling"""
        params = {
            'seasonId': self.season_id,
            'gbId': '36',
            'pageName': page_name,
            'teamId': self.team_id
        }
        
        try:
            # First request to LoadBalance to get redirected
            response = self.session.get(self.base_url, params=params, allow_redirects=True)
            response.raise_for_status()
            
            # The actual content is at the final URL after redirect
            logger.info(f"Fetched {page_name}, final URL: {response.url}")
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {page_name}: {e}")
            return None
    
    def scrape_roster(self) -> List[Dict]:
        """Scrape team roster"""
        logger.info("Scraping roster...")
        html = self._fetch_page("TeamRoster.jsp")
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        roster = []
        
        # Find roster table - TrackWrestling uses various table structures
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows[1:]:  # Skip header
                cols = row.find_all('td')
                
                if len(cols) >= 3:
                    wrestler = {
                        'name': cols[0].get_text(strip=True),
                        'weight_class': cols[1].get_text(strip=True),
                        'grade': cols[2].get_text(strip=True) if len(cols) > 2 else '',
                        'record': cols[3].get_text(strip=True) if len(cols) > 3 else ''
                    }
                    
                    if wrestler['name']:  # Only add if name exists
                        roster.append(wrestler)
        
        logger.info(f"Found {len(roster)} wrestlers")
        return roster
    
    def scrape_schedule(self) -> List[Dict]:
        """Scrape team schedule"""
        logger.info("Scraping schedule...")
        html = self._fetch_page("TeamSchedule.jsp")
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        schedule = []
        
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows[1:]:  # Skip header
                cols = row.find_all('td')
                
                if len(cols) >= 4:
                    match = {
                        'date': cols[0].get_text(strip=True),
                        'opponent': cols[1].get_text(strip=True),
                        'location': cols[2].get_text(strip=True),
                        'time': cols[3].get_text(strip=True) if len(cols) > 3 else '',
                        'result': cols[4].get_text(strip=True) if len(cols) > 4 else 'TBD'
                    }
                    
                    if match['date']:  # Only add if date exists
                        schedule.append(match)
        
        logger.info(f"Found {len(schedule)} matches")
        return schedule
    
    def scrape_results(self) -> List[Dict]:
        """Scrape match results"""
        logger.info("Scraping results...")
        html = self._fetch_page("TeamResults.jsp")
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # Results parsing will be similar to schedule
        # This structure may need adjustment based on actual page layout
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows[1:]:
                cols = row.find_all('td')
                
                if len(cols) >= 5:
                    result = {
                        'date': cols[0].get_text(strip=True),
                        'opponent': cols[1].get_text(strip=True),
                        'score': cols[2].get_text(strip=True),
                        'result': cols[3].get_text(strip=True),
                        'location': cols[4].get_text(strip=True) if len(cols) > 4 else ''
                    }
                    
                    if result['date']:
                        results.append(result)
        
        logger.info(f"Found {len(results)} results")
        return results
    
    def scrape_all(self) -> Dict:
        """Scrape all data and return as dictionary"""
        logger.info(f"Starting scrape for team {self.team_id}, season {self.season_id}")
        
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
    """Main scraper function"""
    # Import season configuration
    try:
        from season_config import TEAM_ID, SEASON_ID, CURRENT_SEASON
        print(f"Using season configuration: {CURRENT_SEASON}")
    except ImportError:
        # Fallback to hardcoded values if config file doesn't exist
        TEAM_ID = "768996150"
        SEASON_ID = "1560212138"
        CURRENT_SEASON = "2025-26"
        print(f"Using default configuration: {CURRENT_SEASON}")
    
    scraper = TrackWrestlingScraper(TEAM_ID, SEASON_ID)
    data = scraper.scrape_all()
    
    # Save to JSON file
    output_file = 'data/wrestling_data.json'
    
    import os
    os.makedirs('data', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Data saved to {output_file}")
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Scrape Complete!")
    print(f"{'='*50}")
    print(f"Roster: {len(data['roster'])} wrestlers")
    print(f"Schedule: {len(data['schedule'])} matches")
    print(f"Results: {len(data['results'])} completed matches")
    print(f"Last Updated: {data['metadata']['last_updated']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
