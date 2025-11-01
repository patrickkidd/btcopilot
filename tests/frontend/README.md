# Frontend Test Suite for btcopilot Auditing Web UI

This directory contains Playwright-based frontend tests for the btcopilot therapist auditing web UI located at `/therapist/audit/`.

## Overview

The test suite covers the complete audit workflow including:
- Audit index page functionality
- Individual discussion audit pages
- Feedback submission system
- Data display and formatting
- Navigation and user experience
- Performance and accessibility

## Prerequisites

1. **Install Playwright dependencies:**
   ```bash
   cd /Users/patrick/dev/btcopilot
   pipenv install
   pipenv run playwright install
   ```

2. **Install browser binaries:**
   ```bash
   pipenv run playwright install-deps
   ```

## Test Structure

```
frontend/
├── conftest.py              # Test fixtures and setup
├── pytest.ini              # Playwright test configuration
├── test_audit_ui.py        # Main audit UI tests
├── test_audit_feedback.py  # Feedback system tests
└── README.md               # This file
```

## Running Tests

### Run all frontend tests
```bash
cd /Users/patrick/dev/btcopilot
pipenv run pytest btcopilot/tests/therapist/frontend/
```

### Run specific test categories
```bash
# Audit UI tests
pipenv run pytest -m audit_ui

# Feedback system tests
pipenv run pytest -m feedback_system

# Performance tests
pipenv run pytest -m performance
```

### Run tests in headed mode (visible browser)
```bash
pipenv run pytest --headed
```

### Run tests with video recording
```bash
pipenv run pytest --video=retain-on-failure
```

### Run tests with tracing
```bash
pipenv run pytest --tracing=retain-on-failure
```

## Test Fixtures

### `authenticated_auditor_context`
Creates a browser context with an authenticated auditor user and test data.

### `audit_page`
Provides a page navigated to the audit index (`/therapist/audit/`).

### `discussion_audit_page`
Provides a page navigated to a specific discussion audit page.

## Test Categories

### Audit UI Tests (`test_audit_ui.py`)
- Page loading and basic functionality
- User interface elements presence
- Navigation between pages
- Data integrity verification

### Feedback System Tests (`test_audit_feedback.py`)
- Conversation feedback submission
- Extraction feedback workflow
- Form validation
- Success/error handling

### Additional Test Areas
- **Data Display**: How audit data is formatted and presented
- **Navigation**: User flow between different audit pages
- **Performance**: Page load times and resource usage
- **Accessibility**: Keyboard navigation and screen reader support

## Test Data

The tests automatically create:
- Test auditor user with appropriate permissions
- Sample discussion with statements
- Subject and Expert speakers
- Realistic conversation flow

## Debugging Failed Tests

### Screenshots
Failed tests automatically capture screenshots in `test-results/` directory.

### Videos
Enable video recording to see exactly what happened during test execution:
```bash
pipenv run pytest --video=retain-on-failure
```

### Traces
Playwright traces provide detailed execution information:
```bash
pipenv run pytest --tracing=retain-on-failure
```

Then open the trace file with:
```bash
pipenv run playwright show-trace trace.zip
```

## Continuous Integration

For CI/CD pipelines, run tests headlessly:
```bash
pipenv run pytest --browser chromium --headed=false
```

## Browser Support

Tests are configured to run on Chromium by default. To test other browsers:
```bash
# Firefox
pipenv run pytest --browser firefox

# WebKit (Safari)
pipenv run pytest --browser webkit

# All browsers
pipenv run pytest --browser all
```

## Environment Variables

- `SERVER_NAME`: Server hostname (default: 127.0.0.1)
- `FLASK_CONFIG`: Flask configuration (default: testing)

## Troubleshooting

### Common Issues

1. **Browser not found**: Run `pipenv run playwright install`
2. **Dependencies missing**: Run `pipenv run playwright install-deps`
3. **Server not running**: Ensure btcopilot is running on the configured port
4. **Authentication failures**: Check that test user creation is working properly

### Debug Mode
Run tests with debug logging:
```bash
pipenv run pytest --log-cli-level=DEBUG
```

## Contributing

When adding new tests:
1. Follow the existing naming conventions
2. Add appropriate markers for test categorization
3. Include descriptive test names and docstrings
4. Test both success and failure scenarios
5. Ensure tests are idempotent and don't interfere with each other
