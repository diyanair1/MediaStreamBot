# Description: This script downloads all audios of the sessions on a given range of dates from the West Virginia Assembly website.
import time
import json
import re
import os
import sys
import logging
import subprocess
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# from download_helper import move_to_s3


# Configuration functions
def load_config():
    config_path = "/config_wv.json"
    with open(config_path, "r") as file:
        return json.load(file)


# Logging setup
def setup_logging(log_path):
    logging.basicConfig(
        filename=log_path, 
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='w',  # Overwrite log file on each run
        force=True      # Ensure no old handlers interfere
    )

    # Ensure logs also print to console in real-time
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(console_handler)
    
    return logging.getLogger()


# Selenium setup
def get_driver():
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={user_agent}")
    # options.add_argument("--headless = new")  # Uncomment for headless operation
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--ignore-certificate-errors')
    # maximize window
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Set performance logging capabilities directly on the options
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    # Setting up Chrome WebDriver
    service = Service(path="/chromedriver-mac-arm64")
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd("Network.enable", {})  # Enable network logging
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": user_agent})
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    return driver


# Helper functions
def append_to_json(entry, respective_path):
    # Load existing data or start a new list
    try:
        with open(respective_path, "r") as file:
            event_list = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        event_list = []

    # Append the new entry to the list
    event_list.append(entry)

    # Save the updated list back to the file
    with open(respective_path, "w") as file:
        json.dump(event_list, file, indent=4)


def format_date(audio_date):
    # Remove the 'th' (or 'st', 'nd', 'rd') using regex
    clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', audio_date)

    # Parse the cleaned string into a datetime object
    date_object = datetime.strptime(clean_date, "%b %d, %Y, %I:%M %p")

    # Format to "YYYY-MM-DD"
    formatted_audio_date = date_object.strftime("%Y-%m-%d")
    return formatted_audio_date


def format_title(title, time, date):
    # Remove ordinal suffix like '17th', '1st', '2nd', '3rd'
    time_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", time)
    
    # Parse the cleaned date string
    dt = datetime.strptime(time_str, "%b %d, %Y, %I:%M %p")
    
    # Convert to HH-MM format (24-hour time)
    formatted_time = dt.strftime("%H-%M")
    
    # Combine everything to create the title
    video_title = f"{date}_{formatted_time}_{title.replace(' ', '_')}.mp4"

    return video_title    # YYYY-MM-DD_HH-MM_The_Title_of_Video.mp4


def get_date_range(start_date, end_date):
    # Generate a list of dates between start_date and end_date (inclusive).
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    date_list = []
    current_date = start

    while current_date <= end:
        date_list.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    return date_list


# Main scraping function
def download_video(driver, download_dir, start_date, end_date, success_path, failed_path, logger):
    date_list = get_date_range(start_date, end_date)    # Get date range
    current_date = datetime.now().strftime("%Y-%m-%d")

    driver.get("https://home.wvlegislature.gov/archived-recordings/")
    time.sleep(3)
    
    # Get audio urls from the audio cards
    main_content = driver.find_element(By.CSS_SELECTOR, "tbody")
    audio_urls = [a.get_attribute("src") for a in main_content.find_elements(By.CSS_SELECTOR, "tr source")]
    audio_titles = [a.text for a in main_content.find_elements(By.CSS_SELECTOR, "tr td:nth-child(2)")]
    audio_dates = [a.text for a in main_content.find_elements(By.CSS_SELECTOR, "tr td div:nth-child(1)")]

    for i in range(len(audio_dates)):
        audio_date = format_date(audio_dates[i])   # Get specific audio date from audio cards

        if audio_date in date_list:
            formatted_title = format_title(audio_titles[i], audio_dates[i], audio_date)
            # Download the audio
            entry = {
                "title": formatted_title,
                "recorded_date": audio_date,
                "link": audio_urls[i],
                "last_attempted_scrape_date": current_date
            }            
                            
            with open(success_path, "r") as file:
                success_list = json.load(file)

            # Check if the title already exists in success_list
            title_exists = any(existing_event["title"] == entry["title"] for existing_event in success_list)

            if title_exists:
                logger.info(f"The event '{entry['title']}' has already been downloaded. Skipping download.")

            else:
                logger.info(f"Downloading event '{entry['title']}'...")            
                try:
                    start_time = time.time()
                    # Download audio using yt-dlp.
                    ytdlp_command = [
                        "yt-dlp",
                        "-f", "best",
                        "-o", f"{download_dir}{formatted_title}.mp3",
                        audio_urls[i]
                    ]
                    subprocess.run(ytdlp_command)

                    # Determining Session type
                    if "committee" in audio_titles[i].lower():
                        session_type = "committee"
                    elif "hearing" in audio_titles[i].lower():
                        session_type = "hearing"
                    else:
                        session_type = "session"     # default 

                    # move_to_s3("west virginia", formatted_title, category="house", session_type, url=audio_urls[i]) 

                    # Updating the success list
                    append_to_json(entry, success_path)

                    logger.info(f"Audio downloaded successfully! -> {formatted_title}")

                    end_time = time.time()
                    time_taken = (end_time - start_time)/60
                    logger.info(f"Time taken to download audio: {time_taken:.2f} min")
                
                except subprocess.CalledProcessError as e:
                    entry = {
                        "title": formatted_title,
                        "recorded_date": audio_date,
                        "link": audio_urls[i],
                        "last_attempted_scrape_date": current_date
                    }
                    append_to_json(entry, failed_path)              
                    logger.info(f"Error downloading audio: {e}")
                    logger.info(f"Failed to download audio! -> {formatted_title}")
        else:
            continue


# Main execution
def main():
    # Load configuration
    config = load_config()
    download_dir = config["output_path"]
    start_date = config["start_date"]
    end_date = config["end_date"]
    failed_path = config["failed_download_json_path"]
    success_path = config["success_download_json_path"]
    log_path = config["log_path"]
    
    # Set up logging
    logger = setup_logging(log_path)
    logger.info("Starting West Virginia Assembly audio scraper")
    
    # Initialize webdriver
    driver = get_driver()
    
    # Run the main scraping function
    download_video(driver, download_dir, start_date, end_date, success_path, failed_path, logger)
    logger.info(f"Finished downloading all videos for given range of dates.")
    
    # Clean up
    driver.quit()


if __name__ == "__main__":
    main()