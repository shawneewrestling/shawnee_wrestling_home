#!/usr/bin/env python3
"""
TrackWrestling Scraper for Shawnee High School Wrestling
Uses Playwright for reliable JavaScript rendering
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, List
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def scrape_with_playwright(team_id: str, season_id: str) -> Dict:
    """Scrape using Playwright for better JavaScript support"""
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return create_empty_data(team_id, season_id)
    
    data = {
        'metadata': {
            'team_id': team_id,
            'season_id': season_id,
            'last_updated': datetime.now().isoformat(),
            'team_name': 'Shawnee High School',
            'season': '2025-26'
        },
        'roster': [],
        'schedule': [],
        'results': []
    }
    
    base_url = "https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Set timeout
            page.set_default_timeout(30000)
            
            # Scrape Schedule
            logger.info("Fetching schedule...")
            schedule_url = f"{base_url}?seasonId={season_id}&gbId=36&pageName=TeamSchedule.jsp;teamId={team_id}"
            await page.goto(schedule_url)
            
            # Wait for content to load
            try:
                await page.wait_for_selector('table', timeout=10000)
                await asyncio.sleep(2)  # Extra wait for JS
            except:
                logger.warning("No table found on schedule page")
            
            # Extract schedule data
            schedule_html = await page.content()
            data['schedule'] = parse_schedule_html(schedule_html)
            logger.info(f"Found {len(data['schedule'])} matches")
            
            # Scrape Roster
            logger.info("Fetching roster...")
            roster_url = f"{base_url}?seasonId={season_id}&gbId=36&pageName=TeamRoster.jsp;teamId={team_id}"
            await page.goto(roster_url)
            
            try:
                await page.wait_for_selector('table', timeout=10000)
                await asyncio.sleep(2)
            except:
                logger.warning("No table found on roster page")
            
            roster_html = await page.content()
            data['roster'] = parse_roster_html(roster_html)
            logger.info(f"Found {len(data['roster'])} wrestlers")
            
            # Scrape Results (if any)
            logger.info("Fetching results...")
            results_url = f"{base_url}?seasonId={season_id}&gbId=36&pageName=TeamResults.jsp;teamId={team_id}"
            await page.goto(results_url)
            
            try:
                await page.wait_for_selector('table', timeout=10000)
                await asyncio.sleep(2)
            except:
                logger.warning("No table found on results page")
            
            results_html = await page.content()
            data['results'] = parse_results_html(results_html)
            logger.info(f"Found {len(data['results'])} results")
            
            await browser.close()
            
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        import traceback
        traceback.print_exc()
    
    return data

def parse_schedule_html(html: str) -> List[Dict]:
    """Parse schedule from HTML"""
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html, 'html.parser')
    schedule = []
    
    # Find all tables
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        
        for i, row in enumerate(rows):
            # Skip header rows
            if i == 0:
                continue
                
            cols = row.find_all(['td', 'th'])
            if len(cols) < 2:
                continue
            
            # Extract text from columns
            col_texts = [col.get_text(strip=True) for col in cols]
            
            # Skip if it looks like a header
            if any(text.lower() in ['date', 'opponent', 'location', 'time', 'result'] 
                   for text in col_texts):
                continue
            
            # Skip empty rows
            if not any(col_texts):
                continue
            
            # Try to build a match entry
            match = {
                'date': col_texts[0] if len(col_texts) > 0 else '',
                'opponent': col_texts[1] if len(col_texts) > 1 else '',
                'location': col_texts[2] if len(col_texts) > 2 else '',
                'time': col_texts[3] if len(col_texts) > 3 else '',
                'result': col_texts[4] if len(col_texts) > 4 else 'TBD'
            }
            
            # Only add if we have at least a date and opponent
            if match['date'] and match['opponent'] and len(match['date']) > 3:
                schedule.append(match)
    
    return schedule

def parse_roster_html(html: str) -> List[Dict]:
    """Parse roster from HTML"""
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html, 'html.parser')
    roster = []
    
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        
        for i, row in enumerate(rows):
            if i == 0:
                continue
                
            cols = row.find_all(['td', 'th'])
            if len(cols) < 2:
                continue
            
            col_texts = [col.get_text(strip=True) for col in cols]
            
            # Skip headers
            if any(text.lower() in ['name', 'weight', 'grade', 'record'] 
                   for text in col_texts):
                continue
            
            if not any(col_texts):
                continue
            
            wrestler = {
                'name': col_texts[0] if len(col_texts) > 0 else '',
                'weight_class': col_texts[1] if len(col_texts) > 1 else '',
                'grade': col_texts[2] if len(col_texts) > 2 else '',
                'record': col_texts[3] if len(col_texts) > 3 else ''
            }
            
            if wrestler['name'] and len(wrestler['name']) > 2:
                roster.append(wrestler)
    
    return roster

def parse_results_html(html: str) -> List[Dict]:
    """Parse results from HTML"""
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        
        for i, row in enumerate(rows):
            if i == 0:
                continue
                
            cols = row.find_all(['td', 'th'])
            if len(cols) < 3:
                continue
            
            col_texts = [col.get_text(strip=True) for col in cols]
            
            if not any(col_texts):
                continue
            
            result = {
                'date': col_texts[0] if len(col_texts) > 0 else '',
                'opponent': col_texts[1] if len(col_texts) > 1 else '',
                'score': col_texts[2] if len(col_texts) > 2 else '',
                'result': col_texts[3] if len(col_texts) > 3 else '',
                'location': col_texts[4] if len(col_texts) > 4 else ''
            }
            
            if result['date'] and result['opponent']:
                results.append(result)
    
    return results

def create_empty_data(team_id: str, season_id: str) -> Dict:
    """Create empty data structure if scraping fails"""
    return {
        'metadata': {
            'team_id': team_id,
            'season_id': season_id,
            'last_updated': datetime.now().isoformat(),
            'team_name': 'Shawnee High School',
            'season': '2025-26'
        },
        'roster': [],
        'schedule': [],
        'results': []
    }

async def main():
    """Main scraper function"""
    # Import season configuration
    try:
        from season_config import TEAM_ID, SEASON_ID, CURRENT_SEASON
        print(f"Using season configuration: {CURRENT_SEASON}")
    except ImportError:
        TEAM_ID = "768996150"
        SEASON_ID = "1560212138"
        CURRENT_SEASON = "2025-26"
        print(f"Using default configuration: {CURRENT_SEASON}")
    
    # Scrape data
    data = await scrape_with_playwright(TEAM_ID, SEASON_ID)
    
    # Save to JSON file
    output_file = 'data/wrestling_data.json'
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
    
    # Warn if no data found
    if len(data['schedule']) == 0:
        print("⚠️  WARNING: No schedule data found!")
        print("   This could mean:")
        print("   - TrackWrestling hasn't published the schedule yet")
        print("   - The page structure changed")
        print("   - Network/timeout issues")
        print(f"   - Check manually: https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId={SEASON_ID}&gbId=36&pageName=TeamSchedule.jsp;teamId={TEAM_ID}")

if __name__ == "__main__":
    asyncio.run(main())
