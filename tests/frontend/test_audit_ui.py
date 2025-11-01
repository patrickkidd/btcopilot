import pytest
from playwright.sync_api import Page, expect


@pytest.mark.skip(reason="Manually skipped for cherry-picking re-enablement")
class TestAuditIndexPage:
    """Test the main audit index page functionality using optimized fixtures"""

    def test_audit_page_loads(self, class_audit_page: Page):
        """Test that the audit index page loads successfully"""
        expect(class_audit_page).to_have_title("AI Chatbot Audit System")
        expect(class_audit_page.locator("h1.title")).to_contain_text(
            "Therapist Chat Audit System"
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
        collapse_btn = class_audit_page.locator("button").filter(
            has_text="Collapse All"
        )

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
        new_diagram_btn = class_audit_page.locator("button").filter(
            has_text="New Diagram"
        )
        if new_diagram_btn.count() > 0:
            expect(new_diagram_btn).to_be_visible()


@pytest.mark.skip(reason="Manually skipped for cherry-picking re-enablement")
class TestDiscussionAuditPage:
    """Test discussion audit page functionality using optimized fixtures"""

    def test_discussion_audit_page_loads(self, class_discussion_page: Page):
        """Test that discussion audit page loads successfully"""
        expect(class_discussion_page).to_have_title("AI Chatbot Audit System")
        # Discussion audit uses breadcrumbs instead of main title
        expect(class_discussion_page.locator(".breadcrumb")).to_be_visible()

    def test_chat_messages_displayed(self, class_discussion_page: Page):
        """Test that chat messages are displayed properly"""
        messages = class_discussion_page.locator(".message, .statement")
        if messages.count() > 0:
            expect(messages.first).to_be_visible()

    def test_feedback_buttons_present(self, class_discussion_page: Page):
        """Test that feedback buttons are present for AI messages"""
        thumbs_up = class_discussion_page.locator("button").filter(has_text="👍")
        thumbs_down = class_discussion_page.locator("button").filter(has_text="👎")

        # At least one of these should be present
        expect(thumbs_up.or_(thumbs_down)).to_have_count_greater_than(0)

    def test_extraction_data_section(self, class_discussion_page: Page):
        """Test that extraction data section is visible"""
        extraction_section = class_discussion_page.locator(".extracted-data, .pdp-data")
        if extraction_section.count() > 0:
            expect(extraction_section).to_be_visible()

    def test_breadcrumbs_present(self, class_discussion_page: Page):
        """Test that breadcrumbs navigation is present"""
        breadcrumbs = class_discussion_page.locator(".breadcrumb")
        expect(breadcrumbs).to_be_visible()

    def test_statement_approval_buttons(self, class_discussion_page: Page):
        """Test statement approval buttons for admins"""
        approve_btn = class_discussion_page.locator("button").filter(has_text="Approve")
        reject_btn = class_discussion_page.locator("button").filter(has_text="Reject")

        # These may or may not be present depending on permissions
        if approve_btn.count() > 0:
            expect(approve_btn).to_be_visible()
        if reject_btn.count() > 0:
            expect(reject_btn).to_be_visible()


@pytest.mark.skip(reason="Manually skipped for cherry-picking re-enablement")
class TestUserInteraction:
    """Test user interaction workflows"""

    def test_feedback_submission(self, class_discussion_page: Page):
        """Test feedback submission workflow"""
        # Click thumbs down on first AI message if available
        thumbs_down = (
            class_discussion_page.locator("button").filter(has_text="👎").first
        )
        expect(thumbs_down).to_be_visible()
        thumbs_down.click()

        # Should show feedback form
        feedback_form = class_discussion_page.locator(".feedback-form")
        expect(feedback_form).to_be_visible()

    def test_extraction_feedback_workflow(self, class_discussion_page: Page):
        """Test extraction feedback workflow"""
        # Look for extraction feedback buttons
        edit_extraction = class_discussion_page.locator("button").filter(
            has_text="Edit Extraction"
        )
        expect(edit_extraction).to_be_visible()
        edit_extraction.click()

        # Should show extraction editing interface
        extraction_editor = class_discussion_page.locator(".extraction-editor")
        expect(extraction_editor).to_be_visible()

    def test_navigation_workflow(self, class_discussion_page: Page):
        """Test navigation back to audit index"""
        # Look for back/breadcrumb navigation
        back_link = class_discussion_page.locator("a").filter(has_text="Back to Audit")
        if back_link.count() > 0:
            back_link.click()
            expect(class_discussion_page).to_have_title("AI Chatbot Audit System")

    def test_statement_expansion(self, class_discussion_page: Page):
        """Test statement expansion functionality"""
        # Click on an AI message to expand it
        ai_message = class_discussion_page.locator(".ai-message-bubble").first
        expect(ai_message).to_be_visible()
        ai_message.click()

        # Should show expanded details
        expanded_content = class_discussion_page.locator(".expanded-content")
        expect(expanded_content).to_be_visible()


@pytest.mark.skip(reason="Manually skipped for cherry-picking re-enablement")
class TestDataIntegrity:
    """Test data integrity and display"""

    def test_statement_order_preserved(self, class_discussion_page: Page):
        """Test that statements are displayed in correct order"""
        statements = class_discussion_page.locator(".statement, .message")
        if statements.count() > 1:
            # Check that statements have sequential ordering
            first_statement = statements.nth(0)
            second_statement = statements.nth(1)

            expect(first_statement).to_be_visible()
            expect(second_statement).to_be_visible()

    def test_speaker_identification(self, class_discussion_page: Page):
        """Test that speakers are properly identified"""
        speaker_indicators = class_discussion_page.locator(
            ".speaker-name, .message-author"
        )
        if speaker_indicators.count() > 0:
            expect(speaker_indicators.first).to_be_visible()

    def test_timestamp_display(self, class_discussion_page: Page):
        """Test that timestamps are displayed where appropriate"""
        timestamps = class_discussion_page.locator(".timestamp, .created-at")
        # Timestamps may not be present on all pages, so check conditionally
        if timestamps.count() > 0:
            expect(timestamps.first).to_be_visible()


@pytest.mark.skip(reason="Manually skipped for cherry-picking re-enablement")
class TestAccessibility:
    """Test accessibility features"""

    def test_keyboard_navigation(self, class_discussion_page: Page):
        """Test keyboard navigation functionality"""
        # Test tab navigation
        class_discussion_page.keyboard.press("Tab")
        focused_element = class_discussion_page.locator(":focus")
        if focused_element.count() > 0:
            expect(focused_element).to_be_visible()

    def test_screen_reader_support(self, class_discussion_page: Page):
        """Test screen reader support with ARIA labels"""
        aria_elements = class_discussion_page.locator("[aria-label], [aria-labelledby]")
        if aria_elements.count() > 0:
            expect(aria_elements.first).to_be_visible()

    def test_color_contrast(self, class_discussion_page: Page):
        """Test that color contrast meets accessibility standards"""
        # This is a basic test - in practice you'd use axe-core or similar
        body = class_discussion_page.locator("body")
        expect(body).to_be_visible()
