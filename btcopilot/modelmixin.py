import datetime
import decimal
import logging

from sqlalchemy import Column, Integer, DateTime, inspect
from sqlalchemy.orm import ColumnProperty, class_mapper
from sqlalchemy.orm.collections import InstrumentedList

from btcopilot import json
from btcopilot.extensions import db


_log = logging.getLogger(__name__)


class AsDictMixin:
    def _warn_no_attr(self, attr):
        _log.warning(f"The model {self.__class__.__name__} has no attribute `{attr}`.")

    @staticmethod
    def _fixup_param_value(value):
        if isinstance(value, str) and value:
            value = {value: {}}
        elif isinstance(value, list):
            value = {x: {} for x in value if x}
        return value

    def as_dict(self, update=None, include=None, exclude=None, only=None):
        """
        Modeled after rails as_json().
        Pass either a list of attr names or a dictionary of attr names with
        similar sub-args.
        created_at, updated_at are left out unless included in `include`.
        """
        ModelClass = self.__class__
        columns_by_name = {
            x.key: x
            for x in class_mapper(ModelClass).iterate_properties
            if isinstance(x, ColumnProperty)
        }
        rels_by_name = {x.key: x for x in inspect(ModelClass).relationships}

        only = self._fixup_param_value(only)

        # compile the list of names to add
        if only:
            to_add = {
                attr: kwargs
                for attr, kwargs in only.items()
                if (
                    attr
                    and attr in columns_by_name
                    or attr in rels_by_name
                    or hasattr(self, attr)
                )
            }
            # Note: For backward compatibility, timestamps are included by default
            # Uncomment below to exclude timestamps unless explicitly included in only:
            # if "created_at" in to_add and "created_at" not in only:
            #     to_add.pop("created_at", None)
            # if "updated_at" in to_add and "updated_at" not in only:
            #     to_add.pop("updated_at", None)

            for attr in only.keys():
                if attr and not attr in to_add:
                    self._warn_no_attr(attr)
        else:
            # include
            if isinstance(include, str):
                _include = {include: {}}
            elif isinstance(include, list):
                _include = {x: {} for x in include}
            elif include is None:
                _include = {}
            else:
                _include = dict(include)

            # exclude
            if isinstance(exclude, str):
                _exclude = [exclude]
            elif isinstance(exclude, list):
                _exclude = list(exclude)
            else:
                _exclude = []
            # Note: created_at and updated_at are included by default for backward compatibility
            # if "created_at" not in _include:
            #     _exclude.append("created_at")
            # if "updated_at" not in _include:
            #     _exclude.append("updated_at")

            # _included_rels = [x for x in rels_by_name.keys() if x in _include]
            to_add = {
                attr: _include.get(attr, {})
                for attr in (list(columns_by_name.keys()) + list(_include.keys()))
                if attr and hasattr(self, attr) and attr not in _exclude
            }
            for attr in _include:
                if attr and not attr in to_add:
                    self._warn_no_attr(attr)

        # __only = only if only else ""
        # _log.debug(f"{self.__class__.__name__}[{self.id}].as_dict({__only})")

        result = {}
        for attr, kwargs in to_add.items():
            # All values should be valid at this point.
            value = getattr(self, attr)
            result[attr] = self._marshal_attr(attr, value, kwargs)

        # Just one level until there is a use case for more levels.
        if update:
            result.update(update)

        return result

    def as_log_dict(self):
        """To override in subclass."""
        return self.as_dict()

    def _marshal_attr(self, attr, value, kwargs):

        ret = None
        if isinstance(value, InstrumentedList):
            ret = [
                x.as_dict(
                    include=kwargs.get("include", {}),
                    exclude=kwargs.get("exclude", {}),
                    only=kwargs.get("only", {}),
                )
                for x in value
            ]
        elif isinstance(value, db.Model):
            kwargs = self._fixup_param_value(kwargs)
            ret = value.as_dict(
                include=kwargs.get("include", {}),
                exclude=kwargs.get("exclude", {}),
                only=kwargs.get("only", {}) if isinstance(kwargs, dict) else kwargs,
            )
        # elif isinstance(value, datetime.datetime):
        #     ret = value.isoformat()
        # elif isinstance(value, datetime.date):
        #     ret = value.isoformat()
        elif isinstance(value, decimal.Decimal):
            ret = float(value)
        elif isinstance(value, list):
            if value and isinstance(value[0], db.Model):
                # _kwargs = kwargs.get(attr, {})
                ret = [x.as_dict(**kwargs) for x in value]
            else:
                ret = list(value)
        elif callable(value):
            _value = value()
            ret = self._marshal_attr(attr, _value, kwargs)
            # if isinstance(_value, list):
            #     if len(_value) and isinstance(_value[0], db.Model):
            #         _kwargs = kwargs.get(attr, {})
            #         ret = [x.as_dict(**_kwargs) for x in _value]
            #     else:
            #         ret = list(_value)
            # else:
            #     ret = _value
        else:
            ret = value
        return ret

    def flask_dict(self, *args, **kwargs):
        data = self.as_dict(*args, **kwargs)
        return json.loads(json.dumps(data))

    def as_json(self, *args, **kwargs):
        data = self.as_dict(*args, **kwargs)
        return json.dumps(data)


class ModelMixin(AsDictMixin):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    def update(self, _commit=False, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        if not "updated_at" in kwargs:
            self.updated_at = datetime.datetime.utcnow()
        if _commit:
            inspect(self).session.commit()

    @classmethod
    def filter_attrs(cls, kwargs):
        column_names = [
            x.key
            for x in class_mapper(cls).iterate_properties
            if isinstance(x, db.ColumnProperty)
        ]
        return {attr: value for attr, value in kwargs.items() if attr in column_names}

    # def as_dict(self, update=None, include=None, exclude=None):
    #     if include is None:
    #         include = []
    #     if not "created_at" in include:
    #         if isinstance(include, )
    #         include.append("created_at")
    #     if not "updated_at" in include:
    #         include.append("updated_at")
    #     return super().as_dict(update=update, include=include, exclude=exclude)

    def _as_dict(self, update={}, include=[], exclude=[]):
        if isinstance(include, str):
            include = [include]
        if isinstance(exclude, str):
            exclude = [exclude]
        result = {}
        for prop in class_mapper(self.__class__).iterate_properties:
            if prop.key in exclude:
                continue
            if isinstance(prop, ColumnProperty):
                result[prop.key] = getattr(self, prop.key)
        result.update(update)
        for _include in include:
            _value = getattr(self, _include)
            if isinstance(_value, InstrumentedList):
                result[_include] = [x.as_dict() for x in _value]
            elif callable(_value):
                result[_include] = _value()
            elif isinstance(_value, ModelMixin):
                result[_include] = _value.as_dict()
            else:
                result[_include] = _value
        return result
