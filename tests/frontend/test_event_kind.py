import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="function")
def discussion_with_events(therapist_flask_app, therapist_test_data):
    from btcopilot.extensions import db
    from btcopilot.personal.models import Statement

    discussion_id = therapist_test_data["discussion_id"]
    discussion = therapist_test_data["discussion"]
    subject_speaker = discussion.statements[0].speaker

    stmt_with_events = Statement(
        discussion_id=discussion_id,
        speaker_id=subject_speaker.id,
        text="My anxiety went up when my father passed away",
        order=3,
        pdp_deltas={
            "people": [{"id": "person1", "name": "Father", "confidence": 0.9}],
            "events": [
                {
                    "id": "event1",
                    "description": "Father passed away",
                    "kind": "shift",
                    "dateTime": "2023-01-15",
                    "symptom": "up",
                    "anxiety": "up",
                    "functioning": "down",
                    "confidence": 0.95,
                }
            ],
        },
    )
    db.session.add(stmt_with_events)
    db.session.commit()

    return therapist_test_data


@pytest.fixture(scope="function")
def event_kind_page(browser, therapist_flask_app, discussion_with_events):
    from flask.testing import FlaskClient
    from playwright.sync_api import Route
    from btcopilot.tests.frontend.conftest import _flask_route_handler

    context = browser.new_context()
    context.discussion_id = discussion_with_events["discussion_id"]
    context.user_id = discussion_with_events["user_id"]

    therapist_flask_app.test_client_class = FlaskClient
    test_client = therapist_flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = discussion_with_events["user_id"]

    def route_handler(route: Route):
        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)
    context.test_client = test_client

    page = context.new_page()
    discussion_id = context.discussion_id
    page.goto(f"http://testserver/training/discussions/{discussion_id}")

    return page


def test_event_kind_field_displays_correctly(event_kind_page: Page):
    event_kind_page.wait_for_selector(".extracted-data-component", timeout=10000)
    collapsed_data = event_kind_page.locator(".collapsed-data-section").first
    expect(collapsed_data).to_be_visible()
    collapsed_data.click()
    event_kind_page.wait_for_selector(".event-kind-section", timeout=5000)
    event_kind_section = event_kind_page.locator(".event-kind-section").first
    expect(event_kind_section).to_be_visible()
    event_kind_label = event_kind_section.locator("text=Event Kind:")
    expect(event_kind_label).to_be_visible()


def test_event_kind_shows_shift_by_default(event_kind_page: Page):
    event_kind_page.wait_for_selector(".extracted-data-component", timeout=10000)
    collapsed_data = event_kind_page.locator(".collapsed-data-section").first
    collapsed_data.click()
    event_kind_page.wait_for_selector(".event-kind", timeout=5000)
    event_kind_display = event_kind_page.locator(".event-kind").first
    expect(event_kind_display).to_contain_text("shift")


def test_variables_visible_for_shift_events(event_kind_page: Page):
    event_kind_page.wait_for_selector(".extracted-data-component", timeout=10000)
    collapsed_data = event_kind_page.locator(".collapsed-data-section").first
    collapsed_data.click()
    event_kind_page.wait_for_selector(".variables-compact", timeout=5000)
    variables_section = event_kind_page.locator(".variables-compact").first
    expect(variables_section).to_be_visible()
    symptom_field = variables_section.locator("text=Symptom:")
    expect(symptom_field).to_be_visible()
    anxiety_field = variables_section.locator("text=Anxiety:")
    expect(anxiety_field).to_be_visible()
    functioning_field = variables_section.locator("text=Functioning:")
    expect(functioning_field).to_be_visible()


def test_event_kind_dropdown_has_all_options(event_kind_page: Page):
    event_kind_page.wait_for_selector(".extracted-data-component", timeout=10000)
    collapsed_data = event_kind_page.locator(".collapsed-data-section").first
    collapsed_data.click()
    event_kind_page.wait_for_selector(".event-kind", timeout=5000)
    event_kind_field = event_kind_page.locator(".event-kind").first
    event_kind_field.click()
    event_kind_page.wait_for_selector("select.inline-edit-select", timeout=5000)
    dropdown = event_kind_page.locator("select.inline-edit-select").first
    expect(dropdown).to_be_visible()
    expected_options = [
        "shift",
        "birth",
        "adopted",
        "bonded",
        "married",
        "separated",
        "divorced",
        "moved",
        "death",
    ]
    for option_value in expected_options:
        option = dropdown.locator(f"option[value='{option_value}']")
        expect(option).to_be_attached()


def test_changing_to_birth_hides_variables(event_kind_page: Page):
    event_kind_page.wait_for_selector(".extracted-data-component", timeout=10000)
    collapsed_data = event_kind_page.locator(".collapsed-data-section").first
    collapsed_data.click()
    event_kind_page.wait_for_selector(".event-kind", timeout=5000)
    variables_section = event_kind_page.locator(".variables-compact").first
    expect(variables_section).to_be_visible()
    event_kind_field = event_kind_page.locator(".event-kind").first
    event_kind_field.click()
    event_kind_page.wait_for_selector("select.inline-edit-select", timeout=5000)
    dropdown = event_kind_page.locator("select.inline-edit-select").first
    dropdown.select_option("birth")
    event_kind_page.wait_for_timeout(500)
    expect(variables_section).not_to_be_visible()


def test_changing_to_death_hides_variables(event_kind_page: Page):
    event_kind_page.wait_for_selector(".extracted-data-component", timeout=10000)
    collapsed_data = event_kind_page.locator(".collapsed-data-section").first
    collapsed_data.click()
    event_kind_page.wait_for_selector(".event-kind", timeout=5000)
    event_kind_field = event_kind_page.locator(".event-kind").first
    event_kind_field.click()
    event_kind_page.wait_for_selector("select.inline-edit-select", timeout=5000)
    dropdown = event_kind_page.locator("select.inline-edit-select").first
    dropdown.select_option("death")
    event_kind_page.wait_for_timeout(500)
    variables_section = event_kind_page.locator(".variables-compact").first
    expect(variables_section).not_to_be_visible()


def test_changing_back_to_shift_shows_variables(event_kind_page: Page):
    event_kind_page.wait_for_selector(".extracted-data-component", timeout=10000)
    collapsed_data = event_kind_page.locator(".collapsed-data-section").first
    collapsed_data.click()
    event_kind_page.wait_for_selector(".event-kind", timeout=5000)
    event_kind_field = event_kind_page.locator(".event-kind").first
    event_kind_field.click()
    event_kind_page.wait_for_selector("select.inline-edit-select", timeout=5000)
    dropdown = event_kind_page.locator("select.inline-edit-select").first
    dropdown.select_option("married")
    event_kind_page.wait_for_timeout(500)
    variables_section = event_kind_page.locator(".variables-compact").first
    expect(variables_section).not_to_be_visible()
    event_kind_field.click()
    event_kind_page.wait_for_selector("select.inline-edit-select", timeout=5000)
    dropdown = event_kind_page.locator("select.inline-edit-select").first
    dropdown.select_option("shift")
    event_kind_page.wait_for_timeout(500)
    expect(variables_section).to_be_visible()


def test_event_kind_persists_after_selection(event_kind_page: Page):
    event_kind_page.wait_for_selector(".extracted-data-component", timeout=10000)
    collapsed_data = event_kind_page.locator(".collapsed-data-section").first
    collapsed_data.click()
    event_kind_page.wait_for_selector(".event-kind", timeout=5000)
    event_kind_field = event_kind_page.locator(".event-kind").first
    event_kind_field.click()
    event_kind_page.wait_for_selector("select.inline-edit-select", timeout=5000)
    dropdown = event_kind_page.locator("select.inline-edit-select").first
    dropdown.select_option("adopted")
    event_kind_page.wait_for_timeout(1000)
    event_kind_display = event_kind_page.locator(".event-kind").first
    expect(event_kind_display).to_contain_text("adopted")
