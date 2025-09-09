"""
Main training application views and route handlers.
"""

from flask import render_template, redirect, url_for, request
from . import training_bp


@training_bp.route('/')
def index():
    """Main training application landing page"""
    # This will be implemented to redirect based on user role
    # For now, simple landing page
    return render_template('training_index.html')


@training_bp.context_processor
def inject_training_globals():
    """Inject common template variables for training routes"""
    return {
        'training_app': True,
        'app_name': 'BT Copilot Training'
    }