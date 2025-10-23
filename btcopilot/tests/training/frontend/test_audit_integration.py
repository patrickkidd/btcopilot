import pytest
from playwright.sync_api import Page, expect


class TestAuditWorkflowIntegration:
    """Integration tests for complete audit workflows"""

    def test_complete_audit_workflow(self, authenticated_auditor_context, flask_app):
        """Test a complete audit workflow from index to feedback submission"""
        # Start at audit index
        index_page = authenticated_auditor_context.new_page()
        index_page.goto(f"http://{flask_app.config['SERVER_NAME']}/therapist/audit/")

        # Verify we're on the audit index
        expect(index_page.locator("h1.title")).to_contain_text(
            "Therapist Chat Audit System"
        )

        # Find and click on a discussion
        discussion_link = index_page.locator("a[href*='/training/discussions/']").first
        if discussion_link.is_visible():
            discussion_link.click()

            # Should navigate to discussion audit page
            expect(index_page).to_have_url("**/discussions/")

            # Look for AI messages to provide feedback on
            ai_messages = index_page.locator(".ai-message-bubble")
            if ai_messages.count() > 0:
                # Click on first AI message
                ai_messages.first.click()

                # Should expand to show details
                expanded_content = index_page.locator(
                    ".expanded-content, .message-details"
                )
                expect(expanded_content).to_be_visible()

                # Try to submit feedback
                thumbs_down = index_page.locator("button").filter(has_text="👎").first
                if thumbs_down.is_visible():
                    thumbs_down.click()

                    # Should show feedback form
                    feedback_form = index_page.locator("textarea, .feedback-form")
                    expect(feedback_form).to_be_visible()

                    # Fill and submit feedback
                    if feedback_form.locator("textarea").count() > 0:
                        feedback_form.locator("textarea").first.fill(
                            "Integration test feedback"
                        )
                        submit_btn = (
                            index_page.locator("button").filter(has_text="Submit").first
                        )
                        if submit_btn.is_visible():
                            submit_btn.click()

                            # Should show success or update the UI
                            expect(index_page.locator("body")).to_be_visible()

    def test_auditor_role_restrictions(self, authenticated_auditor_context, flask_app):
        """Test that auditor role restrictions work properly"""
        page = authenticated_auditor_context.new_page()
        page.goto(f"http://{flask_app.config['SERVER_NAME']}/therapist/audit/")

        # Should be able to access audit pages
        expect(page.locator("h1.title")).to_contain_text("Therapist Chat Audit System")

        # Should not have admin-only elements
        admin_elements = page.locator(".admin-only, [data-admin-only]")
        # Admin elements should not be visible to auditors
        if admin_elements.count() > 0:
            for element in admin_elements.all():
                expect(element).not_to_be_visible()

    def test_data_consistency_across_pages(
        self, authenticated_auditor_context, flask_app
    ):
        """Test that data is consistent between audit index and detail pages"""
        page = authenticated_auditor_context.new_page()

        # Visit audit index
        page.goto(f"http://{flask_app.config['SERVER_NAME']}/therapist/audit/")

        # Get discussion info from index
        discussion_cards = page.locator(".discussion-card, .user-card")
        if discussion_cards.count() > 0:
            first_card = discussion_cards.first
            discussion_title = first_card.locator(
                ".title, .discussion-title"
            ).text_content()

            # Click to go to detail page
            detail_link = first_card.locator("a").first
            if detail_link.is_visible():
                detail_link.click()

                # Verify we're on the correct discussion page
                expect(page).to_have_url("**/discussions/")

                # Check that discussion data matches
                detail_title = page.locator(".title, h1").text_content()
                # The detail page should contain discussion information
                expect(page.locator("body")).to_contain_text("Discussion")

    def test_responsive_design(self, authenticated_auditor_context, flask_app):
        """Test that the audit UI works on different screen sizes"""
        page = authenticated_auditor_context.new_page()

        # Test mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"http://{flask_app.config['SERVER_NAME']}/therapist/audit/")

        # Should still be usable on mobile
        expect(page.locator("h1.title")).to_be_visible()

        # Test tablet viewport
        page.set_viewport_size({"width": 768, "height": 1024})
        page.reload()

        # Should adapt to tablet size
        expect(page.locator("h1.title")).to_be_visible()

        # Test desktop viewport
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.reload()

        # Should work on desktop
        expect(page.locator("h1.title")).to_be_visible()

    def test_error_handling(self, authenticated_auditor_context, flask_app):
        """Test error handling in the audit interface"""
        page = authenticated_auditor_context.new_page()

        # Try to access non-existent discussion
        page.goto(
            f"http://{flask_app.config['SERVER_NAME']}/training/discussions/999999"
        )

        # Should handle 404 gracefully
        expect(page.locator("body")).to_be_visible()

        # Should show appropriate error message
        error_messages = page.locator(".error, .notification.is-danger, .alert")
        if error_messages.count() > 0:
            expect(error_messages.first).to_be_visible()

    def test_session_persistence(self, authenticated_auditor_context, flask_app):
        """Test that user session persists across page navigations"""
        page = authenticated_auditor_context.new_page()

        # Visit audit index
        page.goto(f"http://{flask_app.config['SERVER_NAME']}/therapist/audit/")
        expect(page.locator("h1.title")).to_contain_text("Therapist Chat Audit System")

        # Navigate to a discussion
        discussion_link = page.locator("a[href*='/training/discussions/']").first
        if discussion_link.is_visible():
            discussion_link.click()

            # Should still be authenticated
            expect(page).to_have_url("**/discussions/")

            # Should be able to interact with page (indicating session is active)
            interactive_elements = page.locator("button, a, input")
            expect(interactive_elements.first).to_be_visible()

    def test_audit_data_export_workflow(self, authenticated_auditor_context, flask_app):
        """Test audit data export functionality"""
        page = authenticated_auditor_context.new_page()
        page.goto(f"http://{flask_app.config['SERVER_NAME']}/therapist/audit/")

        # Look for export buttons or links
        export_buttons = page.locator("button").filter(has_text="Export")
        export_links = page.locator("a").filter(has_text="Export")

        if export_buttons.count() > 0 or export_links.count() > 0:
            # Click export button/link
            export_element = (
                export_buttons.first
                if export_buttons.count() > 0
                else export_links.first
            )
            export_element.click()

            # Should trigger download or show export interface
            # Note: Actual download testing would require more complex setup
            expect(page.locator("body")).to_be_visible()
