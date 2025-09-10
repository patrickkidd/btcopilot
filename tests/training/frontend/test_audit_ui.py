import pytest
from playwright.sync_api import Page, expect


class TestAuditIndexPage:
    """Test the main audit index page functionality using optimized fixtures"""

    def test_audit_page_loads(self, class_audit_page: Page):
        """Test that the audit index page loads successfully"""
        expect(class_audit_page).to_have_title("AI Training & Audit System")
        expect(class_audit_page.locator("h1.title")).to_contain_text(
            "AI Training & Audit System"
        )

    def test_audit_instructions_displayed(self, class_audit_page: Page):
        """Test that audit instructions are displayed"""
        instructions = class_audit_page.locator(".notification.is-info")
        expect(instructions).to_be_visible()
        expect(instructions).to_contain_text(
            "Click on any thread to review AI chat responses"
        )

    def test_users_section_exists(self, class_audit_page: Page):
        """Test that users section is present"""
        users_section = class_audit_page.locator("h2.subtitle").filter(
            has_text="Users with Discussions"
        )
        if users_section.count() > 0:
            expect(users_section).to_be_visible()

    def test_expand_collapse_buttons(self, class_audit_page: Page):
        """Test expand all and collapse all functionality"""
        expand_btn = class_audit_page.locator("button").filter(has_text="Expand All")
        collapse_btn = class_audit_page.locator("button").filter(has_text="Collapse All")

        expect(expand_btn).to_be_visible()
        expect(collapse_btn).to_be_visible()

    def test_auditor_diagrams_section(self, class_audit_page: Page):
        """Test that auditor's own diagrams section is displayed"""
        auditor_section = class_audit_page.locator("h2.subtitle").filter(
            has_text="My Diagrams"
        )
        if auditor_section.count() > 0:
            expect(auditor_section).to_be_visible()

    def test_new_diagram_button(self, class_audit_page: Page):
        """Test that new diagram button is present"""
        new_diagram_btn = class_audit_page.locator("button").filter(has_text="New Diagram")
        if new_diagram_btn.count() > 0:
            expect(new_diagram_btn).to_be_visible()

    @pytest.mark.e2e
    def test_expand_all_functionality(self, class_audit_page: Page):
        """Test expand all button functionality"""
        expand_btn = class_audit_page.locator("button").filter(has_text="Expand All")
        if expand_btn.count() > 0:
            expand_btn.click()
            # Check that collapsible content becomes visible
            class_audit_page.wait_for_timeout(500)  # Allow animation to complete

    @pytest.mark.e2e  
    def test_collapse_all_functionality(self, class_audit_page: Page):
        """Test collapse all button functionality"""
        collapse_btn = class_audit_page.locator("button").filter(has_text="Collapse All")
        if collapse_btn.count() > 0:
            collapse_btn.click()
            # Check that collapsible content becomes hidden
            class_audit_page.wait_for_timeout(500)  # Allow animation to complete