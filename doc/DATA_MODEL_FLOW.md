  # Diagram Data Handling Analysis - btcopilot & familydiagram

   ## Overview
   This document provides a comprehensive analysis of how diagram data is currently handled in the Family Diagram application ecosystem, including the data structures, persistence mechanisms, and
    the Pending Data Pool (PDP) system.

   ---

   ## 1. Core Data Structures (btcopilot.schema)

   ### 1.1 DiagramData (Top-level Container)
   ```python
   @dataclass
   class DiagramData:
       people: list[Person] = field(default_factory=list)
       events: list[Event] = field(default_factory=list)
       pdp: PDP = field(default_factory=PDP)
       lastItemId: int = field(default=0)

       def add_person(self, person: Person) -> None:
           person.id = self._next_id()
           self.people.append(person)

       def add_event(self, event: Event) -> None:
           event.id = self._next_id()
           self.events.append(event)

       def _next_id(self) -> int:
           self.lastItemId += 1
           return self.lastItemId
   ```

   **Purpose**: Represents the complete diagram state with both committed data (people/events) and pending data (pdp).

   **Key Fields**:
   - `people`: Confirmed/committed Person objects
   - `events`: Confirmed/committed Event objects
   - `pdp`: Pending Data Pool containing unconfirmed extractions
   - `lastItemId`: Counter for generating unique IDs

   ---

   ### 1.2 Person (Individual)
   ```python
   @dataclass
   class Person:
       id: int | None = None
       name: str | None = None
       last_name: str | None = None
       parents: int | None = None  # PairBond ID
       confidence: float | None = None  # PDP-specific
   ```

   **ID Convention**:
   - Positive integers (1, 2, 3, ...): Committed/confirmed people
   - Negative integers (-1, -2, -3, ...): PDP pending entries
   - Default IDs: 1 = "User", 2 = "Assistant"

   **Relationships**:
   - `parents`: PairBond ID representing the person's parents
     - **IMPORTANT**: A person has exactly ONE pairbond of parents (two people), not multiple pairbonds
     - Biology: Every person has exactly two biological parents
     - Backend schema (schema.py): single integer referencing a PairBond object's ID
     - PDP/Frontend: May represent as `[parent1_id, parent2_id]` (list of two person IDs) for pending data before PairBond creation
     - When committing PDP data, frontend must create a PairBond object first, then reference its ID
   - Spouses/partners are inferred from PairBond entries and Events

   **Confidence**:
   - 1.0 = Confirmed in main database
   - 0.0-0.9 = Pending in PDP, confidence level of extraction

   ---

   ### 1.3 Event (State Change)
   ```python
   @dataclass
   class Event:
       id: int
       kind: EventKind
       person: int | None = None          # Primary person for event
       spouse: int | None = None
       child: int | None = None
       description: str | None = None
       dateTime: str | None = None
       endDateTime: str | None = None
       symptom: VariableShift | None = None
       anxiety: VariableShift | None = None
       relationship: RelationshipKind | None = None
       relationshipTargets: list[int] = field(default_factory=list)
       relationshipTriangles: list[tuple[int, int]] = field(default_factory=list)
       functioning: VariableShift | None = None
       confidence: float | None = None    # PDP-specific
   ```

   **EventKind Enum**:
   ```python
   class EventKind(enum.Enum):
       Bonded = "bonded"
       Married = "married"
       Birth = "birth"
       Adopted = "adopted"
       Moved = "moved"
       Separated = "separated"
       Divorced = "divorced"
       Shift = "shift"          # Generic state change
       Death = "death"
   ```

   **VariableShift Enum**:
   ```python
   class VariableShift(enum.StrEnum):
       Up = "up"
       Down = "down"
       Same = "same"
   ```

   **RelationshipKind Enum**:
   ```python
   class RelationshipKind(enum.Enum):
       Fusion = "fusion"
       Conflict = "conflict"
       Distance = "distance"
       Overfunctioning = "overfunctioning"
       Underfunctioning = "underfunctioning"
       Projection = "projection"
       DefinedSelf = "defined-self"
       Toward = "toward"
       Away = "away"
       Inside = "inside"
       Outside = "outside"
       Cutoff = "cutoff"
   ```

   ---

   ### 1.4 PDP (Pending Data Pool)
   ```python
   @dataclass
   class PDP:
       people: list[Person] = field(default_factory=list)
       events: list[Event] = field(default_factory=list)
   ```

   **Purpose**: Container for pending extractions waiting user confirmation.

   **Characteristics**:
   - Contains unconfirmed Person and Event entries
   - All IDs are negative integers
   - All confidence values < 1.0
   - User can accept (move to main DiagramData) or reject

   ---

   ### 1.5 PDPDeltas (Change Set)
   ```python
   @dataclass
   class PDPDeltas:
       people: list[Person] = field(default_factory=list)
       events: list[Event] = field(default_factory=list)
       delete: list[int] = field(default_factory=list)
   ```

   **Purpose**: Represents only NEW or CHANGED items to apply to PDP.

   **CRITICAL DESIGN PATTERN**:
   - **SPARSE**: Most deltas contain very few items (often empty arrays)
   - **NEW ONLY**: Don't re-extract existing data
   - **SINGLE EVENT**: Each statement typically generates 0-1 new events
   - **UPDATE ONLY CHANGED FIELDS**: When updating existing items

   **Use Cases**:
   1. **New person mentioned**: Add to `people` list
   2. **New event/incident**: Add to `events` list
   3. **Update existing person**: Include only changed fields (name correction, new relationship)
   4. **Delete after correction**: Add ID to `delete` list

   ---

   ## 2. Persistence Layer

   ### 2.1 Diagram Model (btcopilot.pro.models.diagram)

   Database Storage:
   ```python
   class Diagram(db.Model, ModelMixin):
       __tablename__ = "diagrams"

       user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
       name = Column(String)
       alias = Column(String)
       use_real_names = Column(Boolean)
       require_password_for_real_names = Column(Boolean)

       data = Column(LargeBinary)  # Pickled binary blob
       access_rights = relationship(...)
       discussions = relationship(...)
   ```

   **Key Methods**:

   ```python
   def get_diagram_data(self) -> DiagramData:
       """Load DiagramData from pickled binary blob"""
       data = pickle.loads(self.data) if self.data else {}
       return DiagramData(
           people=data.get("people", []),
           events=data.get("events", []),
           pdp=data.get("pdp", PDP()),
           lastItemId=data.get("lastItemId", 0),
       )

   def set_diagram_data(self, diagram_data: DiagramData):
       """Save DiagramData to pickled binary blob"""
       data = pickle.loads(self.data) if self.data else {}
       data["people"] = diagram_data.people
       data["events"] = diagram_data.events
       data["pdp"] = diagram_data.pdp
       data["lastItemId"] = diagram_data.lastItemId
       self.data = pickle.dumps(data)
   ```

   **Data Format**:
   - **Pickle Protocol**: Binary serialization format (Python-specific)
   - **Storage**: LargeBinary column in PostgreSQL
   - **Preservation**: Existing scene data is preserved when updating DiagramData
   - **Nested dict structure**:
     ```
     {
       "people": [Person objects],
       "events": [Event objects],
       "pdp": PDP object,
       "lastItemId": int,
       ... other scene data preserved
     }
     ```

   ---

   ### 2.2 Statement Model (btcopilot.personal.models.statement)

   Links extracted data to conversation:
   ```python
   class Statement(db.Model, ModelMixin):
       __tablename__ = "statements"

       text = Column(Text)
       discussion_id = Column(Integer, ForeignKey("discussions.id"))
       speaker_id = Column(Integer, ForeignKey("speakers.id"))
       pdp_deltas = Column(JSON)  # Stores PDPDeltas as JSON
       custom_prompts = Column(JSON)
       order = Column(Integer)

       approved = Column(Boolean, default=False)
       approved_by = Column(String(100))
       approved_at = Column(DateTime)
       exported_at = Column(DateTime)

       discussion = relationship("Discussion", back_populates="statements")
       speaker = relationship("Speaker", back_populates="statements")
   ```

   **pdp_deltas Column**:
   - Stores `asdict(PDPDeltas)` converted to JSON
   - JSON structure:
     ```json
     {
       "people": [
         {"id": -1, "name": "Mom", "confidence": 0.8},
         {"id": 1, "name": "Alice", "confidence": 0.99}
       ],
       "events": [
         {"id": -2, "kind": "shift", "person": 1, ...}
       ],
       "delete": [4]
     }
     ```

   ---

   ## 3. Data Flow: Extraction Process

   ### 3.1 The Chat Flow (btcopilot.personal.chat)

   1. **User submits statement**
      ```python
      discussion = Discussion(diagram_id=diagram_id)
      user_statement = "I felt anxious when mom called yesterday"
      ```

   2. **Load current state**
      ```python
      if discussion.diagram:
          diagram_data = discussion.diagram.get_diagram_data()
      else:
          diagram_data = DiagramData()
      ```

   3. **Run extraction pipeline**
      ```python
      (new_pdp, pdp_deltas), response_direction = gather(
          pdp.update(discussion, diagram_data, user_statement),
          detect_response_direction(user_statement, discussion),
      )
      ```

   4. **Update PDP in storage**
      ```python
      diagram_data.pdp = new_pdp
      if discussion.diagram:
          discussion.diagram.set_diagram_data(diagram_data)
      ```

   5. **Store statement with deltas**
      ```python
      statement = Statement(
          discussion_id=discussion.id,
          text=user_statement,
          pdp_deltas=asdict(pdp_deltas) if pdp_deltas else None,
          speaker=discussion.chat_user_speaker,
      )
      db.session.add(statement)
      ```

   ---

   ### 3.2 Delta Extraction (btcopilot.pdp)

   **async def update()**:
   ```python
   async def update(
       thread: Discussion,
       diagram_data: DiagramData,
       user_message: str
   ) -> tuple[PDP, PDPDeltas]:
       """
       Compiles prompts, runs LLM, and returns both updated PDP and the deltas.
       """
       SYSTEM_PROMPT = f"""
       {PDP_ROLE_AND_INSTRUCTIONS}

       **Existing Diagram State (DO NOT RE-EXTRACT THIS DATA):**
       {asdict(diagram_data)}

       **Conversation History (for context only):**
       {thread.conversation_history()}

       **NEW USER STATEMENT TO ANALYZE FOR DELTAS:**
       {user_message}
       """

       pdp_deltas = await llm.submit(
           LLMFunction.JSON,
           prompt=SYSTEM_PROMPT,
           response_format=PDPDeltas,
       )

       new_pdp = apply_deltas(diagram_data.pdp, pdp_deltas)
       return new_pdp, pdp_deltas
   ```

   **apply_deltas()**:
   ```python
   def apply_deltas(pdp: PDP, deltas: PDPDeltas) -> PDP:
       """
       Return a copy of the PDP with the deltas applied.
       Handles:
       - Adding new people/events
       - Updating existing entries (only changed fields)
       - Deleting items
       """
       pdp = copy.deepcopy(pdp)

       # Build ID maps for upsert logic
       people_by_id = {item.id: item for item in pdp.people}
       events_by_id = {item.id: item for item in pdp.events}

       # Separate adds and updates
       people_to_update = [
           (item, people_by_id[item.id])
           for item in deltas.people
           if item.id in people_by_id
       ]
       people_to_add = [item for item in deltas.people if item.id not in people_by_id]

       # Apply updates (only changed fields)
       for item, existing in to_update_all:
           for field in getattr(item, "model_fields_set", set()):
               value = getattr(item, field)
               if hasattr(existing, field):
                   setattr(existing, field, value)

       # Add new items
       for item in to_add_people:
           pdp.people.append(item)

       for item in to_add_events:
           pdp.events.append(item)

       # Handle deletes
       for idx in reversed(range(len(pdp.people))):
           if pdp.people[idx].id in to_delete_ids:
               del pdp.people[idx]

       return pdp
   ```

   ---

   ### 3.3 PDP Acceptance/Rejection (btcopilot.personal.routes.diagrams)

   **Accept (move from PDP to main database)**:
   ```python
   @diagrams_bp.route("/<int:diagram_id>/pdp/<int:pdp_id>/accept", methods=["POST"])
   def pdp_accept(diagram_id: int, pdp_id: int):
       database = diagram.get_diagram_data()
       pdp_id = -pdp_id  # Convert negative ID back

       for person in database.pdp.people:
           if person.id == pdp_id:
               database.pdp.people.remove(person)
               database.add_person(person)  # Assigns new positive ID
               diagram.set_diagram_data(database)
               db.session.commit()
               return jsonify(success=True)

       for event in database.pdp.events:
           if event.id == pdp_id:
               database.pdp.events.remove(event)
               database.add_event(event)  # Assigns new positive ID
               diagram.set_diagram_data(database)
               db.session.commit()
               return jsonify(success=True)
   ```

   **Reject (discard from PDP)**:
   ```python
   @diagrams_bp.route("/<int:diagram_id>/pdp/<int:pdp_id>/reject", methods=["POST"])
   def pdp_reject(diagram_id: int, pdp_id: int):
       database = diagram.get_diagram_data()
       pdp_id = -pdp_id

       for person in database.pdp.people:
           if person.id == pdp_id:
               database.pdp.people.remove(person)
               diagram.set_diagram_data(database)
               db.session.commit()
               return jsonify(success=True)

       # Similar for events...
   ```

   ---

   ## 4. Example Delta Types

   ### 4.1 Simple Event with Anxiety Shift
   ```python
   PDPDeltas(
       people=[],
       events=[
           Event(
               id=-2,
               kind=EventKind.Shift,
               person=1,
               description="Felt anxious when mom called",
               dateTime="2025-08-11",
               anxiety=VariableShift.Up,
               confidence=0.8
           )
       ],
       delete=[]
   )
   ```

   ### 4.2 New Person + Relationship Event
   ```python
   PDPDeltas(
       people=[
           Person(id=-5, name="Mother", confidence=0.9)
       ],
       events=[
           Event(
               id=-6,
               kind=EventKind.Shift,
               person=1,
               description="Told brother about mom's meddling",
               relationship=RelationshipKind.Conflict,
               relationshipTargets=[-5],
               confidence=0.7
           )
       ],
       delete=[]
   )
   ```

   ### 4.3 Update Existing Entry + Delete
   ```python
   PDPDeltas(
       people=[
           Person(id=-1, name="Mother", confidence=0.95)
       ],
       events=[],
       delete=[3, 4]  # Remove incorrectly extracted entries
   )
   ```

   ### 4.4 Multiple Relationships (Triangle)
   ```python
   PDPDeltas(
       people=[
           Person(id=-3, name="Brother", confidence=0.8)
       ],
       events=[
           Event(
               id=-4,
               kind=EventKind.Shift,
               person=1,
               description="Triangled brother against mother",
               relationship=RelationshipKind.Inside,  # or Outside
               relationshipTriangles=[(1, -3)],  # Inside vs outside
               confidence=0.7
           )
       ],
       delete=[]
   )
   ```

   ---

   ## 5. FamilyDiagram App Integration

   ### 5.1 Client-Side Diagram Type (pkdiagram.server_types)
   ```python
   @dataclass
   class Diagram:
       id: int
       user_id: int
       access_rights: list[AccessRight]
       created_at: datetime
       updated_at: datetime | None = None
       name: str | None = None
       user: User | None = None
       use_real_names: bool | None = None
       require_password_for_real_names: bool | None = None
       data: bytes | None = None  # Pickled scene data
       pdp: dict | None = None    # PDP structure
       discussions: list[Discussion] = field(default_factory=list)

       def check_access(self, user_id, right):
           if user_id == self.user_id:
               return True
           for access_right in self.access_rights:
               if access_right.user_id == user_id:
                   if right in (btcopilot.ACCESS_READ_WRITE, btcopilot.ACCESS_READ_ONLY):
                       return True
           return False
   ```

   ### 5.2 Scene Serialization (familydiagram)
   - Uses pickle to serialize Qt scene objects
   - Scene data is preserved when updating DiagramData
   - Client reads/writes pickle format from server

   ---

   ## 6. Validation & Constraints

   ### 6.1 ID Management
   ```
   Committed: 1, 2, 3, ... (positive integers)
   PDP:       -1, -2, -3, ... (negative integers)
   ```

   ### 6.2 Person Constraints
   - Each person has at most one parents PairBond
   - Spouses/partners are represented via PairBond entries
   - Deduplication by name when extracting

   ### 6.3 Event Constraints
   - One event per variable shift (merge by timestamp, people, variables)
   - Relationship events require targets or triangles
   - Triangle requires: 2 inside + 1 outside (or vice versa)

   ### 6.4 Confidence Levels
   ```
   Committed: 1.0
   PDP:       0.0 - 0.9 (based on extraction confidence)
   ```

   ---

   ## 7. Prompt Engineering for Deltas

   ### 7.1 System Instructions
   The LLM is instructed with:

   **Key Rules**:
   1. **SPARSE OUTPUT**: Most deltas contain very few items, often empty arrays
   2. **NEW ONLY**: Don't re-extract existing data already in the database
   3. **SINGLE EVENTS**: Each statement typically generates 0-1 new events
   4. **UPDATE ONLY CHANGED FIELDS**: When updating, only include fields that changed

   **Example Scenario**:
   ```
   User says: "My brother-in-law didn't talk to us when he got home from work."

   Current database has:
   - User (id=1)
   - Assistant (id=2)
   - Brother-in-law (id=-1, in PDP)

   Output should be:
   {
     "people": [],  // Empty! Brother-in-law already exists
     "events": [
       {
         "id": -2,
         "kind": "shift",
         "person": -1,
         "description": "Didn't talk when he got home from work",
         "relationship": "distance",
         "relationshipTargets": [1],
         "confidence": 0.7
       }
     ],
     "delete": []
   }
   ```

   ---

   ## 8. Current Data Flow Summary

   ```
   familydiagram (Desktop App)
       ↓
       └─→ Server: POST/PATCH /diagrams/{id}
           └─→ btcopilot.pro.routes.diagrams()
               └─→ Diagram.set_diagram_data(diagram_data)
                   └─→ pickle.dumps() → LargeBinary column

   User Chat Flow:
       ↓
       └─→ Personal API: POST /personal/discussions/{id}/ask
           └─→ btcopilot.personal.chat.ask()
               ├─→ Load: diagram.get_diagram_data()
               ├─→ Extract: pdp.update() → LLM returns PDPDeltas
               ├─→ Apply: pdp.apply_deltas() → new_pdp
               ├─→ Store: diagram.set_diagram_data(updated)
               └─→ Save: statement.pdp_deltas = asdict(PDPDeltas)

   PDP Workflow:
       ↓
       User sees PDP items in UI
       ├─→ Accept: POST /diagrams/{id}/pdp/{pdp_id}/accept
       │   └─→ Move from PDP to main database (negative → positive ID)
       │
       └─→ Reject: POST /diagrams/{id}/pdp/{pdp_id}/reject
           └─→ Remove from PDP
   ```

   ---

   ## Key Takeaways

   1. **Pickle-based Storage**: Diagram data is serialized as pickle binary, preserving existing scene data
   2. **Negative IDs for PDP**: All pending entries use negative IDs for easy identification
   3. **Sparse Deltas**: PDPDeltas should contain only NEW or CHANGED items, not entire dataset
   4. **Confidence Tracking**: Confidence scores (0-1) distinguish committed (1.0) from pending (0-0.9) data
   5. **Stateful Updates**: apply_deltas() uses model_fields_set to identify only changed fields
   6. **Two Stages**: AI extracts deltas → user reviews → accepts/rejects to confirm
   7. **JSON-Storable**: PDPDeltas convert to JSON via asdict() for Statement.pdp_deltas column
   8. **Enumeration**: EventKind, VariableShift, RelationshipKind provide structured event types

   ---

   ## 9. Implementation File Reference

   ### btcopilot - Core Schema
   - [btcopilot/schema.py](../btcopilot/schema.py) - All dataclasses (DiagramData, Person, Event, PDP, PDPDeltas) plus enums and helper functions

   ### btcopilot - Models & Persistence
   - [btcopilot/pro/models/diagram.py](../btcopilot/pro/models/diagram.py) - Diagram SQLAlchemy model with get/set_diagram_data()
   - [btcopilot/personal/models/statement.py](../btcopilot/personal/models/statement.py) - Statement model with pdp_deltas JSON column

   ### btcopilot - Processing Logic
   - [btcopilot/personal/pdp.py](../btcopilot/personal/pdp.py) - update(), apply_deltas(), cumulative()
   - [btcopilot/personal/chat.py](../btcopilot/personal/chat.py) - ask() integrates extraction + storage + response
   - [btcopilot/personal/prompts.py](../btcopilot/personal/prompts.py) - PDP_ROLE_AND_INSTRUCTIONS and other LLM prompts

   ### btcopilot - API Routes
   - [btcopilot/personal/routes/diagrams.py](../btcopilot/personal/routes/diagrams.py) - PDP accept/reject endpoints
   - [btcopilot/pro/routes.py](../btcopilot/pro/routes.py) - Diagram CRUD endpoints

   ### familydiagram - Client Integration
   - [familydiagram/pkdiagram/server_types.py](../../familydiagram/pkdiagram/server_types.py) - Client-side Diagram, Discussion, Statement types
   - [familydiagram/pkdiagram/models/serverfilemanagermodel.py](../../familydiagram/pkdiagram/models/serverfilemanagermodel.py) - Local caching and sync

   ### Test Files
   - [btcopilot/tests/personal/test_pdp.py](../btcopilot/tests/personal/test_pdp.py) - PDPDeltas usage and apply_deltas() tests
   - [btcopilot/tests/training/test_pdp.py](../btcopilot/tests/training/test_pdp.py) - Comprehensive extraction examples
   - [btcopilot/tests/pro/test_diagrams.py](../btcopilot/tests/pro/test_diagrams.py) - Pickle serialization patterns
   - [familydiagram/tests/personal/](../../familydiagram/tests/personal/) - Client integration tests

   ---

   ## 10. Common Code Patterns

   ### Loading Diagram Data
   ```python
   diagram = Diagram.query.get(diagram_id)
   diagram_data = diagram.get_diagram_data()
   # Returns: DiagramData(people=[...], events=[...], pdp=PDP(...), lastItemId=123)
   ```

   ### Saving Diagram Data
   ```python
   diagram_data.pdp = new_pdp
   if discussion.diagram:
       discussion.diagram.set_diagram_data(diagram_data)
   db.session.commit()
   ```

   ### Extracting Deltas
   ```python
   pdp_deltas = await llm.submit(
       LLMFunction.JSON,
       prompt=SYSTEM_PROMPT,
       response_format=PDPDeltas,
   )
   new_pdp = apply_deltas(diagram_data.pdp, pdp_deltas)
   ```

   ### Converting to/from JSON
   ```python
   from btcopilot.schema import asdict, from_dict

   # Serialize to JSON
   pdp_dict = asdict(pdp_deltas)
   statement.pdp_deltas = pdp_dict

   # Deserialize from JSON
   pdp_deltas = from_dict(PDPDeltas, statement.pdp_deltas)
   ```

   ### Accepting PDP Item
   ```python
   database = diagram.get_diagram_data()
   for person in database.pdp.people:
       if person.id == pdp_id:
           database.pdp.people.remove(person)
           database.add_person(person)  # Assigns new positive ID
           diagram.set_diagram_data(database)
           db.session.commit()
   ```

   ---

   ## 11. Storage Flow Details

   ### Pickle vs JSON
   - **Pickle**: Used for entire DiagramData in Diagram.data column (preserves Qt scene objects)
   - **JSON**: Used for PDPDeltas in Statement.pdp_deltas column

   ### Complete Storage Pipeline
   ```
   LLM → PDPDeltas (Python object)
       ↓
       asdict(PDPDeltas)
       ↓
       JSON (Statement.pdp_deltas column)
       ↓
       from_dict(PDPDeltas, json_data)
       ↓
       apply_deltas(pdp, pdp_deltas)
       ↓
       Updated PDP object
       ↓
       pickle.dumps(diagram_data)
       ↓
       Diagram.data (LargeBinary)
   ```

   ### Pickled Diagram Data Structure
   ```python
   # What's in Diagram.data column:
   {
       "people": [Person(id=1, name="User", confidence=1.0), ...],
       "events": [Event(id=1, kind=EventKind.Shift, ...), ...],
       "pdp": PDP(
           people=[Person(id=-1, name="Mom", confidence=0.8)],
           events=[Event(id=-2, ...), ...]
       ),
       "lastItemId": 2,
       ... other scene data preserved
   }
   ```

---

## 12. Training App & SARF Ground Truth Coding

### Overview

The btcopilot training app extends the data model with a ground truth coding workflow for model training and evaluation. While the personal app uses AI to extract SARF (Symptom, Anxiety, Relationship, Functioning) data from conversations, the training app allows domain experts to review, correct, and approve these extractions as ground truth.

**Key Distinction**:
- **Personal App**: Uses `Statement.pdp_deltas` for AI-generated extractions that update the diagram PDP
- **Training App**: Adds `Feedback.edited_extraction` for expert corrections and approval workflows

### Data Models Comparison

| Model | Column | Purpose | Format | Workflow |
|-------|--------|---------|--------|----------|
| Statement | pdp_deltas | AI extraction | JSON (PDPDeltas) | Personal app: Extract → Apply to PDP<br>Training app: Extract → Expert review |
| Feedback | edited_extraction | Expert correction | JSON (PDPDeltas) | Expert edits → Admin approves → Export as test case |

### Approval Workflow

**Mutual Exclusivity Rule**: For any statement, EITHER the AI extraction OR one expert correction can be approved as ground truth, never both.

```
User Statement
     ↓
AI Extracts → Statement.pdp_deltas
     ↓
Expert Reviews in SARF Editor
     ├─→ AI Correct → Admin approves Statement → Export AI version
     └─→ AI Wrong → Expert corrects → Feedback.edited_extraction
                                    ↓
                          Admin approves Feedback → Export corrected version
```

**Enforcement** ([btcopilot/training/routes/admin.py](../btcopilot/training/routes/admin.py)):
- Approving Statement unapproves all Feedback for that statement
- Approving Feedback unapproves Statement and all other Feedback

### Export to Test Cases

Approved ground truth is exported to `./model_tests/data/uncategorized/` as JSON files:

**File Format**:
```json
{
  "test_id": "stmt_123",
  "source": "statement" | "feedback",
  "inputs": {
    "conversation_history": [...],
    "database": {...},
    "current_pdp": {...},
    "user_statement": "..."
  },
  "expected_output": <PDPDeltas>,
  "original_output": <PDPDeltas>  // Only in feedback exports
}
```

**Usage**: Test cases feed model training pipeline for fine-tuning SARF extraction accuracy.

### SARF Editor UI Component

**Main Component**: [btcopilot/training/templates/components/extracted_data_display.html](../btcopilot/training/templates/components/extracted_data_display.html)

**Features**:
- Inline editing of person names, event descriptions, SARF variables
- Tabs to switch between AI extraction and multiple expert corrections (admin only)
- Approval buttons with mutual exclusivity enforcement
- Collapsible summary view showing shift indicators

**Alpine.js State Management**: Tracks editing state, tab selection, approval status, and person data version for reactive updates.

### Critical Differences from Personal App Data Flow

| Aspect | Personal App | Training App |
|--------|-------------|--------------|
| **Purpose** | Real-time diagram updates | Ground truth collection |
| **Storage** | Diagram.data (pickle) | Statement/Feedback (JSON) |
| **Approval** | Automatic (AI accepted) | Manual (admin approves) |
| **Deltas** | Applied via apply_deltas() | Displayed via cumulative() |
| **Export** | None | Test case JSON files |

**Important**: `cumulative()` in training app is for display context only (shows "what AI knew so far"). It does NOT process deletes like `apply_deltas()` does in personal app. See [SARF_GROUND_TRUTH_TECHNICAL.md](./SARF_GROUND_TRUTH_TECHNICAL.md) section 5.3 for details.

### For Complete Technical Details

See **[SARF_GROUND_TRUTH_TECHNICAL.md](./SARF_GROUND_TRUTH_TECHNICAL.md)** for comprehensive documentation including:
- Approval state machine implementation
- SARF variable schema (VariableShift, RelationshipKind enums)
- UI component architecture and Alpine.js patterns
- API endpoints for feedback submission and approval
- Export pipeline and test case format
- Design patterns and gotchas (negative IDs, cumulative vs apply_deltas, etc.)
- Testing considerations and migration path for schema changes