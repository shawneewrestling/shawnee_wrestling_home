#!/usr/bin/env python3
"""
Shawnee Wrestling Scraper - Based on Working Method
Uses Selenium + direct AJAX calls to TrackWrestling
"""

import json
import os
import time
import re
from datetime import datetime
from typing import Dict, List
import logging
import requests
from zoneinfo import ZoneInfo  # Python 3.9+

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
TEAM_ID = "768996150"
SEASON_ID = "1560212138"
MAX_RETRIES = 3
INITIAL_PAUSE = 1
EST = ZoneInfo("America/New_York")

def scrape_team_schedule(team_id: str, season_id: str) -> List[Dict]:
    """Scrape schedule using TrackWrestling AJAX endpoint"""
    
    logger.info("="*60)
    logger.info(f"Scraping schedule for Team ID: {team_id}")
    logger.info(f"Season ID: {season_id}")
    logger.info("="*60)
    
    schedule = []
    retries = 0
    pause = INITIAL_PAUSE
    
    while retries < MAX_RETRIES:
        try:
            # Use the AJAX endpoint that TrackWrestling uses
            # This is the same pattern from your working scraper
            url = f"https://www.trackwrestling.com/tw/seasons/AjaxFunctions.jsp?TIM={int(time.time()*1000)}&twSessionId=kmgthfvfkl&function=getTeamSchedule&teamId={team_id}&seasonId={season_id}"
            
            logger.info(f"Fetching: {url}")
            
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.text
                logger.info(f"Got response: {len(data)} bytes")
                
                # The response might be wrapped in quotes, remove them
                if data.startswith('"') and data.endswith('"'):
                    data = data[1:-1]
                
                # Parse the JSON
                import json
                schedule_data = json.loads(data)
                
                logger.info(f"Parsed {len(schedule_data)} schedule entries")
                
                # Convert to our format
                for entry in schedule_data:
                    # Extract fields from TrackWrestling format
                    # You'll need to adjust indices based on actual data structure
                    try:
                        event_name = entry[2] if len(entry) > 2 else ""
                        date_str = entry[3] if len(entry) > 3 else ""
                        time_str = entry[4] if len(entry) > 4 else ""
                        home_away = entry[12] if len(entry) > 12 else ""
                        location = entry[16] if len(entry) > 16 else ""
                        opponent = entry[19] if len(entry) > 19 else ""
                        
                        # Format date
                        if date_str and len(date_str) == 8:
                            year = date_str[0:4]
                            month = date_str[4:6]
                            day = date_str[6:8]
                            months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                                     'July', 'August', 'September', 'October', 'November', 'December']
                            formatted_date = f"{months[int(month)]} {int(day)}, {year}"
                        else:
                            formatted_date = date_str
                        
                        # Format time
                        if time_str and len(time_str) >= 4:
                            hour = int(time_str[0:2])
                            minute = time_str[2:4]
                            am_pm = "AM" if hour < 12 else "PM"
                            if hour > 12:
                                hour -= 12
                            elif hour == 0:
                                hour = 12
                            formatted_time = f"{hour}:{minute} {am_pm}"
                        else:
                            formatted_time = "TBD"
                        
                        match = {
                            'date': formatted_date,
                            'opponent': opponent if opponent else event_name,
                            'location': "Shawnee High School" if home_away == "H" else (location or "TBD"),
                            'time': formatted_time,
                            'result': 'TBD'
                        }
                        
                        schedule.append(match)
                        logger.info(f"  ✓ {formatted_date} - {match['opponent']}")
                        
                    except Exception as e:
                        logger.warning(f"Error parsing entry: {e}")
                        continue
                
                logger.info(f"Successfully got {len(schedule)} matches")
                return schedule
                
            else:
                logger.error(f"Bad status code: {response.status_code}")
                raise Exception(f"Status code {response.status_code}")
                
        except Exception as e:
            retries += 1
            if retries < MAX_RETRIES:
                logger.warning(f"Error: {e}. Retrying in {pause} seconds... (Attempt {retries}/{MAX_RETRIES})")
                time.sleep(pause)
                pause *= 2
            else:
                logger.error(f"Failed after {MAX_RETRIES} attempts: {e}")
                return []
    
    return []

def scrape_team_roster(team_id: str, season_id: str) -> List[Dict]:
    """Scrape roster using TrackWrestling AJAX endpoint"""
    
    logger.info("="*60)
    logger.info(f"Scraping roster for Team ID: {team_id}")
    logger.info("="*60)
    
    roster = []
    retries = 0
    pause = INITIAL_PAUSE
    
    while retries < MAX_RETRIES:
        try:
            # Use the roster AJAX endpoint
            url = f"https://www.trackwrestling.com/tw/seasons/AjaxFunctions.jsp?TIM={int(time.time()*1000)}&twSessionId=kmgthfvfkl&function=getTeamRoster&teamId={team_id}&seasonId={season_id}"
            
            logger.info(f"Fetching: {url}")
            
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.text
                logger.info(f"Got response: {len(data)} bytes")
                
                # Remove wrapping quotes if present
                if data.startswith('"') and data.endswith('"'):
                    data = data[1:-1]
                
                # Parse JSON
                roster_data = json.loads(data)
                logger.info(f"Parsed {len(roster_data)} roster entries")
                
                # Convert to our format
                for entry in roster_data:
                    try:
                        # Adjust indices based on actual TrackWrestling data structure
                        first_name = entry[2] if len(entry) > 2 else ""
                        last_name = entry[1] if len(entry) > 1 else ""
                        weight_class = entry[5] if len(entry) > 5 else ""
                        grade = entry[11] if len(entry) > 11 else ""
                        
                        # Combine first and last name
                        full_name = f"{first_name} {last_name}".strip()
                        
                        if full_name:
                            wrestler = {
                                'name': full_name,
                                'weight_class': str(weight_class) if weight_class else '',
                                'grade': str(grade) if grade else '',
                                'record': ''  # Records come from match data
                            }
                            
                            roster.append(wrestler)
                            logger.info(f"  ✓ {full_name} - {weight_class} lbs")
                    
                    except Exception as e:
                        logger.warning(f"Error parsing roster entry: {e}")
                        continue
                
                logger.info(f"Successfully got {len(roster)} wrestlers")
                return roster
                
            else:
                logger.error(f"Bad status code: {response.status_code}")
                raise Exception(f"Status code {response.status_code}")
                
        except Exception as e:
            retries += 1
            if retries < MAX_RETRIES:
                logger.warning(f"Error: {e}. Retrying in {pause} seconds... (Attempt {retries}/{MAX_RETRIES})")
                time.sleep(pause)
                pause *= 2
            else:
                logger.error(f"Failed after {MAX_RETRIES} attempts: {e}")
                return []
    
    return []

def main():
    """Main function"""
    
    logger.info("Starting Shawnee Wrestling Scraper")
    logger.info(f"Current date: {datetime.now()}")
    
    # Get schedule
    schedule = scrape_team_schedule(TEAM_ID, SEASON_ID)
    
    # Get roster
    roster = scrape_team_roster(TEAM_ID, SEASON_ID)
    
    # Create data structure
    data = {
        'metadata': {
            'team_id': TEAM_ID,
            'season_id': SEASON_ID,
            'last_updated': datetime.now().isoformat(),
            'team_name': 'Shawnee High School'
        },
        'roster': roster,
        'schedule': schedule,
        'results': []
    }
    
    # Save to JSON
    output_file = 'data/wrestling_data.json'
    os.makedirs('data', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info("="*60)
    logger.info("COMPLETE")
    logger.info("="*60)
    logger.info(f"Saved to: {output_file}")
    logger.info(f"Roster entries: {len(roster)}")
    logger.info(f"Schedule entries: {len(schedule)}")
    logger.info("="*60)
    
    if schedule or roster:
        print("\n✓ SUCCESS!")
        if roster:
            print(f"\nRoster: {len(roster)} wrestlers")
        if schedule:
            print(f"Schedule: {len(schedule)} matches")
            print(f"\nFirst 3 matches:")
            for match in schedule[:3]:
                print(f"  {match['date']} vs {match['opponent']}")
    else:
        print("\n✗ NO DATA")
        print("Check logs above for errors")

if __name__ == "__main__":
    main()
