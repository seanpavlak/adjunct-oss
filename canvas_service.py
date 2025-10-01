"""
Canvas Service for browser automation and Canvas LMS operations
"""

import time
from typing import List, Optional, Tuple
from playwright.sync_api import Page, Playwright, sync_playwright
from response_generator import ResponseGenerator


class CanvasService:
    """Service class for Canvas LMS operations"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
    def __enter__(self):
        """Context manager entry"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def login(self, email: str, password: str) -> None:
        """Login to Canvas with provided credentials"""
        self.page.goto("https://chcp.instructure.com/login/canvas")
        self.page.wait_for_selector('input#pseudonym_session_unique_id', state='attached')
        self.page.fill('input#pseudonym_session_unique_id', email)
        self.page.fill('input[name="pseudonym_session[password]"]', password)
        self.page.press('input[name="pseudonym_session[password]"]', 'Enter')
        time.sleep(3)  # Wait for login to complete
    
    def extract_content(self, author) -> str:
        """Extract content from a discussion author element"""
        content = ""
        content_containers = author.query_selector_all('span.user_content.enhanced')
        for container in content_containers:
            paragraphs = container.query_selector_all('p')
            for p in paragraphs:
                content += p.text_content().strip() + " "
        return content if content else "Content not found or not loaded."
    
    def _is_browser_alive(self) -> bool:
        """Check if the browser/page is still accessible"""
        try:
            # Try to access a simple property to test if browser is alive
            self.page.url
            return True
        except Exception:
            return False
    
    def process_discussion_authors(self, authors: List, week_id: int, llm_config: dict, course_selector: str = "A") -> bool:
        """Process discussion authors and generate responses
        
        Returns:
            bool: True if processing completed successfully, False if browser was closed
        """
        generator = ResponseGenerator(
            week=week_id,
            course_selector=course_selector,
            provider=llm_config['provider'],
            openai_key=llm_config.get('openai_key', ''),
            anthropic_key=llm_config.get('anthropic_key', ''),
            deepseek_key=llm_config.get('deepseek_key', '')
        )
        
        for author in authors:
            try:
                author_id = author.get_attribute('data-authorid')
                name = author.query_selector('[data-testid="author_name"]').text_content()
                content = self.extract_content(author)
                
                print(f"Author ID: {author_id}, Name: {name}, Content: {content}")
                
                reply_button = author.query_selector('[data-testid="threading-toolbar-reply"]')
                if reply_button:
                    reply_button.click()
                    time.sleep(2)
                    
                    # Generate and type response
                    response = generator.reply(content)
                    self.page.keyboard.type(response)
                else:
                    print("Reply button not found for this author.")
            except Exception as e:
                if "Target page, context or browser has been closed" in str(e):
                    # Browser was closed, return False to signal this
                    return False
                else:
                    print("Error: ", e)
        
        return True
    
    def run_discussion_loop(self, week_id: int, llm_config: dict, course_selector: str = "A") -> None:
        """Run the main discussion processing loop"""
        while True:
            try:
                authors = self.page.query_selector_all('[data-authorid]')
                success = self.process_discussion_authors(authors, week_id, llm_config, course_selector)
                
                # Only show the browser closed message at the natural stopping point
                if not success or not self._is_browser_alive():
                    print("Browser window closed, stopping processing...")
                    return
                
                stop = input("Press 'y' to stop or any other key to continue: ").lower()
                if stop == 'y':
                    break
            except Exception as e:
                if "Target page, context or browser has been closed" in str(e):
                    print("Browser window closed, stopping processing...")
                    return
                else:
                    print(f"Error in discussion loop: {e}")
                    break
    
    def navigate_to_discussion(self, course_id: str, topic_id: str) -> None:
        """Navigate to a specific discussion topic"""
        discussion_url = f"https://chcp.instructure.com/courses/{course_id}/discussion_topics/{topic_id}"
        self.page.goto(discussion_url)
        time.sleep(2)
    
    def create_announcement(self, course_id: str, title: str, content: str, scheduled_date: str) -> bool:
        """Create a single announcement with the given details"""
        # Navigate to new announcement page
        announcement_url = f"https://chcp.instructure.com/courses/{course_id}/discussion_topics/new?is_announcement=true"
        self.page.goto(announcement_url)
        time.sleep(2)
        
        try:
            # Fill in the title
            self.page.get_by_test_id("discussion-topic-title").click()
            self.page.get_by_test_id("discussion-topic-title").fill(title)
            
            # Switch to HTML editor and fill in the content
            self.page.get_by_role("button", name="Switch to the html editor").click()
            self.page.get_by_label("html code editor91", exact=True).click()
            self.page.get_by_label("html code editor91", exact=True).fill(content)
            
            # Set the scheduled date
            self.page.get_by_test_id("announcement-available-from-date").fill(scheduled_date)
            self.page.get_by_test_id("announcement-available-from-date").press("Enter")
            
            # Submit the announcement
            self.page.get_by_test_id("announcement-submit-button").click()
            time.sleep(2)
            
            print(f"✓ Created announcement: '{title}' scheduled for {scheduled_date}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to create announcement '{title}': {e}")
            return False
    
    def schedule_announcements(self, course_id: str, announcements: List[dict], announcement_dates: dict) -> Tuple[int, int]:
        """Schedule multiple announcements for a course"""
        successful_announcements = 0
        failed_announcements = 0
        
        for announcement in announcements:
            week = announcement['week']
            title = announcement['title']
            content = announcement['content']
            scheduled_date = announcement_dates.get(week)
            
            if scheduled_date:
                print(f"\nCreating Week {week} announcement...")
                if self.create_announcement(course_id, title, content, scheduled_date):
                    successful_announcements += 1
                else:
                    failed_announcements += 1
            else:
                print(f"✗ No date calculated for week {week}")
                failed_announcements += 1
        
        return successful_announcements, failed_announcements
