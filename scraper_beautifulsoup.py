#!/usr/bin/env python3
"""
TrackWrestling Scraper for Shawnee High School Wrestling
Simple BeautifulSoup approach - no Selenium/Playwright needed
"""

import json
import time
from datetime import datetime
from typing import Dict, List
import logging
import os
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrackWrestlingScraper:
    """Simple scraper using requests + BeautifulSoup"""
    
    def __init__(self, team_id: str, season_id: str):
        self.team_id = team_id
        self.season_id = season_id
        self.base_url = "https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
    
    def fetch_page(self, page_name: str) -> BeautifulSoup:
        """Fetch a page from TrackWrestling"""
        url = f"{self.base_url}?seasonId={self.season_id}&gbId=36&pageName={page_name};teamId={self.team_id}"
        
        logger.info(f"Fetching: {page_name}")
        logger.info(f"URL: {url}")
        
        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Final URL: {response.url}")
            logger.info(f"Content length: {len(response.text)} bytes")
            
            # Save HTML for debugging
            debug_file = f'/tmp/{page_name.replace(".jsp", "")}_debug.html'
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info(f"Saved to: {debug_file}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Count tables
            tables = soup.find_all('table')
            logger.info(f"Found {len(tables)} tables in page")
            
            return soup
            
        except requests.RequestException as e:
            logger.error(f"Error fetching {page_name}: {e}")
            return BeautifulSoup("", 'html.parser')
    
    def scrape_schedule(self) -> List[Dict]:
        """Scrape team schedule"""
        logger.info("="*60)
        logger.info("SCRAPING SCHEDULE")
        logger.info("="*60)
        
        soup = self.fetch_page("TeamSchedule.jsp")
        schedule = []
        
        tables = soup.find_all('table')
        
        for table_idx, table in enumerate(tables):
            logger.info(f"Processing table {table_idx + 1}/{len(tables)}")
            rows = table.find_all('tr')
            logger.info(f"  Found {len(rows)} rows")
            
            for row_idx, row in enumerate(rows):
                cols = row.find_all(['td', 'th'])
                
                if len(cols) < 2:
                    continue
                
                # Extract text
                texts = [col.get_text(strip=True) for col in cols]
                
                # Skip if looks like header
                lower_text = ' '.join(texts).lower()
                if any(word in lower_text for word in ['date', 'opponent', 'time', 'location', 'when', 'where']):
                    logger.info(f"  Row {row_idx}: HEADER (skipped)")
                    continue
                
                # Skip empty
                if not any(texts):
                    continue
                
                # Log what we found
                logger.info(f"  Row {row_idx}: {texts}")
                
                # Build match entry
                match = {
                    'date': texts[0] if len(texts) > 0 else '',
                    'opponent': texts[1] if len(texts) > 1 else '',
                    'location': texts[2] if len(texts) > 2 else '',
                    'time': texts[3] if len(texts) > 3 else '',
                    'result': texts[4] if len(texts) > 4 else 'TBD'
                }
                
                # Add if we have date and opponent
                if match['date'] and match['opponent'] and len(match['date']) > 3:
                    schedule.append(match)
                    logger.info(f"  ✓ ADDED: {match['date']} vs {match['opponent']}")
        
        logger.info(f"Total schedule entries: {len(schedule)}")
        return schedule
    
    def scrape_roster(self) -> List[Dict]:
        """Scrape team roster"""
        logger.info("="*60)
        logger.info("SCRAPING ROSTER")
        logger.info("="*60)
        
        soup = self.fetch_page("TeamRoster.jsp")
        roster = []
        
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cols = row.find_all(['td', 'th'])
                
                if len(cols) < 2:
                    continue
                
                texts = [col.get_text(strip=True) for col in cols]
                
                # Skip headers
                if any(word in ' '.join(texts).lower() for word in ['name', 'weight', 'grade', 'wrestler']):
                    continue
                
                if not any(texts):
                    continue
                
                wrestler = {
                    'name': texts[0] if len(texts) > 0 else '',
                    'weight_class': texts[1] if len(texts) > 1 else '',
                    'grade': texts[2] if len(texts) > 2 else '',
                    'record': texts[3] if len(texts) > 3 else ''
                }
                
                if wrestler['name'] and len(wrestler['name']) > 2:
                    roster.append(wrestler)
                    logger.info(f"✓ {wrestler['name']} - {wrestler['weight_class']}")
        
        logger.info(f"Total roster entries: {len(roster)}")
        return roster
    
    def scrape_results(self) -> List[Dict]:
        """Scrape match results"""
        logger.info("="*60)
        logger.info("SCRAPING RESULTS")
        logger.info("="*60)
        
        soup = self.fetch_page("TeamResults.jsp")
        results = []
        
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cols = row.find_all(['td', 'th'])
                
                if len(cols) < 3:
                    continue
                
                texts = [col.get_text(strip=True) for col in cols]
                
                if not any(texts):
                    continue
                
                result = {
                    'date': texts[0] if len(texts) > 0 else '',
                    'opponent': texts[1] if len(texts) > 1 else '',
                    'score': texts[2] if len(texts) > 2 else '',
                    'result': texts[3] if len(texts) > 3 else '',
                    'location': texts[4] if len(texts) > 4 else ''
                }
                
                if result['date'] and result['opponent']:
                    results.append(result)
                    logger.info(f"✓ {result['date']}: {result['result']} vs {result['opponent']}")
        
        logger.info(f"Total results entries: {len(results)}")
        return results
    
    def scrape_all(self) -> Dict:
        """Scrape all data"""
        logger.info("="*60)
        logger.info("STARTING SCRAPE")
        logger.info(f"Team ID: {self.team_id}")
        logger.info(f"Season ID: {self.season_id}")
        logger.info("="*60)
        
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
    TEAM_ID = "768996150"
    SEASON_ID = "1560212138"
    
    scraper = TrackWrestlingScraper(TEAM_ID, SEASON_ID)
    data = scraper.scrape_all()
    
    # Save to JSON file
    output_file = 'data/wrestling_data.json'
    os.makedirs('data', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info("="*60)
    logger.info("SCRAPE COMPLETE")
    logger.info("="*60)
    logger.info(f"Saved to: {output_file}")
    logger.info(f"Roster: {len(data['roster'])} wrestlers")
    logger.info(f"Schedule: {len(data['schedule'])} matches")
    logger.info(f"Results: {len(data['results'])} results")
    logger.info("="*60)
    
    # Show sample data
    if data['schedule']:
        logger.info("\nSample schedule entry:")
        logger.info(json.dumps(data['schedule'][0], indent=2))
    
    if len(data['schedule']) == 0:
        logger.warning("\n⚠️  NO SCHEDULE DATA FOUND!")
        logger.warning("Check the HTML files saved in /tmp/ to see what was returned")


if __name__ == "__main__":
    main()
