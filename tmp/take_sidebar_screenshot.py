"""Capture the live AI Gateway sidebar to verify the new Coordinator row."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/Volumes/4TB-BAD/HumanAI/CoDRAG/tmp")
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    page.goto("http://localhost:5174/")
    page.wait_for_load_state("domcontentloaded", timeout=15000)
    # Allow the AI Gateway widget to populate from /llm/slots/status (3s poll).
    page.wait_for_timeout(8000)

    # Full screenshot
    page.screenshot(path=str(OUT / "dashboard_full.png"), full_page=False)

    # Sidebar AI Gateway block — try to scope to it
    sidebar = page.locator("text=AI Gateway").first
    if sidebar.count() > 0:
        # screenshot the surrounding container
        try:
            container = sidebar.locator("xpath=ancestor::div[contains(@class,'px-3')][1]")
            container.screenshot(path=str(OUT / "ai_gateway_sidebar.png"))
            print("ai_gateway_sidebar.png written")
        except Exception as e:
            print(f"sidebar crop failed: {e}")

    # Dump rendered slot rows for verification
    rows = page.evaluate("""() => {
        // The expanded view emits slot labels — collect them
        const labels = [];
        document.querySelectorAll('.text-text, .text-text-muted').forEach(el => {
            const t = (el.textContent || '').trim();
            if (['Embedding','Fast Model','Thinking','Coordinator','Code Model'].includes(t)) {
                labels.push(t);
            }
        });
        return [...new Set(labels)];
    }""")
    print("Slot rows found in DOM:", rows)
    browser.close()
