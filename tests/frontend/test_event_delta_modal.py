import pytest
from playwright.sync_api import Page, expect


@pytest.mark.skip(reason="Manually skipped for cherry-picking re-enablement")
class TestEventDeltaModal:
    """Test Add Event Delta modal functionality"""

    def test_event_update_copies_all_fields(self, class_discussion_page: Page):
        """Test that updating an event copies all fields from cumulative PDP"""
        page = class_discussion_page

        page.evaluate(
            """() => {
            const components = Array.from(document.querySelectorAll('[x-data]'));
            const extractionComponents = components.filter(el => {
                const data = el.getAttribute('x-data');
                return data && data.includes('componentExtractedDataWithReview');
            });

            const component = extractionComponents.find(comp => {
                const alpineData = Alpine.$data(comp);
                return alpineData.cumulativePdp?.events?.length > 0;
            });

            if (!component) throw new Error('No component with events found');

            const alpineData = Alpine.$data(component);
            alpineData.addEvent();
        }"""
        )

        expect(page.locator("#add-event-delta-modal")).to_have_class("modal is-active")

        action_select = page.locator("#event-delta-action-select")
        action_select.select_option("update")

        event_select = page.locator("#event-delta-id-select")
        expect(event_select).to_be_visible()

        event_options = event_select.locator("option")
        expect(event_options).to_have_count_greater_than(1)

        event_select.select_option(index=1)

        initial_event_count = page.evaluate(
            """() => {
            const component = window.currentAddEventComponent;
            return component.extractedData?.events?.length || 0;
        }"""
        )

        page.locator("button").filter(has_text="Add").click()

        page.wait_for_timeout(100)

        final_event_count = page.evaluate(
            """() => {
            const component = window.currentAddEventComponent;
            return component.extractedData?.events?.length || 0;
        }"""
        )

        assert final_event_count == initial_event_count + 1

        last_event = page.evaluate(
            """() => {
            const component = window.currentAddEventComponent;
            const events = component.extractedData?.events || [];
            return events[events.length - 1];
        }"""
        )

        required_fields = [
            "id",
            "kind",
            "description",
            "dateTime",
            "confidence",
            "person",
            "spouse",
            "child",
        ]
        for field in required_fields:
            assert field in last_event, f"Field '{field}' missing from copied event"

        expect(page.locator("#add-event-delta-modal")).not_to_have_class(
            "modal is-active"
        )

    def test_event_create_has_default_fields(self, class_discussion_page: Page):
        """Test that creating a new event has all default fields"""
        page = class_discussion_page

        page.evaluate(
            """() => {
            const components = Array.from(document.querySelectorAll('[x-data]'));
            const extractionComponents = components.filter(el => {
                const data = el.getAttribute('x-data');
                return data && data.includes('componentExtractedDataWithReview');
            });

            const component = extractionComponents[0];
            if (!component) throw new Error('No component found');

            const alpineData = Alpine.$data(component);
            alpineData.addEvent();
        }"""
        )

        expect(page.locator("#add-event-delta-modal")).to_have_class("modal is-active")

        action_select = page.locator("#event-delta-action-select")
        expect(action_select).to_have_value("new")

        event_select_field = page.locator("#event-delta-select-field")
        expect(event_select_field).not_to_be_visible()

        initial_event_count = page.evaluate(
            """() => {
            const component = window.currentAddEventComponent;
            return component.extractedData?.events?.length || 0;
        }"""
        )

        page.locator("button").filter(has_text="Add").click()

        page.wait_for_timeout(100)

        final_event_count = page.evaluate(
            """() => {
            const component = window.currentAddEventComponent;
            return component.extractedData?.events?.length || 0;
        }"""
        )

        assert final_event_count == initial_event_count + 1

        last_event = page.evaluate(
            """() => {
            const component = window.currentAddEventComponent;
            const events = component.extractedData?.events || [];
            return events[events.length - 1];
        }"""
        )

        assert last_event["kind"] == "shift"
        assert last_event["description"] == "New Event"
        assert last_event["confidence"] == 1.0
        assert last_event["id"] < 0

    def test_event_dropdown_populated_from_cumulative(
        self, class_discussion_page: Page
    ):
        """Test that event dropdown is populated from cumulative PDP"""
        page = class_discussion_page

        cumulative_events = page.evaluate(
            """() => {
            const components = Array.from(document.querySelectorAll('[x-data]'));
            const extractionComponents = components.filter(el => {
                const data = el.getAttribute('x-data');
                return data && data.includes('componentExtractedDataWithReview');
            });

            const component = extractionComponents.find(comp => {
                const alpineData = Alpine.$data(comp);
                return alpineData.cumulativePdp?.events?.length > 0;
            });

            if (!component) return [];

            const alpineData = Alpine.$data(component);
            alpineData.addEvent();
            return alpineData.cumulativePdp?.events || [];
        }"""
        )

        if len(cumulative_events) == 0:
            pytest.skip("No cumulative events available for testing")

        expect(page.locator("#add-event-delta-modal")).to_have_class("modal is-active")

        action_select = page.locator("#event-delta-action-select")
        action_select.select_option("update")

        event_select = page.locator("#event-delta-id-select")
        event_options = event_select.locator("option")

        expect(event_options).to_have_count(len(cumulative_events) + 1)

        page.locator("button").filter(has_text="Cancel").click()
