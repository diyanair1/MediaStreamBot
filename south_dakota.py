# Description: This script downloads all audios of the sessions on a given range of dates from the South Dakota Assembly website.
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import subprocess
from datetime import datetime, timedelta
import os
import logging
import sys
# from download_helper import move_to_s3

def load_config():
    config_path = "/config_sd.json"
    with open(config_path, "r") as file:
        return json.load(file)

# Accessing the config file
config = load_config()
download_dir = config["output_path"]
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

def format_date(date):
    # Convert the string to a datetime object
    date_obj = datetime.strptime(date, "%Y-%m-%d")

    # Format the date to "DD-MM-YYYY"
    formatted_date = date_obj.strftime("%d/%m/%Y")
    return formatted_date

def format_title(title, details, date):
    dt = datetime.strptime(details, "%m/%d %I:%M %p")       # Parse the date and time string
    formatted_time = dt.strftime("%H-%M")         # Format to HH-MM (24-hour format)

    # Combine everything to create the title
    video_title = f"{date}_{formatted_time}_{title.replace(' ', '_')}.mp4"

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
    
    current_date = datetime.now().strftime("%Y-%m-%d")

    driver.get("https://sdlegislature.gov/Session/Committee/1231/Minutes")
    time.sleep(3)
    logger.info("Loaded main committee page")

    # Get committee urls and respective titles
    committee_urls = [a.get_attribute("href") for a in driver.find_elements(By.CSS_SELECTOR, "div.v-list.hidden-sm-and-down.v-sheet.theme--light.v-list--dense a")]
    committee_titles = [a.text for a in driver.find_elements(By.CSS_SELECTOR, "div.v-list.hidden-sm-and-down.v-sheet.theme--light.v-list--dense a div.v-list-item__title")]

    date_list = get_date_range()
    logger.info(f"Generated date range: {date_list}")

    for i in range(len(committee_urls)):

        for date in date_list:
            logger.info(f"Fetching videos for {committee_titles[i]} on {date}")

            # Navigating to specific committee page
            driver.get(committee_urls[i])
            time.sleep(3)

            # Click "Journals & Audio" tab
            wrapper = driver.find_elements(By.CSS_SELECTOR, "div.v-slide-group__wrapper a")[2]
            wrapper.click()
            time.sleep(3)

            # Filter by date
            formatted_date = format_date(date)
            filter = driver.find_element(By.CSS_SELECTOR, "input[placeholder='Filter']")
            filter.send_keys(formatted_date)
            time.sleep(3)

            # Fetching audio urls and audio details
            try:
                if driver.find_elements(By.CSS_SELECTOR, "tbody tr[class='v-data-table__empty-wrapper']"):
                    logger.info(f"No events found for the given date for {committee_titles[i]}")
                    continue
                else:
                    tr_class = driver.find_elements(By.CSS_SELECTOR, "tbody tr[class='']")

                    # Fetching audio urls
                    audio_urls = []
                    for tr in tr_class:
                        if tr.find_elements(By.CSS_SELECTOR, "a[aria-label='SDPB Audio']"):
                            audio_urls.append(tr.find_element(By.CSS_SELECTOR, "a[aria-label='SDPB Audio']").get_attribute("href"))
                        else:
                            audio_urls.append("No audio found")
                    
                    # Fetching audio details
                    audio_details = []
                    for tr in tr_class:
                        audio_details.append(tr.find_elements(By.CSS_SELECTOR, "td[class='text-start']")[0].text)

                    # Downloading audios from the event page
                    for j in range(len(audio_urls)):
                        formatted_title = format_title(committee_titles[i], audio_details[j], date)
                        if audio_urls[j] != "No audio found":
                                
                            entry = {
                                "title": formatted_title,
                                "recorded_date": date,
                                "link": audio_urls[j],
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
                                    # Download audio using yt-dlp.
                                    ytdlp_command = [
                                        "yt-dlp",
                                        "-f", "best",
                                        "-o", f"{download_dir}{formatted_title}.mp3",
                                        audio_urls[j]
                                    ]
                                    subprocess.run(ytdlp_command)

                                    # Determining Category
                                    if "Senate" in committee_titles[i]:
                                        category = "senate"
                                    elif "House" in committee_titles[i]:
                                        category = "house"
                                    elif "Joint" in committee_titles[i]:
                                        category = "joint"
                                    else:
                                        category = "unknown"   # default

                                    # Determining Session type
                                    if "Committee" in committee_titles[i]:
                                        session_type = "committee"
                                    elif "Hearing" in committee_titles[i]:
                                        session_type = "hearing"
                                    else:
                                        session_type = "session"                                    
                                    
                                    # move_to_s3("south dakota", formatted_title, category, session_type, url=audio_urls[j])
                                    # print(f"CATEGORY= {category}")
                                    # print(f"SESSION TYPE= {session_type}")

                                    # Updating the success list
                                    append_to_json(entry, success_path)

                                    logger.info(f"\nAudio downloaded successfully! -> {formatted_title}")

                                    end_time = time.time()
                                    time_taken = (end_time - start_time)/60
                                    logger.info(f"Time taken to download audio: {time_taken:.2f} min\n")


                                
                                except subprocess.CalledProcessError as e:
                                    entry = {
                                        "title": formatted_title,
                                        "recorded_date": date,
                                        "link": audio_urls[j],
                                        "last_attempted_scrape_date": current_date
                                    }
                                    append_to_json(entry, failed_path)              
                                    logger.info(f"\nError downloading audio: {e}")
                                    logger.info(f"Failed to download audio! -> {formatted_title}\n")
                        else:
                            continue  

            except Exception as e:
                logger.info(f"\nEncountered error while fetching audio urls and details: {e}\n")
                continue


def main():
    driver = get_driver()

    download_video(driver)

    driver.quit()

if __name__ == "__main__":
    main()