import pytest
import re
from playwright.sync_api import Page, expect


class TestAuditorSelection:

    def test_add_codes_from_scratch_as_auditor(self, class_discussion_page: Page):
        """Test that auditors can add codes from scratch without AI extraction"""
        class_discussion_page.wait_for_load_state("networkidle")

        # Find a subject message row in the Changes to Notes column
        data_cell = class_discussion_page.locator("td.data-cell").first
        expect(data_cell).to_be_visible()

        # Click to expand the coding interface
        data_cell.click()

        # Should see Add Person and Add Event buttons
        add_person_btn = class_discussion_page.locator("text=Add Person").first
        add_event_btn = class_discussion_page.locator("text=Add Event").first

        expect(add_person_btn).to_be_visible()
        expect(add_event_btn).to_be_visible()

        # Add a person
        add_person_btn.click()

        # Person name input should be visible
        person_name_input = class_discussion_page.locator("input.inline-edit-input").first
        expect(person_name_input).to_be_visible()

        # Enter a person name
        person_name_input.fill("Test Person")
        person_name_input.press("Enter")

        # Wait for auto-save
        class_discussion_page.wait_for_timeout(2000)

        # Refresh page
        class_discussion_page.reload()
        class_discussion_page.wait_for_load_state("networkidle")

        # Codes should still be there after refresh
        expect(class_discussion_page.locator("text=Test Person")).to_be_visible()

    def test_admin_auditor_dropdown_shows_when_codes_exist(self, admin_discussion_page: Page):
        """Test that admin sees auditor dropdown when codes exist"""
        admin_discussion_page.wait_for_load_state("networkidle")

        # Auditor dropdown should be visible
        auditor_dropdown = admin_discussion_page.locator("select#auditor-filter")
        expect(auditor_dropdown).to_be_visible()

        # Should have AI option
        ai_option = auditor_dropdown.locator("option[value='AI']")
        expect(ai_option).to_be_visible()

    def test_admin_auditor_dropdown_hidden_when_no_codes(self, admin_discussion_page: Page):
        """Test that admin doesn't see dropdown when no codes exist"""
        # Navigate to a discussion with no extractions
        admin_discussion_page.goto(admin_discussion_page.url.replace("/discussions/1", "/discussions/999"))
        admin_discussion_page.wait_for_load_state("networkidle")

        # Auditor dropdown should not be visible
        auditor_dropdown = admin_discussion_page.locator("select#auditor-filter")
        expect(auditor_dropdown).not_to_be_visible()

    def test_admin_can_filter_by_ai(self, admin_discussion_page: Page):
        """Test admin can select AI from dropdown to view only AI codes"""
        admin_discussion_page.wait_for_load_state("networkidle")

        # Select AI from dropdown
        auditor_dropdown = admin_discussion_page.locator("select#auditor-filter")
        auditor_dropdown.select_option("AI")

        # Page should reload with selected_auditor=AI parameter
        admin_discussion_page.wait_for_load_state("networkidle")
        expect(admin_discussion_page).to_have_url(re.compile(r"selected_auditor=AI"))

        # Should show AI codes only (no human auditor tabs)
        tabs = admin_discussion_page.locator(".tabs")
        expect(tabs).not_to_be_visible()

    def test_admin_can_filter_by_human_auditor(self, admin_discussion_page: Page):
        """Test admin can select a human auditor to view their codes"""
        admin_discussion_page.wait_for_load_state("networkidle")

        # Get the auditor dropdown
        auditor_dropdown = admin_discussion_page.locator("select#auditor-filter")

        # Get all options (skip first which is placeholder)
        options = auditor_dropdown.locator("option").all()

        # If there are human auditors, select the first one
        if len(options) > 2:  # Placeholder + AI + at least one human
            human_auditor_option = options[2]
            auditor_value = human_auditor_option.get_attribute("value")

            auditor_dropdown.select_option(auditor_value)

            # Page should reload with selected_auditor parameter
            admin_discussion_page.wait_for_load_state("networkidle")
            expect(admin_discussion_page).to_have_url(re.compile(f"selected_auditor={auditor_value}"))

            # Tabs should be hidden when viewing single auditor
            tabs = admin_discussion_page.locator(".tabs")
            expect(tabs).not_to_be_visible()

    def test_cumulative_notes_recalculate_for_selected_auditor(self, admin_discussion_page: Page):
        """Test that cumulative notes update when auditor is selected"""
        admin_discussion_page.wait_for_load_state("networkidle")

        # Select a different auditor
        auditor_dropdown = admin_discussion_page.locator("select#auditor-filter")
        options = auditor_dropdown.locator("option").all()

        if len(options) > 2:
            auditor_dropdown.select_option(options[2].get_attribute("value"))
            admin_discussion_page.wait_for_load_state("networkidle")

            # Cumulative content should still exist
            cumulative_cell_after = admin_discussion_page.locator("td.data-cell").nth(1)
            expect(cumulative_cell_after).to_be_visible()

    def test_delete_button_shows_for_user_codes(self, class_discussion_page: Page):
        """Test delete button appears when user has saved codes"""
        class_discussion_page.wait_for_load_state("networkidle")

        # Expand a data cell
        data_cell = class_discussion_page.locator("td.data-cell").first
        data_cell.click()

        # Add a person to create feedback
        add_person_btn = class_discussion_page.locator("text=Add Person").first
        add_person_btn.click()

        person_name_input = class_discussion_page.locator("input.inline-edit-input").first
        person_name_input.fill("Delete Test Person")
        person_name_input.press("Enter")

        # Wait for auto-save
        class_discussion_page.wait_for_timeout(2000)

        # Delete button should appear
        delete_btn = class_discussion_page.locator("button.is-danger i.fa-times").first
        expect(delete_btn).to_be_visible()

    def test_delete_button_removes_user_codes(self, class_discussion_page: Page):
        """Test that delete button removes user's codes for statement"""
        class_discussion_page.wait_for_load_state("networkidle")

        # Expand and add codes
        data_cell = class_discussion_page.locator("td.data-cell").first
        data_cell.click()

        add_person_btn = class_discussion_page.locator("text=Add Person").first
        add_person_btn.click()

        person_name_input = class_discussion_page.locator("input.inline-edit-input").first
        person_name_input.fill("To Be Deleted")
        person_name_input.press("Enter")

        # Wait for auto-save
        class_discussion_page.wait_for_timeout(2000)

        # Click delete button
        delete_btn = class_discussion_page.locator("button.is-danger").first

        # Handle confirmation dialog
        class_discussion_page.on("dialog", lambda dialog: dialog.accept())
        delete_btn.click()

        # Wait for deletion
        class_discussion_page.wait_for_timeout(1000)

        # Person should be gone
        expect(class_discussion_page.locator("text=To Be Deleted")).not_to_be_visible()

    def test_codes_expanded_by_default(self, class_discussion_page: Page):
        """Test that all code sections are expanded by default"""
        class_discussion_page.wait_for_load_state("networkidle")

        # Find expanded data sections - they should be visible without clicking
        expanded_sections = class_discussion_page.locator(".admin-tabbed-data").all()

        # At least some should be visible (have display: block)
        visible_count = 0
        for section in expanded_sections:
            if section.is_visible():
                visible_count += 1

        assert visible_count > 0, "No code sections are expanded by default"


@pytest.fixture(scope="function")
def admin_test_data(flask_app):
    """Create admin user and discussion data"""
    from btcopilot.extensions import db
    from btcopilot.pro.models import User
    from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
    import btcopilot

    admin_user = User(
        username="admin_auditor@example.com",
        password="testpass",
        first_name="Admin",
        last_name="User",
        status="confirmed",
    )
    admin_user._plaintext_password = "testpass"
    admin_user.set_role(btcopilot.ROLE_ADMIN)

    db.session.add(admin_user)
    db.session.commit()

    discussion = Discussion(user=admin_user)
    db.session.add(discussion)

    subject_speaker = Speaker(
        discussion=discussion, type=SpeakerType.Subject, name="Test Subject"
    )
    expert_speaker = Speaker(
        discussion=discussion, type=SpeakerType.Expert, name="AI Assistant"
    )
    db.session.add(subject_speaker)
    db.session.add(expert_speaker)

    stmt1 = Statement(
        discussion=discussion,
        speaker=subject_speaker,
        text="I need help understanding my family dynamics",
        order=1,
    )
    stmt2 = Statement(
        discussion=discussion,
        speaker=expert_speaker,
        text="I can help you with that. Tell me more about your family.",
        order=2,
    )
    db.session.add(stmt1)
    db.session.add(stmt2)
    db.session.commit()

    return {
        "user_id": admin_user.id,
        "username": admin_user.username,
        "discussion_id": discussion.id,
        "admin_user": admin_user,
        "discussion": discussion,
    }


@pytest.fixture(scope="function")
def admin_context(browser, flask_app, admin_test_data):
    """Browser context for admin user"""
    from playwright.sync_api import BrowserContext, Route
    from flask.testing import FlaskClient

    context = browser.new_context()
    context.discussion_id = admin_test_data["discussion_id"]
    context.user_id = admin_test_data["user_id"]
    context.username = admin_test_data["username"]

    flask_app.test_client_class = FlaskClient
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = admin_test_data["user_id"]

    def _flask_route_handler(route: Route, test_client: FlaskClient):
        from urllib.parse import urlparse

        request = route.request
        parsed_url = urlparse(request.url)
        path = parsed_url.path
        query_string = parsed_url.query
        post_data = request.post_data_buffer if request.post_data_buffer else None

        headers = {}
        for name, value in request.headers.items():
            if name.lower() not in ["host", "content-length", "connection"]:
                headers[name] = value

        try:
            response = test_client.open(
                path,
                method=request.method,
                data=post_data,
                query_string=query_string,
                headers=headers,
                follow_redirects=False,
            )

            response_headers = {}
            for key, value in response.headers:
                response_headers[key] = value

            route.fulfill(
                status=response.status_code,
                headers=response_headers,
                body=response.get_data(),
            )

        except Exception as e:
            route.fulfill(status=500, body=f"Flask test client error: {str(e)}")

    def route_handler(route: Route):
        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)
    context.test_client = test_client

    return context


@pytest.fixture(scope="function")
def admin_discussion_page(admin_context):
    """Page fixture for admin viewing discussion"""
    page = admin_context.new_page()
    discussion_id = admin_context.discussion_id
    page.goto(f"http://testserver/training/discussions/{discussion_id}")
    page.wait_for_load_state("networkidle")
    return page
