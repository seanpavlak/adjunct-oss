import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.get_by_role("link", name="OL PHYS 100-General Physics-Pavlak(Hybrid-A)-C250902 OL PHYS 100 General").click()
    page.goto("https://chcp.instructure.com/courses/83062/gradebook/speed_grader?assignment_id=3313305")
    page.goto("https://chcp.instructure.com/courses/83062/gradebook/speed_grader?assignment_id=3313305&student_id=90268")
    page.frame_locator("#speedgrader_iframe").locator("#entry_6435205 div").filter(has_text="The metric system isn't").nth(1).click()
    page.frame_locator("#speedgrader_iframe").locator("#entry_6466880 div").filter(has_text="For some of us, high school").nth(1).click()
    page.get_by_role("button", name="View Rubric").click()
    page.get_by_role("button", name="40 pts Exceeds Expectations (").click()
    page.get_by_role("button", name="10 pts Meets Expectations (").click()
    page.get_by_role("button", name="21 pts Needs Improvement (70").click()
    page.get_by_role("button", name="17 pts Meets Expectations (85").click()
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Total Points: 88", exact=True).click()
    page.get_by_label("Grade out of").click()
    page.get_by_label("Grade out of").fill("88")
    page.get_by_label("Grade out of").press("Enter")
    page.frame_locator("iframe[title=\"Rich Text Area\\. Press OPTION\\+F8 for Rich Content Editor shortcuts\\.\"]").get_by_label("Rich Text Area. Press ALT-0").click()
    page.frame_locator("iframe[title=\"Rich Text Area\\. Press OPTION\\+F8 for Rich Content Editor shortcuts\\.\"]").get_by_label("Rich Text Area. Press ALT-0").fill("Please make sure that in the future you are utilizing citations when referencing any factual information and that we are responding to at least 2 separate peers. ")
    page.get_by_role("button", name="Submit").click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
