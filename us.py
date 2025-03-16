# Description: 
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import yaml
from datetime import datetime
import os

def load_config():
    config_path = "/Users/diya/Desktop/Selenium/gov_sesh/config_us.yaml"
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

# Accessing the config file
config = load_config()
chromedriver_path = config["chromedriver_path"]
download_path = config["download_path"]
dates = config["date"]
success_failed_path = config["success_failed_path"]

def get_driver():
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={user_agent}")
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
    service = Service(path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd("Network.enable", {})  # Enable network logging
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": user_agent})
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    return driver

def append_to_json(entry, filename):
    # Load existing data or start a new list
    try:
        with open(os.path.join(success_failed_path, filename), "r") as file:
            event_list = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        event_list = []

    # Append the new entry to the list
    event_list.append(entry)

    # Save the updated list back to the file
    with open(os.path.join(success_failed_path, filename), "w") as file:
        json.dump(event_list, file, indent=4)  

def download_video(driver):

    # Generating url based on date
    date_obj = datetime.strptime(dates, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%Y/%m/%d")
    url = f"https://www.congress.gov/committee-schedule/daily/{formatted_date}"
    
    current_date = datetime.now().strftime("%Y-%m-%d")

    driver.get(url)
    time.sleep(5)
    
    # Get event urls from the session cards
    main_content = driver.find_element(By.CSS_SELECTOR, "article.column-main.main-content[role='article']")
    event_urls = [a.get_attribute("href") for a in main_content.find_elements(By.CSS_SELECTOR, ".schedule-heading.blue a")]
    event_titles = [a.text for a in main_content.find_elements(By.CSS_SELECTOR, ".committee-schedule-section h4")]

    # Downloading videos from the event page
    for i in range(len(event_urls)):

        # Click on the event
        driver.get(event_urls[i])
        time.sleep(5)
        
        # Get the video URL
        if driver.find_elements(By.TAG_NAME, "iframe"):
            youtube_url = driver.find_element(By.TAG_NAME, "iframe").get_attribute("src")
        else:
            youtube_url = None
        if youtube_url:
            try:
                start_time = time.time()
                # Download video using yt-dlp.
                ytdlp_command = [
                    "yt-dlp",
                    "-f", "best",
                    "-o", f"{download_path}{event_titles[i]}.mp4",
                    youtube_url
                ]
                subprocess.run(ytdlp_command)

                # Updating the success list
                entry = {
                    "title": event_titles[i],
                    "recorded_date": dates,
                    "link": url,
                    "last_attempted_scrape_date": current_date
                }
                append_to_json(entry, "success_list.json")

                print(f"Video downloaded successfully! -> {event_titles[i]}")

                end_time = time.time()
                time_taken = (end_time - start_time)/60
                print(f"Time taken to download video: {time_taken:.2f} min")
            
            except subprocess.CalledProcessError as e:
                entry = {
                    "title": event_titles[i],
                    "recorded_date": dates,
                    "link": url,
                    "last_attempted_scrape_date": current_date
                }
                append_to_json(entry, "failed_list.json")              
                print(f"Error downloading video: {e}")
                print(f"Failed to download video! -> {event_titles[i]}")

        else:
            print("No video urls were found in the network logs!")
            entry = {
                "title": event_titles[i],
                "recorded_date": dates,
                "link": url,
                "last_attempted_scrape_date": current_date
            }
            append_to_json(entry, "failed_list.json")    
            print(f"Failed to download video! -> {event_titles[i]}")


def main():
    driver = get_driver()

    download_video(driver)

    driver.quit()

if __name__ == "__main__":
    main()
