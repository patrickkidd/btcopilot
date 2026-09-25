# Live evals

Real coach turns on the private prompts, paid on the testing key. How to run them, the
caps and the results files are described at the top of `conftest.py`. Pass rates by
model: `uv run python -m btcopilot.tests.live.passrate`.

The paid suite, as it would run:

    uv run pytest btcopilot/tests/live -m "not waiting" --collect-only -q

## Waiting list

These evals check a coding on the record: a symptom, anxiety or functioning shift, or a
relationship move. Their coding rule is undecided. They stay in the files, marked
`waiting`, and never run until the rule is ratified.

| Test | What the speaker says | Undecided code | Status |
|------|-----------------------|----------------|--------|
| `test_a_feeling_that_interferes_with_work_is_a_symptom` (R-0424) | "My hands shake so badly before work that I've started calling in sick." | symptom up on the speaker | awaits ratified ground truth from the IRR review group |
| `test_a_feeling_that_interferes_with_nothing_is_not_a_symptom` (R-0424) | "I get a little nervous before big meetings, but it never gets in the way of anything." | no symptom | awaits ratified ground truth from the IRR review group |
| `test_a_diagnosis_is_symptom_up_on_the_person_it_happened_to_dated_when_it_happened` (R-0425) | "My mother was diagnosed with breast cancer in March 2019." | symptom up on the mother, dated 2019 | awaits ratified ground truth from the IRR review group |
| `test_the_coach_infers_anxiety_down_from_what_is_described` (R-0427) | "My dad finally retired last year and he seems so much more relaxed now." | anxiety down on the father | awaits ratified ground truth from the IRR review group |
| `test_the_coach_infers_anxiety_up_around_a_stressor_half_remembered` (R-0427) | "I barely remember the year we moved, except that my parents fought about money." | anxiety up | awaits ratified ground truth from the IRR review group |
| `test_things_rocky_since_the_divorce_is_functioning_down_on_the_speaker` (R-0428) | "Things have always been rocky for me since the divorce." | functioning down on the speaker | awaits ratified ground truth from the IRR review group |
| `test_mom_diagnosis_is_a_symptom_on_mom_and_stepping_back_is_under_and_over_functioning` (R-0433) | "My brother Colm lives nearby. Ever since Mom got her diagnosis, he's stepped back and I'm doing everything." | symptom up on the mother; underfunctioning on the brother, overfunctioning on the speaker | awaits ratified ground truth from the IRR review group |
| `test_a_visit_and_an_argument_is_one_conflict_event_from_the_visitor_to_the_speaker` (R-0434) | "Michael came over to visit, and we ended up arguing." | one conflict, from Michael to the speaker | awaits ratified ground truth from the IRR review group |
| `test_projection_is_coded_in_the_turn_it_is_described_without_asking` (R-0435) | "Finn's grades slipped last fall and I got so anxious about him that I was checking his homework every night and on him constantly." | projection, coded without asking | awaits ratified ground truth from the IRR review group |
| `test_a_shift_said_again_makes_no_second_event_and_is_folded_into_the_first` (R-0442) | "Like I said, I was really worried after we moved in 2019, I couldn't sleep." | the anxiety-up shift already on the record | awaits ratified ground truth from the IRR review group |
| `test_a_couple_splitting_over_having_kids_is_an_away_move_between_the_two_of_them` (R-0057) | "Rory and I split up in 2015 because he wanted kids and I didn't." | an away move between the speaker and Rory | awaits ratified ground truth from the IRR review group |
| `test_a_move_carries_no_symptom_anxiety_or_functioning_shift` (R-0366) | "We moved to Arizona in early 2000." | no symptom, anxiety or functioning shift on the move | awaits ratified ground truth from the IRR review group |
