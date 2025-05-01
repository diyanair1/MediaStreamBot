# Description: This script downloads all videos of the sessions on a given range of dates from the US Congress Assembly website.
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import os
import logging
import sys
from datetime import datetime, timedelta
# from download_helper import move_to_s3

def load_config():
    config_path = "/config_us.json"
    with open(config_path, "r") as file:
        return json.load(file)

# Accessing the config file
config = load_config()
download_path = config["output_path"]
start_date = config["start_date"]
end_date = config["end_date"]
failed_path = config["failed_download_json_path"]
success_path = config["success_download_json_path"]
log_path = config["log_path"]

# Set up logging
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

logger = logging.getLogger()
logger.info("Starting South Dakota Assembly audio scraper")

def get_driver():
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--headless")  # Uncomment for headless operation
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

def format_title(title, date):
    # Combine everything to create the title
    video_title = f"{date}_00-00_{title.replace(' ', '_')}.mp4"

    return video_title    # YYYY-MM-DD_HH-MM_The_Title_of_Video.mp4

def get_date_range():
    # Generate a list of dates between start_date and end_date (inclusive).
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    date_list = []
    current_date = start

    while current_date <= end:
        date_list.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    return date_list

def download_video(driver):

    date_list = get_date_range()

    for date in date_list:
        logger.info(f"Fetching videos for {date}")

        # Generating url based on date
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y/%m/%d")
        url = f"https://www.congress.gov/committee-schedule/daily/{formatted_date}"
        
        current_date = datetime.now().strftime("%Y-%m-%d")

        driver.get(url)
        time.sleep(5)
        
        # Get event urls from the session cards
        main_content = driver.find_element(By.CSS_SELECTOR, "article.column-main.main-content[role='article']")
        event_urls = [a.get_attribute("href") for a in main_content.find_elements(By.CSS_SELECTOR, ".schedule-heading.blue a")]
        event_titles = [a.text for a in main_content.find_elements(By.CSS_SELECTOR, ".committee-schedule-section h4")]
        event_type = [a.text for a in main_content.find_elements(By.CSS_SELECTOR, ".committee-schedule-section h3")]

        # Downloading videos from the event page
        for i in range(len(event_urls)):
            formatted_title = format_title(event_titles[i], date)
            # Click on the event
            driver.get(event_urls[i])
            time.sleep(5)
            
            # Get the video URL
            if driver.find_elements(By.TAG_NAME, "iframe"):
                youtube_url = driver.find_element(By.TAG_NAME, "iframe").get_attribute("src")
            else:
                youtube_url = None
            if youtube_url:
                    # Check for duplicates
                    entry = {
                        "title": formatted_title,
                        "recorded_date": date,
                        "link": youtube_url,
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
                        # Download the audio
                        try:
                            start_time = time.time()
                            # Download video using yt-dlp.
                            ytdlp_command = [
                                "yt-dlp",
                                "-f", "best",
                                "-o", f"{download_path}{formatted_title}.mp4",
                                youtube_url
                            ]
                            subprocess.run(ytdlp_command)

                            # Determining Category
                            if "senate" in event_type[i].lower():
                                category = "senate"
                            elif "house" in event_type[i].lower():
                                category = "house"
                            elif "joint" in event_type[i].lower():
                                category = "joint"
                            else:
                                category = "unknown"   # default

                            # Determining Session type
                            if "committee" in event_type[i].lower():
                                session_type = "committee"
                            elif "hearing" in event_type[i].lower():
                                session_type = "hearing"
                            else:
                                session_type = "session"     # default 

                            # move_to_s3("us congress", formatted_title, category, session_type, url=youtube_url)
                            
                            # Updating the success list
                            append_to_json(entry, success_path)

                            logger.info(f"Video downloaded successfully! -> {formatted_title}")

                            end_time = time.time()
                            time_taken = (end_time - start_time)/60
                            logger.info(f"Time taken to download video: {time_taken:.2f} min")
                        
                        except subprocess.CalledProcessError as e:
                            entry = {
                                "title": formatted_title,
                                "recorded_date": date,
                                "link": youtube_url,
                                "last_attempted_scrape_date": current_date
                            }
                            append_to_json(entry, failed_path)              
                            logger.info(f"Error downloading video: {e}")
                            logger.info(f"Failed to download video! -> {formatted_title}")

            else:
                logger.info("No video urls were found!")
                entry = {
                    "title": formatted_title,
                    "recorded_date": date,
                    "link": "Not Found",
                    "last_attempted_scrape_date": current_date
                }
                append_to_json(entry, failed_path)    
                logger.info(f"Failed to download video! -> {formatted_title}")


def main():
    driver = get_driver()

    download_video(driver)

    driver.quit()

if __name__ == "__main__":
    main()
