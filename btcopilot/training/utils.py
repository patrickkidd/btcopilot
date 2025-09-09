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
    """
    Get auditor ID from request/session for audit tracking.
    This is a placeholder - should be implemented by parent app.
    """
    # This will be overridden by parent application's user system
    return session.get('user_id', 'anonymous')