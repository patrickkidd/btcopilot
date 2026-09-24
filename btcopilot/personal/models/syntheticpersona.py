from sqlalchemy import Column, Text, Integer, JSON

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class SyntheticPersona(db.Model, ModelMixin):

    __tablename__ = "synthetic_personas"

    name = Column(Text, unique=True, nullable=False)
    background = Column(Text, nullable=False)
    traits = Column(JSON, nullable=False)  # list of trait value strings
    attachment_style = Column(Text, nullable=False)  # AttachmentStyle value
    presenting_problem = Column(Text, nullable=False)
    data_points = Column(JSON, nullable=True)  # [{category, keywords}]
    sex = Column(Text, nullable=False)  # "male" / "female"
    age = Column(Integer, nullable=False)

    def to_persona(self):
        from btcopilot.tests.personal.synthetic import (
            Persona,
            PersonaTrait,
            AttachmentStyle,
            DataPoint,
            DataCategory,
        )

        return Persona(
            name=self.name,
            background=self.background,
            attachmentStyle=AttachmentStyle(self.attachment_style),
            traits=[PersonaTrait(t) for t in self.traits],
            presenting_problem=self.presenting_problem,
            dataPoints=[
                DataPoint(DataCategory(dp["category"]), dp["keywords"])
                for dp in (self.data_points or [])
            ],
        )
