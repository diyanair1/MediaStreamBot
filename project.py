from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.action_chains import ActionChains
import json
import os
# import yt_dlp

# Setting up chrome webdriver
service = Service(path = "/Users/diya/Desktop/Selenium/chromedriver-mac-arm64")
driver = webdriver.Chrome(service=service)

# Setting up bs4
URL = "http://www.jefrench.com/basic-french-lessons/"
page = requests.get(URL)
soup = BeautifulSoup(page.content, "html.parser")

video_urls = [] 
titles = set()   # Using sets to avoid duplicates

# Open main page
driver.get("http://www.jefrench.com/basic-french-lessons/")

# Get all title elements first
WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, ".menu-basic-french-lessons-container li.menu-item a"))
)

title_elements = driver.find_elements(By.CSS_SELECTOR, ".menu-basic-french-lessons-container li.menu-item a") # . for class

# Store the href values
title_links = []
for title_element in title_elements:
    title_links.append(title_element.get_attribute('href'))
    titles.add(title_element.text.strip())

# Pops last elements from title_links
title_links.pop()
title_links.pop()
title_links.pop()
title_links.pop()
title_links.pop()
title_links.pop()

# Navigate to each link directly
for title_link in title_links:
    try:
        driver.get(title_link)
        print(f"Navigating to: {title_link} ...")

        try:

            # Wait for page to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "video"))
            )

            video_element = driver.find_element(By.TAG_NAME, "video")

            # Click the video to start playing
            try:
                wrapper = video_element.find_element(By.XPATH, "./parent::*")  # Get the video wrapper
                ActionChains(driver).move_to_element(wrapper).click().perform()
                print(f"Clicked wrapper to play video: {video_element.get_attribute('id')}")
            except:
                ActionChains(driver).move_to_element(video_element).click().perform()
                print(f"Clicked video to play: {video_element.get_attribute('id')}")

            # Use JavaScript to ensure video starts playing
            driver.execute_script("arguments[0].play();", video_element)

            # Wait for video `src` to be available
            WebDriverWait(driver, 10).until(lambda d: video_element.get_attribute('src'))
            video_src = video_element.get_attribute('src')

            if video_src:
                video_urls.append(video_src)
                print(f"Found video source: {video_src}")
            else:
                print(f"No video source found for: {video_element.get_attribute('id')}")
                video_urls.append("no links")

        except:
            video_urls.append("no links")
        
        # Ensure video_urls and titles have the same length
        video_data = []
        for title, url in zip(titles, video_urls):
            video_entry = {"title": title, "video_url": url}
            video_data.append(video_entry)

        # Define the filenames
        filename = "video_data.json"
        video_folder = "downloaded_videos"

        # Create folder if it doesn't exist
        if not os.path.exists(video_folder):
            os.makedirs(video_folder)

        # Write to a JSON file
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(video_data, f, indent=4, ensure_ascii=False)

        print(f"JSON file '{filename}' has been created successfully.")

        for title, url in zip(titles, video_urls):
            if url and url.lower() != "no links":
                try:
                    response = requests.get(url, stream=True)
                    response.raise_for_status()   # Raise an exception for 4xx/5xx errors
                    
                    safe_title = "_".join(title.split())  # Replace spaces with underscores
                    file_path = os.path.join(video_folder, f"{safe_title}.mp4")
                    
                    with open(file_path, "wb") as video_file:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                video_file.write(chunk)
                    
                    print(f"Downloaded: {file_path}")
                except requests.exceptions.RequestException as e:
                    print(f"Failed to download {title}: {e}")


    except Exception as e:
        print(f"Error processing: {title_link}: {e}")
        # Continue with the next link

quit()
