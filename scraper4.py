from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import psycopg2
import sys
import time
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException, StaleElementReferenceException

# Database configuration
DB_HOST = "localhost"
DB_NAME = "data_scrap"
DB_USER = "postgres"
DB_PASSWORD = "password"
DB_PORT = "5432"

def setup_driver():
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()  # Ensure all elements are visible
        return driver
    except WebDriverException as e:
        print(f"Failed to initialize WebDriver: {str(e)}")
        sys.exit(1)

def create_feedback_table(conn):
    """Create the feedback table if it doesn't exist"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    feedback_rating VARCHAR(20),
                    comment TEXT,
                    date VARCHAR(50),
                    left_by VARCHAR(100),
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error creating table: {e}")
        conn.rollback()

def insert_feedback(conn, feedback_data):
    """Insert feedback data into the database"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO feedback (feedback_rating, comment, date, left_by)
                VALUES (%s, %s, %s, %s)
            """, feedback_data)
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error inserting feedback: {e}")
        conn.rollback()

def scrape_current_page(driver, conn):
    """Scrape all feedback items on the current page"""
    feedback_items = []
    i = 1
    
    while True:
        try:
            # Construct XPaths - these might need adjustment based on actual page structure
            xpath_base = f'/html/body/main/div/div[1]/div/div[1]/div[4]/div/div/div[2]/div[2]/div[2]/div[{i}]'
            xpath_left_by = f'{xpath_base}/div[3]/div[2]/p'
            xpath_feedback = f'{xpath_base}/div[1]/span'
            xpath_comments = f'{xpath_base}/div[2]/div'
            xpath_dates = f'{xpath_base}/div[4]'

            # Find elements with timeout
            feedback_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath_feedback))
            )
            comment_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath_comments))
            )
            date_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath_dates))
            )
            left_by_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath_left_by))
            )

            # Extract data
            feedback = feedback_element.get_attribute("title") or feedback_element.text
            comment = comment_element.text
            date = date_element.text
            left_by = left_by_element.text.split("\n")[1] if "\n" in left_by_element.text else left_by_element.text

            print(f'Feedback {i}: {feedback}, Comment: {comment[:30]}..., Date: {date}, Left by: {left_by}')

            # Store in database
            insert_feedback(conn, (feedback, comment, date, left_by))
            
            feedback_items.append({
                'feedback': feedback,
                'comment': comment,
                'date': date,
                'left_by': left_by
            })
            
            i += 1

        except TimeoutException:
            print(f"No more feedback entries found on this page at index {i}")
            break
        except StaleElementReferenceException:
            print(f"Stale element reference at index {i}, retrying...")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"Error processing feedback {i}: {str(e)}")
            i += 1
            continue
    
    return feedback_items

def go_to_next_page(driver):
    """Attempt to navigate to the next page of feedback"""
    max_attempts = 3
    attempts = 0
    
    while attempts < max_attempts:
        try:
            # Scroll to bottom to ensure pagination controls are visible
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Try different ways to find the next button
            next_buttons = driver.find_elements(By.XPATH, '//a[contains(@class, "page-link") and contains(text(), "Next")]')
            
            if not next_buttons:
                next_buttons = driver.find_elements(By.XPATH, '//a[contains(text(), "Next")]')
            
            if not next_buttons:
                next_buttons = driver.find_elements(By.XPATH, '//li[contains(@class, "next")]/a')
            
            if not next_buttons:
                print("No next page button found")
                return False
                
            next_button = next_buttons[0]
            
            # Check if button is clickable
            if next_button.is_enabled() and next_button.is_displayed():
                # Use JavaScript click to avoid element interception issues
                driver.execute_script("arguments[0].click();", next_button)
                time.sleep(3)  # Wait for page to load
                
                # Verify we actually moved to a new page
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "feedback-item")]'))
                )
                return True
            else:
                print("Next button is not clickable")
                return False
                
        except Exception as e:
            attempts += 1
            print(f"Attempt {attempts} to go to next page failed: {str(e)}")
            time.sleep(2)
    
    print(f"Failed to go to next page after {max_attempts} attempts")
    return False

def main():
    try:
        # Initialize WebDriver
        driver = setup_driver()
        driver.get("url/ website link")
        
        # Connect to PostgreSQL database
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            print("Database connection established successfully")
        except psycopg2.Error as e:
            print(f"Database connection failed: {e}")
            driver.quit()
            sys.exit(1)
        
        # Create table if not exists
        create_feedback_table(conn)
        
        page_number = 1
        max_pages = 10  # Safety limit to prevent infinite loops
        
        while page_number <= max_pages:
            print(f"\nScraping page {page_number}")
            feedback_items = scrape_current_page(driver, conn)
            
            if not feedback_items:
                print("No feedback items found on this page")
                break
                
            if not go_to_next_page(driver):
                print("No more pages available")
                break
                
            page_number += 1

    finally:
        # Clean up resources
        if 'conn' in locals():
            conn.close()
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    main()