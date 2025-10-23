Problem/Acceptance Criteria

- btcopilot and FD need to write the same data to server diagrams, so they need to share the same data structure definitions.
- btcopilot needs to use pydantic_ai for llm structured outputs but FD can't embed pydantic into the exe.

Proposed Solution

1. Move btcopilot.personal.database to btcopilot.schema
3. Subdivide btcopilot wheel into this schema section with zero-to-lightweight dependencies and the rest of the server arch that imports langchain, transformers, etc.
3. Update "event" in schema in btcopilot to be compatible with familydiagram's event.py data model:
    - Move EventKind and RelationshipKind to btcopilot.schema
    - Add `kind: EventKind` to btcopilot event
    - Add `person`, `spouse`, `child` to btcopilot Events
    - When `event.kind().isOffspring()`, ensure Event.child and Event.spouse is set (`isPairBond()` is always True when `isOffspring()` is True )
    - When `event.kind().isPairBond()`, ensure Event.spouse is set
    - When `event.kind() == EventKind.Shift`, ensure `relationship: RelationshipKind` and `Event.relationshipTargets` is not empty
        - When `event.kind() == EventKind.Shift and event.kind() in (EventKind.Inside, EventKind.Outside)`, ensure `Event.relationshipTriangles` is set.
4. Add `UP_TO('2.0.12b3')` migration to `familydiagram/models/compat.py` to read old FD pickle+Qt FD file format and convert to new JSON+btcopilot.schema format that matches the bew btcopilot.schema format.
5. Make familydiagram import btcopilot.schema and build object tree from new JSON file format
6. Use generic data classes that can be converted to pydantic classes or something?
7. Replace pickle+Qt FD file format with JSON+btcopilot.schema

Rules:
- Don't worry about maintaining backwaard compatibility within the  btcopilot
  repo, there is no production data there. Just get the code right as of now.
- The schema is used to define the object relationships and value ranges for
  enums, etc to pydantic_ai, so we need to define all of that hierarchy with
  value spaces in a single schema class under PDP and Database as before. I
  realize I changed the relationship subdivisions, but I did have classes and
  subclasses for the different relationship kinds, variable shift values,etc. If
  these aren't needed anymore that's fine, but the key requirement is passing
  the complete expected output object hierarchy and value spaces as a single
  pydantic class to pydantic_ai for the expected structured outputs
- Don't use __all__ in python modules, it isn't necessary for this mostly private code base.