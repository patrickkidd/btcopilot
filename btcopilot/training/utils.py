"""
Utility functions for training web application.

Common helpers for breadcrumbs, navigation, and other UI utilities.
"""

def get_breadcrumbs(current_page):
    """
    Generate breadcrumb navigation for training pages.
    
    Args:
        current_page: String identifier for current page
        
    Returns:
        List of breadcrumb dictionaries with title and url
    """
    breadcrumbs = [
        {'title': 'Training', 'url': '/training'}
    ]
    
    page_breadcrumbs = {
        'audit': [
            {'title': 'Audit', 'url': '/training/audit'}
        ],
        'feedback': [
            {'title': 'Feedback', 'url': '/training/feedback'}  
        ],
        'prompts': [
            {'title': 'Prompt Lab', 'url': '/training/prompts'}
        ],
        'admin': [
            {'title': 'Admin', 'url': '/training/admin'}
        ],
        'thread': [
            {'title': 'Audit', 'url': '/training/audit'},
            {'title': 'Thread Review', 'url': None}
        ]
    }
    
    if current_page in page_breadcrumbs:
        breadcrumbs.extend(page_breadcrumbs[current_page])
    
    return breadcrumbs


def get_auditor_id(request, session):
    """Get auditor ID from request headers or use current user's ID"""
    # First check for explicit header (for testing)
    if request.headers.get("X-Auditor-Id"):
        return request.headers.get("X-Auditor-Id")
    
    # Use current user's ID as auditor ID via Flask g context
    from flask import g
    if hasattr(g, 'current_user') and g.current_user and hasattr(g.current_user, 'id'):
        return str(g.current_user.id)  # Convert to string for consistency
    
    # This shouldn't happen in practice since routes require login
    return "anonymous"