#!/usr/bin/env python3
"""
Quick Season Update Script
Run this to update to a new season
"""

import sys

def update_season():
    """Interactive script to update season configuration"""
    
    print("="*60)
    print("Shawnee Wrestling - Season Update Tool")
    print("="*60)
    print()
    
    print("This script will help you update to a new wrestling season.")
    print()
    
    # Get season info
    season_name = input("Enter season name (e.g., 2025-26): ").strip()
    if not season_name:
        print("❌ Season name is required!")
        return
    
    print()
    print("Now find your Team ID and Season ID from TrackWrestling:")
    print("1. Go to trackwrestling.com")
    print("2. Search for 'Shawnee High School'")
    print(f"3. Select the {season_name} season")
    print("4. Look at the URL in your browser")
    print()
    print("Example URL:")
    print("https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?")
    print("  seasonId=1234567890  ← This is your Season ID")
    print("  &teamId=9876543210   ← This is your Team ID")
    print()
    
    team_id = input("Enter Team ID: ").strip()
    if not team_id:
        print("❌ Team ID is required!")
        return
    
    season_id = input("Enter Season ID: ").strip()
    if not season_id:
        print("❌ Season ID is required!")
        return
    
    print()
    print("="*60)
    print("Configuration to be updated:")
    print("="*60)
    print(f"Season:    {season_name}")
    print(f"Team ID:   {team_id}")
    print(f"Season ID: {season_id}")
    print("="*60)
    print()
    
    confirm = input("Update configuration? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("❌ Update cancelled.")
        return
    
    # Update season_config.py
    config_content = f'''# Season Configuration File
# Update these values when a new season starts

# Current Season: {season_name}
CURRENT_SEASON = "{season_name}"
TEAM_ID = "{team_id}"
SEASON_ID = "{season_id}"

# Historical Seasons (for reference)
SEASONS = {{
    "2023-24": {{
        "team_id": "1441922147",
        "season_id": "842514138"
    }},
    "2024-25": {{
        "team_id": "768996150",
        "season_id": "1560212138"
    }},
    "{season_name}": {{
        "team_id": "{team_id}",
        "season_id": "{season_id}"
    }}
}}

# TrackWrestling URLs (for reference)
# Format: https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId={{SEASON_ID}}&gbId=36&pageName=TeamRoster.jsp;teamId={{TEAM_ID}}
'''
    
    try:
        with open('season_config.py', 'w') as f:
            f.write(config_content)
        
        print()
        print("✅ Configuration updated successfully!")
        print()
        print("Next steps:")
        print("1. Test the scraper: python test_scraper.py")
        print("2. Commit changes: git add season_config.py")
        print("3. Commit changes: git commit -m 'Update to {season_name} season'")
        print("4. Push to GitHub: git push origin main")
        print()
        print("Your automated site will use the new season immediately!")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return


if __name__ == "__main__":
    try:
        update_season()
    except KeyboardInterrupt:
        print("\n\n❌ Update cancelled by user.")
        sys.exit(0)
