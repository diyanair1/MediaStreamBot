# MediaStreamBot

**MediaStreamBot** is an automated web scraper that extracts and downloads session recordings from U.S. government state legislature websites. Designed for use with sessions from **North Dakota**, **South Dakota**, **West Virginia**, and **U.S. Congress**, this bot retrieves video metadata and downloads recordings to AWS S3 bucket based on date filters.

---

## Features

- Filter sessions by **start** and **end** date  
- Automatically download `.m3u8` stream recordings via `ffmpeg`  
- Maintain logs of **successful** and **failed** downloads  
- 🔍 Bypass common anti-bot mechanisms using `Selenium` and `Chrome DevTools Protocol`  
