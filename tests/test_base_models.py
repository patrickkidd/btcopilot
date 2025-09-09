"""
Tests for base model mixins (AsDictMixin and ModelMixin).

Tests migrated from fdserver to ensure base functionality works correctly.
"""

import pytest
import datetime
from freezegun import freeze_time
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, create_engine
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base

from btcopilot.modelmixin import ModelMixin, AsDictMixin

# Create test database setup
Base = declarative_base()
FIXED_TIME = datetime.datetime.fromisoformat("2025-01-15T12:00:00")


class TestUser(Base, ModelMixin):
    """Test user model for mixin testing"""
    __tablename__ = 'test_users'
    
    username = Column(String(100))
    first_name = Column(String(100), default='')
    last_name = Column(String(100), default='') 
    active = Column(Boolean, default=True)
    secret = Column(String(255))
    
    licenses = relationship("TestLicense", back_populates="user")
    
    @property
    def roles(self):
        return ["subscriber"]
    
    @property 
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def status(self):
        return "pending"


class TestLicense(Base, ModelMixin):
    """Test license model for relationship testing"""
    __tablename__ = 'test_licenses'
    
    user_id = Column(Integer, ForeignKey('test_users.id'))
    policy_id = Column(Integer)
    key = Column(String(255))
    active = Column(Boolean, default=True)
    canceled = Column(Boolean, default=False)
    
    user = relationship("TestUser", back_populates="licenses")


@pytest.fixture(scope='function')
def db_session():
    """Create in-memory database session for testing"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def user(db_session):
    """Create test user with licenses"""
    with freeze_time(FIXED_TIME):
        user = TestUser(
            username="something",
            secret="some_secret"
        )
        user.created_at = datetime.datetime.utcnow()  # Explicitly set
        
        # Create licenses
        licenses = [TestLicense(policy_id=i, key="asd") for i in range(3)]
        for license in licenses:
            license.user = user
            db_session.add(license)
        
        db_session.add(user)
        db_session.commit()
        yield user


def test_basic_as_dict(user):
    """Test basic as_dict functionality"""
    result = user.as_dict()
    
    expected = {
        "active": True,
        "first_name": "",
        "id": 1,
        "last_name": "",
        "roles": ["subscriber"],
        "secret": "some_secret",
        "status": "pending",
        "created_at": FIXED_TIME,
        "updated_at": None,
        "username": "something",
    }
    
    # Remove non-deterministic keys for comparison
    result_filtered = {k: v for k, v in result.items() if k in expected}
    assert result_filtered == expected


def test_include_relationships(user):
    """Test including relationships in as_dict"""
    result = user.as_dict(include={"licenses": {"only": ["id"]}})
    
    # Check that licenses are included with only id field
    assert "licenses" in result
    assert len(result["licenses"]) == 3
    for i, license_dict in enumerate(result["licenses"]):
        assert license_dict == {"id": i + 1}


def test_include_properties(user):
    """Test including computed properties"""
    result = user.as_dict(include={"licenses": {"only": ["id"]}, "full_name": {}})
    
    assert "full_name" in result
    assert result["full_name"] == " "  # Empty first_name + space + empty last_name = " "
    assert "licenses" in result


def test_exclude_fields(user):
    """Test excluding specific fields"""
    result = user.as_dict(exclude=["secret", "active"])
    
    assert "secret" not in result
    assert "active" not in result
    assert "username" in result  # Should still be present


def test_nested_exclude(user):
    """Test excluding fields in nested relationships"""
    result = user.as_dict(
        include={
            "licenses": {
                "exclude": [
                    "policy_id",
                    "key", 
                    "created_at",
                    "updated_at",
                ]
            }
        }
    )
    
    assert "licenses" in result
    for license_dict in result["licenses"]:
        assert "policy_id" not in license_dict
        assert "key" not in license_dict
        assert "created_at" not in license_dict
        assert "updated_at" not in license_dict
        # But these should be present
        assert "id" in license_dict
        assert "active" in license_dict


def test_only_parameter(user):
    """Test using only parameter to limit fields"""
    result = user.as_dict(only={"id": {}, "username": {}, "full_name": {}})
    
    expected_keys = {"id", "username", "full_name"}
    assert set(result.keys()) == expected_keys


def test_update_method(user):
    """Test the update method functionality"""
    original_updated_at = user.updated_at
    
    user.update(username="new_username", first_name="John")
    
    assert user.username == "new_username"
    assert user.first_name == "John"
    assert user.updated_at != original_updated_at
    assert user.updated_at is not None


def test_filter_attrs():
    """Test filter_attrs class method"""
    kwargs = TestUser.filter_attrs({
        "created_at": datetime.datetime.now(),
        "updated_at": None,
        "username": "me@there.com",
        "invalid_arg": 123,  # Should be filtered out
        "nonexistent_field": "value"  # Should be filtered out
    })
    
    # Should only include valid column attributes
    valid_keys = {"created_at", "updated_at", "username"}
    assert set(kwargs.keys()).issubset(valid_keys)
    assert "invalid_arg" not in kwargs
    assert "nonexistent_field" not in kwargs


def test_as_log_dict(user):
    """Test as_log_dict method"""
    log_dict = user.as_log_dict()
    
    # Should be same as as_dict() by default
    regular_dict = user.as_dict()
    assert log_dict == regular_dict


def test_flask_dict(user):
    """Test flask_dict method for JSON serialization"""
    flask_dict = user.flask_dict()
    
    # Should handle datetime serialization
    assert isinstance(flask_dict, dict)
    assert "created_at" in flask_dict
    # created_at should be serialized as string for JSON compatibility
    if flask_dict["created_at"] is not None:
        assert isinstance(flask_dict["created_at"], str)


def test_as_json(user):
    """Test as_json method"""
    json_str = user.as_json()
    
    assert isinstance(json_str, str)
    assert "username" in json_str
    assert "something" in json_str
    
    # Should be valid JSON
    import json
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)
    assert parsed["username"] == "something"