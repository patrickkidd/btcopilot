I need to get btcopilot to store the PDP in the diagram files used by FD.
Diagram files are currently stored as python pickle bytes in the sqlalchemy
model column btcopilot.pro.models.Diagram.data. I have started a proto
getter/setter instance method api in Diagram.get_diagram_data and
Diagram.set_diagram_data which takes a python dataclass from btcopilot.schema as
an argument. I want to improve these two instance methods, or methods on the
passed DiagramData dataclass, to allow editing the contents of Diagram.data in a
way that the familydiagram app can read. Right now, btcopilot does not add items
to the diagram file directly, but sets up a pending data pool (PDP) that the
user is supposed to confirm one item at a time or all items at once. So I guess
what I want is for the DiagramData dataclass to be able to add PDP deltas to
itself in the format that the FD app requires. Some deltas are dependent on
other deltas, like a new event that references a person, for example. So the api
will need to validate that the passed details can even be added without breakign
the data.