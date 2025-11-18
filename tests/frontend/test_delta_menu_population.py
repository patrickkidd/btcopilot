import pytest
from playwright.sync_api import Page, expect
from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
import btcopilot


@pytest.fixture(scope="function")
def discussion_with_diagram(flask_app):
    with flask_app.app_context():
        auditor_user = User(
            username="diagram_auditor@example.com",
            password="testpass",
            first_name="Diagram",
            last_name="Auditor",
            status="confirmed",
        )
        auditor_user._plaintext_password = "testpass"
        auditor_user.set_role(btcopilot.ROLE_AUDITOR)
        db.session.add(auditor_user)
        db.session.commit()

        diagram = Diagram(user_id=auditor_user.id, name="Test Diagram")
        diagram.data = {
            "people": [
                {"id": 1, "name": "User"},
                {"id": 2, "name": "Assistant"},
                {"id": 3, "name": "Database Person A"},
                {"id": 4, "name": "Database Person B"},
            ],
            "events": [
                {"id": 1, "description": "Database Event 1", "kind": "shift"},
                {"id": 2, "description": "Database Event 2", "kind": "birth"},
            ],
        }
        db.session.add(diagram)
        db.session.commit()

        discussion = Discussion(user=auditor_user, diagram=diagram)
        db.session.add(discussion)

        subject_speaker = Speaker(
            discussion=discussion, type=SpeakerType.Subject, name="Test User"
        )
        expert_speaker = Speaker(
            discussion=discussion, type=SpeakerType.Expert, name="AI Assistant"
        )
        db.session.add(subject_speaker)
        db.session.add(expert_speaker)

        stmt1 = Statement(
            discussion=discussion,
            speaker=subject_speaker,
            text="Hello, I need help with my family diagram",
            order=1,
            pdp_deltas={
                "people": [{"id": -1, "name": "Cumulative Person A"}],
                "events": [
                    {"id": -1, "description": "Cumulative Event A", "kind": "shift"}
                ],
            },
        )
        stmt2 = Statement(
            discussion=discussion,
            speaker=expert_speaker,
            text="I'd be happy to help you with your family diagram.",
            order=2,
        )
        db.session.add(stmt1)
        db.session.add(stmt2)
        db.session.commit()

        return {
            "user_id": auditor_user.id,
            "username": auditor_user.username,
            "discussion_id": discussion.id,
            "diagram_id": diagram.id,
        }


def test_update_person_includes_database_people(
    browser, flask_app, discussion_with_diagram
):
    context = browser.new_context()
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = discussion_with_diagram["user_id"]

    def route_handler(route):
        from btcopilot.tests.frontend.conftest import _flask_route_handler

        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)

    page = context.new_page()
    page.goto(
        f"http://testserver/training/discussions/{discussion_with_diagram['discussion_id']}"
    )

    page.evaluate(
        """() => {
        const components = Array.from(document.querySelectorAll('[x-data]'));
        const component = components.find(el => {
            const data = el.getAttribute('x-data');
            return data && data.includes('componentExtractedDataWithReview');
        });
        if (component) {
            const alpineData = Alpine.$data(component);
            alpineData.addPerson();
        }
    }"""
    )

    expect(page.locator("#add-person-delta-modal")).to_have_class("modal is-active")

    action_select = page.locator("#person-delta-action-select")
    action_select.select_option("update")

    person_select = page.locator("#person-delta-id-select")
    options_text = page.evaluate(
        """() => {
        const select = document.getElementById('person-delta-id-select');
        return Array.from(select.options).map(opt => opt.textContent);
    }"""
    )

    assert any("Database Person A" in opt for opt in options_text)
    assert any("Database Person B" in opt for opt in options_text)

    context.close()


def test_update_person_includes_cumulative_people(
    browser, flask_app, discussion_with_diagram
):
    context = browser.new_context()
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = discussion_with_diagram["user_id"]

    def route_handler(route):
        from btcopilot.tests.frontend.conftest import _flask_route_handler

        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)

    page = context.new_page()
    page.goto(
        f"http://testserver/training/discussions/{discussion_with_diagram['discussion_id']}"
    )

    page.evaluate(
        """() => {
        const components = Array.from(document.querySelectorAll('[x-data]'));
        const component = components.find(el => {
            const data = el.getAttribute('x-data');
            return data && data.includes('componentExtractedDataWithReview');
        });
        if (component) {
            const alpineData = Alpine.$data(component);
            alpineData.addPerson();
        }
    }"""
    )

    action_select = page.locator("#person-delta-action-select")
    action_select.select_option("update")

    options_text = page.evaluate(
        """() => {
        const select = document.getElementById('person-delta-id-select');
        return Array.from(select.options).map(opt => opt.textContent);
    }"""
    )

    assert any("Cumulative Person A" in opt for opt in options_text)

    context.close()


def test_update_person_excludes_expert_speakers(
    browser, flask_app, discussion_with_diagram
):
    with flask_app.app_context():
        from btcopilot.personal.models import Discussion

        discussion = Discussion.query.get(discussion_with_diagram["discussion_id"])
        expert_speaker = next(
            (s for s in discussion.speakers if s.type == SpeakerType.Expert), None
        )
        if expert_speaker:
            expert_speaker.person_id = 2

        db.session.commit()

    context = browser.new_context()
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = discussion_with_diagram["user_id"]

    def route_handler(route):
        from btcopilot.tests.frontend.conftest import _flask_route_handler

        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)

    page = context.new_page()
    page.goto(
        f"http://testserver/training/discussions/{discussion_with_diagram['discussion_id']}"
    )

    page.evaluate(
        """() => {
        const components = Array.from(document.querySelectorAll('[x-data]'));
        const component = components.find(el => {
            const data = el.getAttribute('x-data');
            return data && data.includes('componentExtractedDataWithReview');
        });
        if (component) {
            const alpineData = Alpine.$data(component);
            alpineData.addPerson();
        }
    }"""
    )

    action_select = page.locator("#person-delta-action-select")
    action_select.select_option("update")

    options_text = page.evaluate(
        """() => {
        const select = document.getElementById('person-delta-id-select');
        return Array.from(select.options).map(opt => opt.textContent);
    }"""
    )

    assert not any("Assistant" in opt and "(ID: 2)" in opt for opt in options_text)

    context.close()


def test_update_event_includes_database_events(
    browser, flask_app, discussion_with_diagram
):
    context = browser.new_context()
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = discussion_with_diagram["user_id"]

    def route_handler(route):
        from btcopilot.tests.frontend.conftest import _flask_route_handler

        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)

    page = context.new_page()
    page.goto(
        f"http://testserver/training/discussions/{discussion_with_diagram['discussion_id']}"
    )

    page.evaluate(
        """() => {
        const components = Array.from(document.querySelectorAll('[x-data]'));
        const component = components.find(el => {
            const data = el.getAttribute('x-data');
            return data && data.includes('componentExtractedDataWithReview');
        });
        if (component) {
            const alpineData = Alpine.$data(component);
            alpineData.addEvent();
        }
    }"""
    )

    expect(page.locator("#add-event-delta-modal")).to_have_class("modal is-active")

    action_select = page.locator("#event-delta-action-select")
    action_select.select_option("update")

    options_text = page.evaluate(
        """() => {
        const select = document.getElementById('event-delta-id-select');
        return Array.from(select.options).map(opt => opt.textContent);
    }"""
    )

    assert any("Database Event 1" in opt for opt in options_text)
    assert any("Database Event 2" in opt for opt in options_text)

    context.close()


def test_update_event_includes_cumulative_events(
    browser, flask_app, discussion_with_diagram
):
    context = browser.new_context()
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = discussion_with_diagram["user_id"]

    def route_handler(route):
        from btcopilot.tests.frontend.conftest import _flask_route_handler

        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)

    page = context.new_page()
    page.goto(
        f"http://testserver/training/discussions/{discussion_with_diagram['discussion_id']}"
    )

    page.evaluate(
        """() => {
        const components = Array.from(document.querySelectorAll('[x-data]'));
        const component = components.find(el => {
            const data = el.getAttribute('x-data');
            return data && data.includes('componentExtractedDataWithReview');
        });
        if (component) {
            const alpineData = Alpine.$data(component);
            alpineData.addEvent();
        }
    }"""
    )

    action_select = page.locator("#event-delta-action-select")
    action_select.select_option("update")

    options_text = page.evaluate(
        """() => {
        const select = document.getElementById('event-delta-id-select');
        return Array.from(select.options).map(opt => opt.textContent);
    }"""
    )

    assert any("Cumulative Event A" in opt for opt in options_text)

    context.close()


def test_delete_includes_database_people(browser, flask_app, discussion_with_diagram):
    context = browser.new_context()
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = discussion_with_diagram["user_id"]

    def route_handler(route):
        from btcopilot.tests.frontend.conftest import _flask_route_handler

        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)

    page = context.new_page()
    page.goto(
        f"http://testserver/training/discussions/{discussion_with_diagram['discussion_id']}"
    )

    available_ids = page.evaluate(
        """() => {
        const components = Array.from(document.querySelectorAll('[x-data]'));
        const component = components.find(el => {
            const data = el.getAttribute('x-data');
            return data && data.includes('componentExtractedDataWithReview');
        });
        if (component) {
            const alpineData = Alpine.$data(component);
            return alpineData.getCumulativeOnlyIds();
        }
        return [];
    }"""
    )

    labels = [item["label"] for item in available_ids]

    assert any("Database Person A" in label for label in labels)
    assert any("Database Person B" in label for label in labels)

    context.close()


def test_delete_includes_database_events(browser, flask_app, discussion_with_diagram):
    context = browser.new_context()
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = discussion_with_diagram["user_id"]

    def route_handler(route):
        from btcopilot.tests.frontend.conftest import _flask_route_handler

        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)

    page = context.new_page()
    page.goto(
        f"http://testserver/training/discussions/{discussion_with_diagram['discussion_id']}"
    )

    available_ids = page.evaluate(
        """() => {
        const components = Array.from(document.querySelectorAll('[x-data]'));
        const component = components.find(el => {
            const data = el.getAttribute('x-data');
            return data && data.includes('componentExtractedDataWithReview');
        });
        if (component) {
            const alpineData = Alpine.$data(component);
            return alpineData.getCumulativeOnlyIds();
        }
        return [];
    }"""
    )

    labels = [item["label"] for item in available_ids]

    assert any("Database Event 1" in label for label in labels)
    assert any("Database Event 2" in label for label in labels)

    context.close()
