#!/usr/bin/env python3
"""
Local Test Script for Shawnee Wrestling Scraper
Run this to test the scraper before deploying
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import TrackWrestlingScraper
import json

def test_scraper():
    """Test the scraper with 2025 season data"""
    print("="*60)
    print("Testing Shawnee Wrestling Scraper")
    print("="*60)
    
    # 2025 Season
    team_id = "768996150"
    season_id = "1560212138"
    
    print(f"\nTeam ID: {team_id}")
    print(f"Season ID: {season_id}")
    print(f"\nFetching data from TrackWrestling...")
    
    scraper = TrackWrestlingScraper(team_id, season_id)
    
    try:
        # Test roster
        print("\n1. Testing Roster Scrape...")
        roster = scraper.scrape_roster()
        print(f"   ✓ Found {len(roster)} wrestlers")
        if roster:
            print(f"   Sample: {roster[0]}")
        
        # Test schedule
        print("\n2. Testing Schedule Scrape...")
        schedule = scraper.scrape_schedule()
        print(f"   ✓ Found {len(schedule)} matches")
        if schedule:
            print(f"   Sample: {schedule[0]}")
        
        # Test results
        print("\n3. Testing Results Scrape...")
        results = scraper.scrape_results()
        print(f"   ✓ Found {len(results)} results")
        if results:
            print(f"   Sample: {results[0]}")
        
        # Full scrape
        print("\n4. Running Full Scrape...")
        data = scraper.scrape_all()
        
        # Save to test file
        test_file = 'data/test_data.json'
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"   ✓ Data saved to {test_file}")
        
        # Summary
        print("\n" + "="*60)
        print("Test Summary:")
        print("="*60)
        print(f"Roster:   {len(data['roster'])} wrestlers")
        print(f"Schedule: {len(data['schedule'])} matches")
        print(f"Results:  {len(data['results'])} results")
        print(f"\nLast Updated: {data['metadata']['last_updated']}")
        
        # Warnings
        if len(data['roster']) == 0:
            print("\n⚠️  WARNING: No roster data found")
            print("   Check if TrackWrestling has published the roster yet")
        
        if len(data['schedule']) == 0:
            print("\n⚠️  WARNING: No schedule data found")
            print("   Check if TrackWrestling has published the schedule yet")
        
        print("\n" + "="*60)
        print("✓ Scraper test completed successfully!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_website():
    """Test if the website can load the data"""
    print("\n" + "="*60)
    print("Testing Website Data Loading")
    print("="*60)
    
    data_file = 'data/wrestling_data.json'
    
    if not os.path.exists(data_file):
        print(f"✗ Data file not found: {data_file}")
        return False
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✓ Data file is valid JSON")
        print(f"✓ Contains {len(data.get('roster', []))} wrestlers")
        print(f"✓ Contains {len(data.get('schedule', []))} matches")
        print(f"✓ Contains {len(data.get('results', []))} results")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in data file: {e}")
        return False
    except Exception as e:
        print(f"✗ Error reading data file: {e}")
        return False


if __name__ == "__main__":
    print("\n🏆 Shawnee Wrestling Automation Test Suite\n")
    
    # Test scraper
    scraper_ok = test_scraper()
    
    # Test website loading
    website_ok = test_website()
    
    # Final result
    print("\n" + "="*60)
    if scraper_ok and website_ok:
        print("✓ ALL TESTS PASSED")
        print("\nYou're ready to deploy to GitHub!")
        print("\nNext steps:")
        print("1. git add .")
        print("2. git commit -m 'Initial setup'")
        print("3. git push origin main")
    else:
        print("✗ SOME TESTS FAILED")
        print("\nPlease fix the errors above before deploying")
    print("="*60 + "\n")
