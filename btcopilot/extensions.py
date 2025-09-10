from flask_sqlalchemy import SQLAlchemy as FlaskSQLAlchemy
from sqlalchemy.ext.declarative import declarative_base
from flask import request

Base = declarative_base()

class SQLAlchemy(FlaskSQLAlchemy):
    def make_declarative_base(self, model, metadata=None):
        if not hasattr(Base, 'query_class'):
            Base.query_class = self.Query
            Base.query = None
        if not hasattr(Base, 'query'):
            Base.query = None
        return Base

db = SQLAlchemy()

def init_app(app):
    db.init_app(app)
    
    @app.after_request
    def add_security_headers(response):
        if request.endpoint and request.endpoint.startswith("training."):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            if response.content_type and "text/html" in response.content_type:
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
        return response

__all__ = ['db', 'Base', 'init_app']