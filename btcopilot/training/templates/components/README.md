# Extracted Data Display Components

This directory contains reusable template components for displaying extracted PDP (Personal Data Profile) data throughout the application.

## Components

### 1. `extracted_data_display.html` - Full Interactive Component

The main component with full functionality including feedback controls, collapsible sections, and Alpine.js integration.

**Usage:**
```django
{% include "components/extracted_data_display.html" with data=extracted_data collapsed=true show_feedback=true message_id=message.id feedback_data=existing_feedback %}
```

**Parameters:**
- `data` (required): The extracted data object containing `people`, `events`, `deletes`
- `collapsed` (optional, default: true): Whether to show collapsed view initially
- `show_feedback` (optional, default: false): Whether to show feedback controls
- `message_id` (required if show_feedback=true): Message ID for feedback submission
- `feedback_data` (optional): Existing feedback data if any
- `component_id` (optional): Unique identifier for this component instance

**Features:**
- Collapsible summary/detail views
- Interactive feedback controls with thumbs up/down
- Corrected data display from auditor feedback
- Alpine.js reactive components
- Full variable display (symptom, anxiety, functioning, relationship)

### 2. `extracted_data_simple.html` - Read-only Display

Simplified component for read-only display without feedback functionality.

**Usage:**
```django
{% include "components/extracted_data_simple.html" with data=extracted_data show_summary=true show_details=true %}
```

**Parameters:**
- `data` (required): The extracted data object
- `show_summary` (optional, default: true): Whether to show summary tags
- `show_details` (optional, default: false): Whether to show full details

**Features:**
- Clean, simple layout
- No interactive elements
- Summary tags and detailed views
- Responsive column layout for variables

### 3. `extracted_data_corrected.html` - Corrected Data Display

Helper component for displaying corrected extraction data from auditor feedback.

**Usage:**
```django
<!-- Used within other components -->
<div x-data='{ correctedData: {{ feedback.edited_extraction|tojson }} }'>
    {% include "components/extracted_data_corrected.html" %}
</div>
```

**Features:**
- Displays corrected data with info styling
- Compact layout for feedback contexts
- Works with Alpine.js data binding

## Data Structure

The components expect extracted data in this format:

```javascript
{
    "people": [
        {
            "id": 1,
            "name": "John Doe",
            "confidence": 0.95,
            // ... other person fields
        }
    ],
    "events": [
        {
            "id": 1,
            "description": "Family discussion about stress",
            "confidence": 0.87,
            "symptom": { "shift": "up" },
            "anxiety": { "shift": "down" },
            "functioning": { "shift": "same" },
            "relationship": { "kind": "triangle" }
        }
    ],
    "deletes": [2, 5, 7]  // IDs of items to delete
}
```

## CSS Classes

The components use these CSS classes (defined in `therapist_base.html`):

- `.shift-indicator` - Base styling for variable indicators
- `.shift-up` - Yellow background for "up" shifts
- `.shift-down` - Red background for "down" shifts
- `.shift-same` - Gray background for "same" shifts
- `.shift-relationship` - Red background for relationship indicators
- `.variables-compact` - Grid layout for variable display
- `.person-item`, `.event-item` - Item styling
- `.section-header` - Section header styling

## JavaScript Dependencies

- **Alpine.js** (required for full component)
- **Font Awesome** (for icons)
- **Bulma CSS** (for styling)

## Integration Examples

### In Audit Discussion Page
```django
<!-- Replace existing extracted data display with: -->
{% include "components/extracted_data_display.html" with data=item.extracted_data collapsed=item.has_conv_feedback|not show_feedback=true message_id=item.message.id feedback_data=item.ext_feedback component_id=item.message.id %}
```

### In User Detail Modal
```django
<!-- Show user's recent extracted data -->
{% for thread in user.recent_threads %}
    {% if thread.latest_extraction %}
    <div class="box">
        <h6 class="title is-6">Discussion {{ thread.id }} - Latest Extraction</h6>
        {% include "components/extracted_data_simple.html" with data=thread.latest_extraction show_summary=true show_details=false %}
    </div>
    {% endif %}
{% endfor %}
```

### In Dashboard Summary
```django
<!-- Quick overview of recent extractions -->
{% for extraction in recent_extractions %}
<div class="column is-one-third">
    {% include "components/extracted_data_simple.html" with data=extraction show_summary=true show_details=false %}
</div>
{% endfor %}
```

## Migration Guide

To migrate existing extracted data displays:

1. **Identify existing display code** in templates
2. **Replace with component include** using appropriate parameters
3. **Remove duplicate HTML/CSS** that's now in the component
4. **Update JavaScript** to use component-specific functions if needed
5. **Test functionality** to ensure Alpine.js and feedback features work

## Future Enhancements

- Add export functionality
- Include data validation indicators
- Add comparison views between original and corrected data
- Implement data filtering and search within components