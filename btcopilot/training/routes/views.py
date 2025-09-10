"""
Main training application views and route handlers.
"""

from flask import render_template, redirect, url_for, request
from . import training_bp


@training_bp.route('/')
def index():
    """Main training application landing page with role-based redirection"""
    from ..auth import get_current_user, _check_role, UserRole
    
    user = get_current_user()
    if not user:
        return redirect(url_for('training.auth.login'))

    # Use the role checking system (works in both standalone and integrated modes)
    if _check_role(user, UserRole.Admin):
        return redirect(url_for('training.admin.index'))
    elif _check_role(user, UserRole.Auditor):
        return redirect(url_for('training.audit.index'))
    
    # Default fallback - show audit page for any authenticated user
    return redirect(url_for('training.audit.index'))


@training_bp.context_processor
def inject_training_globals():
    """Inject common template variables for training routes"""
    return {
        'training_app': True,
        'app_name': 'BT Copilot Training'
    }