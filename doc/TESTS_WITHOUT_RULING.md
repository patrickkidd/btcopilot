# Tests that prove no ruling (R-0421)

Each test below says `no ruling` on its top line: it proves plumbing, a helper, or a
behaviour nobody has ruled. For each, the owner either rules the behaviour (and the
test cites the new id) or the test is deleted. One line each: the test, then what it
proves, taken from its own docstring or name. Swept 2026-09-23.

## btcopilot/tests/chat/personal/test_agent.py

- `test_a_turn_that_fails_before_the_coach_answers_stores_no_words` — a turn that fails before the coach answers stores no words.
- `test_people_and_their_events_all_land_in_one_turn` — A turn that adds the people and stops has lost what was said about them: the coach keeps calling tools until every dated fact is in the record.
- `test_the_words_before_a_tool_call_are_not_the_coach_speaking` — The model works out what to do in the open.
- `test_a_turn_that_never_stops_calling_tools_still_says_something` — The page shows what the coach said, so a turn may not end on a tool call.
- `test_a_turn_with_no_words_at_all_fails_rather_than_showing_a_bare_bubble` — a turn with no words at all fails rather than showing a bare bubble.
- `test_a_csrf_token_older_than_an_hour_still_posts` — The token the page is stamped with lives as long as the session it belongs to.
- `test_a_model_with_no_price_raises` — a model with no price raises.
- `test_tracing_provider` — tracing provider.

## btcopilot/tests/chat/personal/test_api.py

- `test_session_list_omits_a_transcript_import` — A discussion brought in from a recording has no chat speaker ids and is not a session the chat app can open.
- `test_session_create` — session create.
- `test_session_switch_by_last_activity` — session switch by last activity.
- `test_session_statements` — session statements.
- `test_session_delete_keeps_the_record` — session delete keeps the record.
- `test_session_delete_of_another_user_is_not_found` — session delete of another user is not found.
- `test_session_rename_rejects_unknown_field` — session rename rejects unknown field.
- `test_chat_requires_json` — chat requires json.
- `test_session_of_another_user_is_not_found` — session of another user is not found.
- `test_preferences_rejects_unknown_key` — preferences rejects unknown key.
- `test_preferences_rejects_bad_value` — preferences rejects bad value.
- `test_read_only_grant_is_not_listed_or_writable` — read only grant is not listed or writable.
- `test_a_named_record_takes_the_write_and_a_stranger_s_does_not` — The coding screen writes onto the record its coding is of, which it names on the request; a record the user may not write is refused.
- `test_event_rejects_unknown_field` — event rejects unknown field.
- `test_event_rejects_unknown_person` — event rejects unknown person.
- `test_event_of_missing_id_is_404` — event of missing id is 404.

## btcopilot/tests/chat/personal/test_caching.py

- `test_what_the_call_cost_and_what_it_read_back_is_logged` — what the call cost and what it read back is logged.
- `test_the_coach_asks_for_its_effort_and_no_sampling` — the coach asks for its effort and no sampling.
- `test_a_model_without_effort_sends_none` — a model without effort sends none.
- `test_thinking_goes_back_unchanged_before_the_tool_call` — thinking goes back unchanged before the tool call.
- `test_a_model_that_takes_no_fallbacks_is_sent_none` — a model that takes no fallbacks is sent none.
- `test_a_model_cut_off_mid_answer_leaves_no_tool_call_to_run` — a model cut off mid answer leaves no tool call to run.

## btcopilot/tests/chat/personal/test_chatpage.py

- `test_page_loads` — The page is the built web bundle: the picture, the composer, and the menu that holds the timeline.
- `test_page_carries_what_only_the_server_knows` — The bundle is static; the CSRF token, the diagram and the session the user returns to are injected into it.
- `test_health_reports_the_version` — health reports the version.
- `test_page_requires_login` — page requires login.
- `test_timeline_shows_own_data_only` — timeline shows own data only.
- `test_timeline_empty_for_user_without_diagram` — timeline empty for user without diagram.
- `test_chat_round_trip` — chat round trip.
- `test_chat_reuses_discussion` — chat reuses discussion.
- `test_chat_rejects_missing_csrf` — chat rejects missing csrf.
- `test_chat_rejects_bad_csrf` — chat rejects bad csrf.
- `test_pwa_files_are_served_from_the_app_root` — The service worker has to answer from /app/ or its scope cannot cover the app.
- `test_a_tap_that_names_no_item_kind_is_refused_in_words` — a tap that names no item kind is refused in words.

## btcopilot/tests/chat/personal/test_chatspeakers.py

- `test_the_coach_is_not_a_person_in_a_new_record` — the coach is not a person in a new record.
- `test_the_id_the_coach_used_to_hold_is_never_handed_to_anyone` — the id the coach used to hold is never handed to anyone.
- `test_a_new_session_points_the_coach_at_no_person` — a new session points the coach at no person.

## btcopilot/tests/chat/personal/test_claude_backend.py

- `test_is_claude_model_positive` — is claude model positive.
- `test_is_claude_model_negative` — is claude model negative.
- `test_prepare_messages_from_turns` — prepare messages from turns.
- `test_prepare_messages_from_prompt` — prepare messages from prompt.
- `test_prepare_messages_prepends_user_if_starts_with_assistant` — prepare messages prepends user if starts with assistant.
- `test_prepare_messages_merges_consecutive_same_role` — prepare messages merges consecutive same role.
- `test_prepare_messages_no_args_raises` — prepare messages no args raises.
- `test_claude_text_with_simple_prompt` — claude text with simple prompt.
- `test_claude_text_sync` — claude text sync.
- `test_response_text_sync_routes_to_claude` — response_text_sync routes to Claude when RESPONSE_MODEL starts with claude-.
- `test_response_text_sync_routes_to_gemini` — response_text_sync routes to Gemini when RESPONSE_MODEL is not Claude.
- `test_chat_flow_mock_still_works` — Existing chat_flow mock works regardless of backend (mocks _generate_response).
- `test_chat_generate_response_uses_response_text_sync` — _generate_response in chat.py uses the unified response_text_sync.
- `test_discussion_update_summary_uses_response_text_sync` — Discussion.update_summary uses the unified response_text_sync.

## btcopilot/tests/chat/personal/test_claude_structured.py

- `test_gemini_structured_dispatches_claude_models` — gemini structured dispatches claude models.
- `test_claude_structured_parses_fenced_json_and_counts_usage` — claude structured parses fenced json and counts usage.
- `test_claude_structured_raises_on_truncation` — claude structured raises on truncation.

## btcopilot/tests/chat/personal/test_clusters.py

- `test_a_shift_gathers_the_moves_around_it` — a shift gathers the moves around it.
- `test_a_move_beyond_the_span_stays_out` — a move beyond the span stays out.
- `test_a_couple_share_a_cluster_through_their_pair_bond` — a couple share a cluster through their pair bond.
- `test_two_shifts_that_reach_the_same_move_are_one_cluster` — two shifts that reach the same move are one cluster.
- `test_two_recorded_years_apart_end_the_cluster` — The two shifts reach the same middle event, so the rules first put all five together; nothing is recorded in the stretch between them, so it breaks at the….
- `test_a_break_can_leave_a_shift_standing_alone` — When the break takes the only companion away, what is left is a shift with no related move, which is a dot and not a cluster.
- `test_a_birth_alone_seeds_nothing` — a birth alone seeds nothing.
- `test_a_relationship_move_seeds_a_cluster` — a relationship move seeds a cluster.
- `test_a_seeding_event_may_not_be_left_out` — a seeding event may not be left out.
- `test_one_event_may_not_sit_in_two_groups` — one event may not sit in two groups.
- `test_a_rejected_grouping_is_asked_for_once_more` — a rejected grouping is asked for once more.
- `test_an_id_the_record_does_not_have_is_rejected` — an id the record does not have is rejected.

## btcopilot/tests/chat/personal/test_clustersync.py

- `test_a_grouping_stuck_under_the_floor_can_still_be_removed` — a grouping stuck under the floor can still be removed.
- `test_a_grouping_of_unknown_provenance_is_left_alone` — A row written before provenance was recorded is treated as the user's: guessing that the model made it would lose a name the user chose.
- `test_the_coach_is_never_told_the_model_made_a_grouping_it_may_not_have` — the coach is never told the model made a grouping it may not have.
- `test_the_same_events_are_not_regrouped_twice` — the same events are not regrouped twice.
- `test_a_grouping_made_by_the_older_rules_is_regrouped` — a grouping made by the older rules is regrouped.

## btcopilot/tests/chat/personal/test_coach_smoke.py

- `test_smoke_opus_returning_user` — smoke opus returning user.
- `test_smoke_gemini_returning_user` — smoke gemini returning user.
- `test_pattern_b_shallow_cycling_opus` — pattern b shallow cycling opus.
- `test_pattern_b_shallow_cycling_gemini` — pattern b shallow cycling gemini.
- `test_pattern_c_long_session_opus` — pattern c long session opus.
- `test_pattern_c_long_session_gemini` — pattern c long session gemini.

## btcopilot/tests/chat/personal/test_intake.py

- `test_no_diagram_all_not_covered_except_presenting_problem` — no diagram all not covered except presenting problem.
- `test_empty_diagram_outstanding_excludes_presenting_problem` — empty diagram outstanding excludes presenting problem.
- `test_full_picture` — full picture.
- `test_partial_grandparents_when_parent_known_but_no_grandparent_bond` — partial grandparents when parent known but no grandparent bond.
- `test_functioning_coverage_thin_when_no_shift_events` — functioning coverage thin when no shift events.
- `test_functioning_coverage_rich_when_sarf_and_timeline_present` — functioning coverage rich when sarf and timeline present.
- `test_format_coverage_renders_known_and_outstanding` — format coverage renders known and outstanding.
- `test_format_coverage_empty_when_only_presenting_problem` — format coverage empty when only presenting problem.
- `test_roster_lists_all_named_people_even_without_speaker_links` — roster lists all named people even without speaker links.
- `test_real_desktop_quirks_dont_crash` — real desktop quirks dont crash.
- `test_committed_scene_format_contract` — Regression: pins the real committed-data contract for the Personal app.

## btcopilot/tests/chat/personal/test_lanes.py

- `test_people_and_bonds_from_structure` — people and bonds from structure.
- `test_certainty_grades_map_to_schema` — certainty grades map to schema.
- `test_structure_events_created` — structure events created.
- `test_same_direction_only_for_unchanged_descriptions` — same direction only for unchanged descriptions.
- `test_relationship_polarity_normalized_per_doc` — relationship polarity normalized per doc.
- `test_strip_prefers_primary_symptom_then_household` — strip prefers primary symptom then household.
- `test_relationship_events_stamp_household_lane` — relationship events stamp household lane.
- `test_aliases_merge_spellings_without_code_changes` — aliases merge spellings without code changes.

## btcopilot/tests/chat/personal/test_migrate_json.py

- `test_converts_once_and_is_idempotent` — converts once and is idempotent.

## btcopilot/tests/chat/personal/test_pairbonds.py

- `test_adding_a_bond_writes_it` — adding a bond writes it.
- `test_a_bond_of_one_person_with_themselves_is_refused` — a bond of one person with themselves is refused.
- `test_ending_a_bond_leaves_its_children_without_parents` — ending a bond leaves its children without parents.

## btcopilot/tests/chat/personal/test_passwordless.py

- `test_coming_back_to_the_site_root_lands_in_the_chat` — coming back to the site root lands in the chat.
- `test_signing_in_stamps_the_session_the_training_app_ages` — signing in stamps the session the training app ages.
- `test_fixture_token_signs_in` — The visual suite mints its links through the fixture installer, so the installer's own token has to open a session, not the sign-in page.
- `test_invite_is_single_use` — invite is single use.
- `test_invite_is_reusable_where_the_sandbox_says_so` — invite is reusable where the sandbox says so.
- `test_expired_code_is_rejected` — expired code is rejected.
- `test_used_code_is_rejected` — used code is rejected.
- `test_unknown_email_gets_no_code` — unknown email gets no code.
- `test_code_requests_are_rate_limited` — code requests are rate limited.
- `test_revoking_the_session_logs_out` — revoking the session logs out.
- `test_registering_a_passkey_stores_it` — registering a passkey stores it.
- `test_revoked_passkey_is_refused` — revoked passkey is refused.

## btcopilot/tests/chat/personal/test_people.py

- `test_changing_someone_keeps_their_id` — changing someone keeps their id.
- `test_a_field_the_record_has_no_room_for_is_refused` — a field the record has no room for is refused.
- `test_removing_someone_takes_them_off_the_record` — removing someone takes them off the record.
- `test_a_record_behind_its_own_counter_never_renames_someone` — a record behind its own counter never renames someone.

## btcopilot/tests/chat/personal/test_preferences.py

- `test_prefs_returns_every_key` — prefs returns every key.
- `test_set_prefs_round_trips` — set prefs round trips.
- `test_set_prefs_rejects_unknown_key` — set prefs rejects unknown key.
- `test_set_prefs_rejects_bad_value` — set prefs rejects bad value.
- `test_speak_must_be_bool` — speak must be bool.

## btcopilot/tests/chat/personal/test_pro.py

- `test_a_chat_session_is_still_the_default` — a chat session is still the default.
- `test_a_recording_cannot_be_started_without_its_transcript` — a recording cannot be started without its transcript.
- `test_the_clinician_becomes_the_coachs_side_of_the_thread` — the clinician becomes the coachs side of the thread.
- `test_a_recording_with_no_clinician_is_refused` — a recording with no clinician is refused.

## btcopilot/tests/chat/personal/test_productevents.py

- `test_events_are_stored_with_user_and_session` — events are stored with user and session.
- `test_an_unknown_screen_or_name_is_refused` — an unknown screen or name is refused.
- `test_web_and_server_name_the_same_screens_and_features` — web and server name the same screens and features.

## btcopilot/tests/chat/personal/test_promptfiles.py

- `test_the_open_source_prompts_say_what_their_constants_said` — the open source prompts say what their constants said.
- `test_the_private_prompts_say_what_their_constants_said` — the private prompts say what their constants said.
- `test_the_app_runs_whole_with_no_private_prompts` — the app runs whole with no private prompts.
- `test_a_prompt_renders_the_fragments_it_includes` — a prompt renders the fragments it includes.
- `test_a_missing_fragment_raises_rather_than_rendering_empty` — a missing fragment raises rather than rendering empty.
- `test_importing_the_app_decrypts_nothing` — A prompt is read when it is called for, never when a module loads, or a test run and the migration chain would need a key before they could start.

## btcopilot/tests/chat/personal/test_prorecord.py

- `test_editing_an_event_by_hand_keeps_the_fields_only_the_desktop_knows` — The chat editor writes the fields it shows; relationshipIntensity and the desktop's drawing fields on the same event are not its to drop.

## btcopilot/tests/chat/personal/test_record.py

- `test_the_write_refuses_a_description_that_names_a_person_the_event_links` — Owner ruling 2026-09-09: the links say who, so the words may not say the same person again.
- `test_the_write_refuses_a_birth_hung_on_the_person_instead_of_the_child` — the write refuses a birth hung on the person instead of the child.
- `test_a_birth_about_the_child_with_words_of_its_own_commits` — a birth about the child with words of its own commits.
- `test_a_grouping_stored_under_the_older_floor_blocks_nothing_else` — A record can hold a grouping made when two events were enough.
- `test_delete_person_cascades_like_the_scene` — delete person cascades like the scene.
- `test_delete_of_a_missing_item_raises` — delete of a missing item raises.
- `test_the_write_refuses_a_shift_that_says_nothing_moved` — the write refuses a shift that says nothing moved.
- `test_the_write_refuses_a_moment_already_in_the_record` — the write refuses a moment already in the record.

## btcopilot/tests/chat/personal/test_ref_index_e2e.py

- `test_the_state_handed_to_the_coach_carries_the_index` — the state handed to the coach carries the index.
- `test_the_instruction_teaches_the_markup_the_parser_reads` — Guards the one thing that silently breaks chips: the instruction and the parser drifting apart on the markup.

## btcopilot/tests/chat/personal/test_refs.py

- `test_a_reply_naming_nothing_has_no_references` — a reply naming nothing has no references.
- `test_unparseable_target_keeps_its_words_and_makes_no_reference` — unparseable target keeps its words and makes no reference.
- `test_backwards_range_is_not_a_reference` — backwards range is not a reference.
- `test_index_names_every_kind_of_id_the_markup_takes` — index names every kind of id the markup takes.
- `test_index_leaves_out_what_the_picture_cannot_aim_at` — index leaves out what the picture cannot aim at.
- `test_index_is_empty_without_a_dated_record` — index is empty without a dated record.
- `test_index_is_capped` — index is capped.
- `test_clusters_are_listed_newest_first` — Ids sort as text, so double digits are where a by-id sort goes wrong.
- `test_a_large_cast_cannot_crowd_out_the_events` — a large cast cannot crowd out the events.

## btcopilot/tests/chat/personal/test_structure.py

- `test_a_bond_of_one_person_with_themselves_is_refused` — a bond of one person with themselves is refused.
- `test_a_bond_with_one_side_is_refused` — a bond with one side is refused.
- `test_nobody_is_born_to_a_bond_they_are_in` — nobody is born to a bond they are in.
- `test_a_bond_between_two_different_people_commits` — a bond between two different people commits.

## btcopilot/tests/chat/personal/test_synthetic.py

- `test_system_prompt_includes_anti_patterns` — system prompt includes anti patterns.
- `test_system_prompt_includes_attachment_narrative` — system prompt includes attachment narrative.
- `test_system_prompt_includes_trait_behaviors` — system prompt includes trait behaviors.
- `test_system_prompt_deduplicates_high_functioning` — system prompt deduplicates high functioning.
- `test_system_prompt_no_old_conditional_sections` — system prompt no old conditional sections.
- `test_detects_therapist_cliches` — detects therapist cliches.
- `test_detects_repetitive_starters` — detects repetitive starters.
- `test_counts_questions` — counts questions.
- `test_words_per_response` — words per response.
- `test_question_only_ratio` — question only ratio.
- `test_response_type_classification` — response type classification.
- `test_detects_echoing` — detects echoing.
- `test_good_conversation_scores_higher` — good conversation scores higher.
- `test_coverage_detects_missing_categories` — coverage detects missing categories.
- `test_coverage_tracks_matched_keywords` — coverage tracks matched keywords.
- `test_coverage_full_persona` — coverage full persona.
- `test_coverage_empty_datapoints` — coverage empty datapoints.
- `test_generate_persona` — generate persona.
- `test_coverage_in_live_conversation` — coverage in live conversation.
- `test_single_persona_conversation` — single persona conversation.
- `test_full_synthetic_suite` — full synthetic suite.
- `test_regression_robotic_patterns` — regression robotic patterns.
- `test_persist_synthetic_conversation` — persist synthetic conversation.
- `test_opus_vs_gemini_baseline` — Run matched conversations with Opus and Gemini, print metrics side by side.
- `test_non_persist_cleans_up` — non persist cleans up.

## btcopilot/tests/chat/personal/test_timeline.py

- `test_per_person_isolation` — One person's line must never be influenced by another's events (the known QML mixed-sum bug).
- `test_lane_picker_data_from_diagram` — lane picker data from diagram.
- `test_seed_fixture_covers_every_move_the_play_by_play_draws` — The play-by-play has one symbol per move kind; the fixture has to walk through all of them or the stepping is never exercised.
- `test_seed_fixture_covers_every_rule` — seed fixture covers every rule.
- `test_the_axis_spans_every_dated_event_not_only_the_lane_marks` — the axis spans every dated event not only the lane marks.
- `test_undated_events_belong_to_no_cluster_but_stay_in_the_list` — undated events belong to no cluster but stay in the list.
- `test_every_event_carries_the_words_the_list_shows` — every event carries the words the list shows.
- `test_an_event_carries_the_fields_whoever_stored_it_left_out` — an event carries the fields whoever stored it left out.
- `test_a_moment_says_who_from_its_links_and_what_without_the_name` — Owner ruling 2026-09-09: who comes from the links, what never repeats a linked person's name.

## btcopilot/tests/chat/personal/test_toolmeanings.py

- `test_every_tool_parameter_has_a_default_meaning` — every tool parameter has a default meaning.

## btcopilot/tests/chat/personal/test_turns.py

- `test_a_second_message_while_the_coach_is_answering_is_refused` — a second message while the coach is answering is refused.
- `test_a_hold_left_by_a_dead_worker_runs_out` — A worker that dies mid-turn says nothing.
- `test_the_stream_numbers_every_event` — the stream numbers every event.
- `test_another_users_turn_is_not_found` — another users turn is not found.
- `test_a_turn_nobody_started_is_not_found` — a turn nobody started is not found.
- `test_the_task_can_be_run_on_its_own` — The worker calls the task with ids, and what it returns is the reply the page would have been handed before.

## btcopilot/tests/chat/review/test_api.py

- `test_coding_reuses_the_coders_record_from_the_last_cut` — coding reuses the coders record from the last cut.
- `test_done_freezes_the_coders_record` — done freezes the coders record.
- `test_a_coder_sees_no_one_elses_coding_until_their_own_is_done` — a coder sees no one elses coding until their own is done.
- `test_names_are_hidden_on_codings_until_ratification` — names are hidden on codings until ratification.
- `test_snapshot_marks_the_shared_event_agreed_and_the_lone_one_disputed` — snapshot marks the shared event agreed and the lone one disputed.
- `test_agreement_lands_on_the_cut` — agreement lands on the cut.
- `test_one_vote_per_coder_per_item` — one vote per coder per item.
- `test_a_coder_reads_only_their_own_votes` — a coder reads only their own votes.
- `test_ratifying_writes_the_ground_truth_export` — ratifying writes the ground truth export.
- `test_the_coachs_draft_lands_as_ai_rules` — the coachs draft lands as ai rules.
- `test_a_post_without_a_csrf_token_is_refused` — a post without a csrf token is refused.
- `test_the_agenda_gathers_what_the_meeting_must_take_up` — the agenda gathers what the meeting must take up.
- `test_the_coachs_replay_is_a_coding_with_its_model` — the coachs replay is a coding with its model.
- `test_the_agenda_says_what_each_coder_is_doing` — Patrick has not started; the other coder has a coding under way.
- `test_a_coder_who_pressed_done_reads_as_done` — a coder who pressed done reads as done.
- `test_the_coach_is_not_one_of_the_coders_the_agenda_waits_on` — the coach is not one of the coders the agenda waits on.
- `test_taking_a_conversation_off_the_agenda` — taking a conversation off the agenda.
- `test_a_cut_someone_started_cannot_be_taken_off_the_agenda` — a cut someone started cannot be taken off the agenda.
- `test_a_nudge_reaches_everyone_not_done` — a nudge reaches everyone not done.
- `test_a_coder_cannot_nudge` — a coder cannot nudge.
- `test_a_coder_cannot_read_a_session_whole` — a coder cannot read a session whole.
- `test_the_ballot_carries_the_turn_and_the_person_of_each_opinion` — the ballot carries the turn and the person of each opinion.
- `test_each_version_of_a_person_carries_the_line_its_coder_wrote_it_from` — each version of a person carries the line its coder wrote it from.
- `test_a_person_nobody_wrote_from_a_turn_carries_no_line` — a person nobody wrote from a turn carries no line.
- `test_no_name_reaches_the_ballot` — no name reaches the ballot.
- `test_the_coachs_own_reading_is_not_on_the_ballot` — the coachs own reading is not on the ballot.
- `test_the_vote_task_goes_when_every_disputed_event_has_a_vote` — the vote task goes when every disputed event has a vote.
- `test_nudges_switched_off_are_refused` — nudges switched off are refused.

## btcopilot/tests/chat/review/test_isolation.py

- `test_only_the_adapter_reaches_the_app` — only the adapter reaches the app.
- `test_the_adapter_is_where_it_is_reached` — the adapter is where it is reached.

## btcopilot/tests/chat/review/test_matching.py

- `test_the_same_man_named_three_ways_is_one_person` — One coder wrote "father", another "Corinne's father", a third his name.
- `test_two_people_with_the_same_first_name_are_not_matched` — Two men called Marcus standing in different places in the family: one is the father, one is a son-in-law, and they are not the same man.
- `test_a_person_who_could_be_two_is_handed_to_the_room` — Two sisters both called Lee, with nothing in the family to tell them apart: the item carries both versions and the room decides who is who.
- `test_an_ambiguous_person_is_never_agreed` — The row the snapshot writes for it is disputed and says it is unsure.

## btcopilot/tests/chat/review/test_meeting.py

- `test_the_coach_is_not_counted_as_a_coder` — the coach is not counted as a coder.
- `test_what_only_the_coach_read_differently_is_not_disputed` — The two people wrote the second moment the same way; only the coach dated it otherwise, and that does not put it in front of the room.
- `test_the_kept_version_is_not_on_the_blind_reading` — the kept version is not on the blind reading.
- `test_a_coder_cannot_ask_for_the_names` — a coder cannot ask for the names.
- `test_the_tally_names_who_voted_which_way` — the tally names who voted which way.
- `test_both_agreement_figures_are_kept` — both agreement figures are kept.
- `test_what_every_coder_read_the_same_way_is_ratified_too` — An agreed item is never argued over, so ratifying is what confirms it onto the record.
- `test_a_cut_the_coach_never_coded_says_so_rather_than_scoring_it` — No score and no differences, so the screen can say the coach did not code this conversation instead of showing an empty space.
- `test_where_the_coach_differed_is_written_once_at_ratification` — where the coach differed is written once at ratification.
- `test_the_result_says_what_each_coder_tends_to_do` — the result says what each coder tends to do.
- `test_changing_an_opinion_rewords_the_same_moment` — A change is a rewording, not a second event beside the first: it lands on the moment the opinions already name.
- `test_a_person_can_be_decided_before_what_they_stand_on_is_ratified` — Keeping a person born to a bond the coders all read the same way puts that bond on the case first, so the record has what the person needs and the room is….
- `test_a_decision_the_record_refuses_is_the_rooms_fault` — A shift with no variable is refused in the record's own words, not as a server error.
- `test_a_cut_that_is_not_ratified_has_no_result` — a cut that is not ratified has no result.
- `test_a_ratified_cut_cannot_be_decided_again` — a ratified cut cannot be decided again.

## btcopilot/tests/chat/review/test_migration.py

- `test_author_enum_takes_review` — author enum takes review.
- `test_discussion_kind_defaults_to_chat` — discussion kind defaults to chat.

## btcopilot/tests/chat/review/test_scribe.py

- `test_adds_the_person_the_coder_names` — adds the person the coder names.
- `test_asks_when_the_coder_points_without_naming` — A bare pronoun with more than one person in the record is asked about before any model call, so nothing can be written (R-0270).
- `test_asks_when_one_name_could_be_two_people` — asks when one name could be two people.
- `test_a_whole_name_settles_shared_words` — "Marcus's father" against "Marcus's grandmother" is not ambiguity.
- `test_a_relation_word_names_a_person` — "grandmother stopped speaking to him" names one person and, by gender, points at the other: no question.
- `test_a_gendered_pronoun_with_one_candidate_is_not_asked` — a gendered pronoun with one candidate is not asked.
- `test_a_turn_that_names_nobody_still_reaches_the_model` — No name and no pronoun is not ambiguity: the model reads the turn.
- `test_writes_the_event_after_a_wasted_guess` — On an empty record the cheap model guesses an id, is refused, then adds two people before the event.
- `test_says_so_when_it_runs_out_of_steps` — What was written stays, and the coder is told, never shown it as done.
- `test_a_bond_with_no_event_says_it_has_no_date_yet` — a bond with no event says it has no date yet.
- `test_a_year_the_coder_only_said_as_a_year_reads_as_the_year` — A year alone is stored as the first of January, approximate; the month was never said, so it is not read back (R-0326).
- `test_a_january_date_the_coder_stated_keeps_its_month` — a january date the coder stated keeps its month.

## btcopilot/tests/chat/test_admin.py

- `test_users_list_and_show` — users list and show.
- `test_users_roles_set_then_read` — users roles set then read.
- `test_unknown_user_is_named` — unknown user is named.
- `test_licence_granted_then_revoked` — licence granted then revoked.
- `test_diagram_counts_and_export` — diagram counts and export.
- `test_import_dry_run_counts_and_writes_nothing` — import dry run counts and writes nothing.
- `test_token_cap_default_and_one_person` — token cap default and one person.
- `test_token_cap_refuses_a_negative` — token cap refuses a negative.
- `test_nudge_switch` — nudge switch.
- `test_agenda_is_empty_before_any_cut` — agenda is empty before any cut.
- `test_table_output_has_a_header` — table output has a header.
- `test_skill_file_is_the_same_bytes_twice` — skill file is the same bytes twice.
- `test_run_rejects_an_unknown_command` — run rejects an unknown command.

## btcopilot/tests/chat/test_boxsecrets.py

- `test_every_setting_the_app_requires_has_a_home_on_the_box` — every setting the app requires has a home on the box.

## btcopilot/tests/schema/test_apply_local_changes.py

- `test_clean_item_takes_server_state` — User didn't touch the item → server's concurrent edit survives.
- `test_dirty_item_takes_local_state` — User edited the item → local wins (item-level last-write-wins).
- `test_same_item_both_sides_edited_local_wins` — Both sides edited the same item different fields → local item wins whole.
- `test_local_deletion_survives_server_unchanged` — User deleted the item locally → it stays deleted, even if server still has it.
- `test_local_addition_preserved` — User added a new item → it appears in result.
- `test_server_addition_preserved` — Other client added an item → it appears in result alongside local additions.
- `test_simultaneous_delete_both_sides` — Both sides deleted the same item → it stays deleted (idempotent).
- `test_empty_snapshot_treats_all_as_added` — empty snapshot treats all as added.
- `test_qpointf_field_unchanged_not_marked_dirty` — QtCore types in dicts compare correctly via pickle bytes (regression guard).
- `test_qdatetime_field_unchanged_not_marked_dirty` — qdatetime field unchanged not marked dirty.
- `test_id_collision_between_local_add_and_server_add_local_wins` — If both sides somehow allocated the same id (shouldn't happen with block allocation, but verify behavior is item-level LWW = local wins).
- `test_items_without_ids_skipped` — Items missing an id are silently skipped (defensive).
- `test_local_edit_beats_server_delete` — Item-level last-write-wins: if user edited an item locally and another client deleted it server-side, the user's edit wins (item resurrects with the user's….
- `test_local_add_with_server_unchanged_no_other_items` — Edge case: local has new id, server is empty (or has unrelated items).
- `test_regression_snapshot_must_reflect_local_view_not_canonical` — Regression for the bug discovered by e2e harness 2026-05-02: Prior bug: client's snapshot was set from `_diagram.data` (canonical), which after a merge….
- `test_regression_subsequent_save_preserves_other_client_items_after_delete` — Regression for the bug's second-half scenario: After Pro's first save brought Person 99 into the merged result, the next save's snapshot must NOT include 99….

## btcopilot/tests/schema/test_commit.py

- `test_commit_single_person` — commit single person.
- `test_commit_single_event` — commit single event.
- `test_commit_event_with_pdp_person_reference` — commit event with pdp person reference.
- `test_commit_person_with_pdp_parent_references` — commit person with pdp parent references.
- `test_commit_event_with_pdp_relationship_targets` — commit event with pdp relationship targets.
- `test_commit_event_with_pdp_triangles` — commit event with pdp triangles.
- `test_commit_preserves_committed_references` — commit preserves committed references.
- `test_commit_multiple_items_at_once` — commit multiple items at once.
- `test_commit_partial_pdp` — commit partial pdp.
- `test_commit_rejects_positive_id` — commit rejects positive id.
- `test_commit_rejects_nonexistent_pdp_id` — commit rejects nonexistent pdp id.
- `test_commit_complex_transitive_closure` — commit complex transitive closure.
- `test_commit_birth_event_creates_inferred_child` — commit birth event creates inferred child.
- `test_commit_married_event_creates_inferred_pair_bond` — When committing a Married event with person/spouse but no PairBond, create one.
- `test_commit_bonded_event_creates_inferred_pair_bond` — When committing a Bonded event with person/spouse but no PairBond, create one.
- `test_commit_married_event_uses_existing_pair_bond` — When committing a Married event with existing PairBond, don't create duplicate.
- `test_commit_separated_event_creates_inferred_pair_bond` — commit separated event creates inferred pair bond.
- `test_commit_divorced_event_creates_inferred_pair_bond` — commit divorced event creates inferred pair bond.
- `test_commit_birth_case3_creates_pair_bond` — Birth with person+spouse but no child creates pair bond and inferred child.
- `test_commit_birth_existing_pair_bond_sets_child_parents` — Birth Case 2 with existing pair bond should still set child.parents.
- `test_commit_dedup_pair_bond_against_committed` — Committing a PDP pair bond whose dyad already exists in committed should reuse the committed one.
- `test_commit_dedup_pair_bond_child_parents_remapped` — When a PDP pair bond is deduped, Person.parents should remap to the existing committed PB.
- `test_commit_birth_case2_finds_committed_pair_bond` — Birth Case 2 with committed person should find committed pair bond and spouse.
- `test_reject_transitive_cascade` — Rejecting a person should transitively cascade through pair bonds to children.
- `test_commit_backfills_committed_child_parents` — commit backfills committed child parents.
- `test_commit_backfill_does_not_overwrite_existing_parents` — commit backfill does not overwrite existing parents.
- `test_commit_pair_bond_married_none_defaults_true` — commit pair bond married none defaults true.
- `test_commit_pair_bond_married_false_preserved` — commit pair bond married false preserved.
- `test_apply_parent_edits_leaves_non_parents_update_rows_staged` — apply parent edits leaves non parents update rows staged.

## btcopilot/tests/schema/test_date_utils.py

- `test_validatedDateTimeText_empty` — validatedDateTimeText empty.
- `test_validatedDateTimeText_blank` — validatedDateTimeText blank.
- `test_validatedDateTimeText_standard_format` — validatedDateTimeText standard format.
- `test_validatedDateTimeText_with_time` — validatedDateTimeText with time.
- `test_validatedDateTimeText_blank_time` — validatedDateTimeText blank time.
- `test_validatedDateTimeText_8digit_format` — validatedDateTimeText 8digit format.
- `test_pyDateTimeString_datetime` — pyDateTimeString datetime.
- `test_pyDateTimeString_from_string` — pyDateTimeString from string.

## btcopilot/tests/schema/test_diagram_model.py

- `test_update_with_version_check_atomicity` — Test that update_with_version_check atomically updates both data and version.
- `test_update_with_version_check_conflict` — Test that update_with_version_check rejects when version mismatches.
- `test_update_with_version_check_using_diagram_data` — Test that update_with_version_check works with DiagramData objects.
- `test_model_imports_without_the_qt_gui_module` — The server must start where PyQt5.QtGui's system libraries are absent.

## btcopilot/tests/schema/test_inferred_idempotent.py

- `test_commit_then_replay_on_fresh_pdp_no_duplicates` — Simulate the 409-retry semantic: each attempt runs commit_pdp_items on a fresh DiagramData (because server rejects and returns its untouched state).
- `test_double_commit_on_same_diagramData_fails_fast` — If commit_pdp_items is called twice on the SAME DiagramData with the same item_ids, the second call raises ValueError because the item is no longer in pdp.

## btcopilot/tests/schema/test_isolation.py

- `test_schema_import_isolation` — schema import isolation.
- `test_commit_pdp_items_no_private_imports` — commit_pdp_items must not import private btcopilot modules at call time.

## btcopilot/tests/schema/test_validation.py

- `test_get_all_pdp_item_ids` — get all pdp item ids.
- `test_dataclass_to_json_schema_force_required` — Verify force_required adds fields to required list even if they have defaults.
- `test_pdp_deltas_schema_has_event_required_fields` — Verify PDPDeltas schema marks Event required fields via PDP_FORCE_REQUIRED.
- `test_pdp_deltas_schema_has_pair_bond_required_fields` — pdp deltas schema has pair bond required fields.
- `test_commit_repairs_dangling_parents` — commit repairs dangling parents.
- `test_commit_with_positive_id_people_in_pdp` — Positive-ID people in PDP (committed item updates) should not be committed.

## btcopilot/tests/test_db.py

- `test_every_chat_model_is_in_the_chain` — A model in a chat-app package whose table the chain does not build is a table that exists on the sandbox by hand and on a fresh server not at all, which is….
- `test_chain_matches_what_the_models_declare` — chain matches what the models declare.

## btcopilot/tests/test_diagramjson.py

- `test_encode_rejects_unknown_type` — encode rejects unknown type.

## btcopilot/tests/test_proimport.py

- `test_dry_run_counts_and_writes_nothing` — dry run counts and writes nothing.
- `test_every_failure_is_named_with_its_reason` — every failure is named with its reason.

## web/test/ballot.test.ts

- `reads a year on its own as the year` — reads a year on its own as the year.
- `reads in the order they happened` — reads in the order they happened.

## web/test/board.test.ts

- `keeps every moment, not only the ones with a mark to draw` — keeps every moment, not only the ones with a mark to draw.
- `puts the people a bond ties on stage with the one who shifted` — puts the people a bond ties on stage with the one who shifted.
- `keeps a moment that names nobody, so the walk still steps past it` — keeps a moment that names nobody, so the walk still steps past it.

## web/test/caption.test.ts

- `a tap that lands on no moment lets go of the one that was picked` — a tap that lands on no moment lets go of the one that was picked.
- `the undated shelf is recorded against the diagram itself` — the undated shelf is recorded against the diagram itself.
- `only a stretch can be played, and a moment plays the stretch it is in` — only a stretch can be played, and a moment plays the stretch it is in.
- `a chip tap with nothing picked does nothing at all` — a chip tap with nothing picked does nothing at all.
- `dismiss returns to rest` — dismiss returns to rest.

## web/test/chips.test.ts

- `tones every chip in an offered message amber` — tones every chip in an offered message amber.
- `leaves text with no markup alone` — leaves text with no markup alone.
- `does not treat an unknown kind as a chip` — does not treat an unknown kind as a chip.
- `keeps a span of time as plain words, not a chip that goes nowhere` — keeps a span of time as plain words, not a chip that goes nowhere.
- `finds every chip in a play-by-play` — finds every chip in a play-by-play.
- `aims nothing when the chip names something the picture has not got` — aims nothing when the chip names something the picture has not got.

## web/test/editor.test.ts

- `takes the text's own height until ten lines, then stays` — takes the text's own height until ten lines, then stays.

## web/test/meeting.test.ts

- `seats what the list has newly gained at the end and drops what it lost` — seats what the list has newly gained at the end and drops what it lost.

## web/test/parents.test.ts

- `takes the couple those two already are, named either way round` — takes the couple those two already are, named either way round.
- `finds none for two people who are not a couple` — finds none for two people who are not a couple.

## web/test/picture.test.ts

- `fills the screen and no more when one cluster is all there is` — fills the screen and no more when one cluster is all there is.
- `is the screen for a record with nothing to separate` — is the screen for a record with nothing to separate.
- `pulls two clusters apart until their boxes clear each other` — pulls two clusters apart until their boxes clear each other.
- `keeps a box wide enough for the two years written in it` — keeps a box wide enough for the two years written in it.
- `never reaches past two screens, however crowded the record` — never reaches past two screens, however crowded the record.
- `parks the present at the right edge, one screen of line behind it` — parks the present at the right edge, one screen of line behind it.
- `stay where they fall when they already read apart` — stay where they fall when they already read apart.
- `spreads seven moments held inside a few weeks across the box` — spreads seven moments held inside a few weeks across the box.
- `lets a tap on either of two dots 6px apart pick that dot` — lets a tap on either of two dots 6px apart pick that dot.
- `draws both labels and the seam with real numbers` — draws both labels and the seam with real numbers.
- `is the calendar year, not the count since 1970` — is the calendar year, not the count since 1970.

## web/test/rows.test.ts

- `is the name alone, with no second line under it` — is the name alone, with no second line under it.
- `says nothing about a birth the record does hold` — says nothing about a birth the record does hold.

## web/test/search.test.ts

- `keeps a family whose own name matches, even with no sessions on it` — keeps a family whose own name matches, even with no sessions on it.
- `keeps every session of a family whose name matches` — keeps every session of a family whose name matches.
- `names an untitled session by the first words said in it` — names an untitled session by the first words said in it.

## web/test/spotlight.test.ts

- `a date the record is sure of says its month` — a date the record is sure of says its month.
- `a date it only guessed says its year and nothing more` — a date it only guessed says its year and nothing more.
- `the person is named only when the record is not about them` — the person is named only when the record is not about them.
- `a pair keeps the other person and leaves out the one reading` — a pair keeps the other person and leaves out the one reading.
- `a long line wraps onto a second row at a space` — a long line wraps onto a second row at a space.
- `a word too long to break is cut rather than left hanging` — a word too long to break is cut rather than left hanging.
- `clip leaves short text alone and marks what it cuts` — clip leaves short text alone and marks what it cuts.
- `dots shrink as the record gets busier` — dots shrink as the record gets busier.
- `what the coach did not name recedes only when it named something` — what the coach did not name recedes only when it named something.
- `with more named moments than rows, the first and last take one row each` — with more named moments than rows, the first and last take one row each.
- `a moment near the right edge writes its words to the left instead` — a moment near the right edge writes its words to the left instead.
- `a moment with no room for words keeps its row so its leader is drawn` — a moment with no room for words keeps its row so its leader is drawn.
- `more named moments than rows keeps the first and last` — more named moments than rows keeps the first and last.
- `a single moment still gets a zone` — a single moment still gets a zone.
- `a tap steps through the moments under it, then comes back to the first` — a tap steps through the moments under it, then comes back to the first.

## web/test/stream.test.ts

- `re-reads the record once for a run of edits, not once each` — re-reads the record once for a run of edits, not once each.
- `drops words the coach said again` — drops words the coach said again.

## web/test/structure.test.ts

- `reads the people and the bonds before the events` — reads the people and the bonds before the events.
- `is named by both people` — is named by both people.
- `says whether they married rather than showing a true or a false` — says whether they married rather than showing a true or a false.

## web/test/task.test.ts

- `leaves a row the room has not ratified as a faint record` — leaves a row the room has not ratified as a faint record.

## web/test/turn.test.ts

- `says nothing for reads and for showing the picture` — says nothing for reads and for showing the picture.
- `says nothing for a tool it does not know` — says nothing for a tool it does not know.

## web/test/when.test.ts

- `names the day, and the year only when it is another year` — names the day, and the year only when it is another year.
- `reads twelve-hour with midnight and noon as 12` — reads twelve-hour with midnight and noon as 12.
- `drops the clock` — drops the clock.

## web/tests/visual/board.spec.ts

- `earlier moves stay behind the one being drawn` — earlier moves stay behind the one being drawn.
- `the last move has nowhere further to go` — the last move has nowhere further to go.

## web/tests/visual/chat.spec.ts

- `a coach bubble says who is speaking` — a coach bubble says who is speaking.
- `it stands apart in amber` — it stands apart in amber.

## web/tests/visual/crosslinks.spec.ts

- `a person not yet chosen is still chosen by tapping` — a person not yet chosen is still chosen by tapping.
- `the words of the moment picked open its editor` — the words of the moment picked open its editor.

## web/tests/visual/failure.spec.ts

- `warns under the board and leaves the board up` — warns under the board and leaves the board up.

## web/tests/visual/frame.spec.ts

- `holds what it draws, at rest and with a cluster open` — holds what it draws, at rest and with a cluster open.

## web/tests/visual/gestures.spec.ts

- `Delete removes the session and the record survives it` — Delete removes the session and the record survives it.
- `never writes more than three rows of words` — never writes more than three rows of words.

## web/tests/visual/layout.spec.ts

- `picking a moment moves nothing sideways` — picking a moment moves nothing sideways.
- `is cut with an ellipsis rather than spilling over the picture` — is cut with an ellipsis rather than spilling over the picture.

## web/tests/visual/moves.spec.ts

- `the ${spec.name} drawing` — the ${spec.name} drawing.

## web/tests/visual/people.spec.ts

- `the people list orders by birth until the reader asks for names` — the people list orders by birth until the reader asks for names.

## web/tests/visual/picture.spec.ts

- `at rest: ${what}` — at rest: ${what}.
- `opens it, and the wire underneath is tappable` — opens it, and the wire underneath is tappable.
- `settles where a cluster is not cut in half` — settles where a cluster is not cut in half.
- `a tap still picks the cluster under the thumb` — a tap still picks the cluster under the thumb.

## web/tests/visual/reset.spec.ts

- `a tap on empty wire shows the whole line again` — a tap on empty wire shows the whole line again.
- `opens its editor` — opens its editor.
- `a dot picks its moment and never travels` — a dot picks its moment and never travels.

## web/tests/visual/sandboxapp.spec.ts

- `the chat app: the picture, the lists, the sessions sheet and the account` — the chat app: the picture, the lists, the sessions sheet and the account.

## web/tests/visual/sandboxtap.spec.ts

- `a tap on the thread keeps its place` — a tap on the thread keeps its place.

## web/tests/visual/select.spec.ts

- `answers on both of its lines, not just the first` — answers on both of its lines, not just the first.

## web/tests/visual/sessions.spec.ts

- `tapping the scrim closes it` — tapping the scrim closes it.

## web/tests/visual/settings.spec.ts

- `the back chevron on the root page closes the stack` — the back chevron on the root page closes the stack.

## For Patrick to rule

1. **A birth opens a chapter.** R-0375 says a birth, marriage, divorce or death opens a chapter of the story. `test_clusters.py::test_a_birth_alone_seeds_nothing` proves a birth alone starts no cluster, and passes only because two events can never be a cluster (R-0215).
2. **Import once, or no import.** `test_proimport.py`'s apply and second-run tests cite R-0327, "old Pro users are imported once". R-0355 says there is no import at the switch-over. Which stands decides whether those tests keep their id or are deleted.
3. **Where the private prompts live.** `test_scribe.py::test_a_private_file_replaces_the_scribe_prompt` cites R-0314, which says the prompt lives in fdserver. It now lives in btcopilot, so the ruling's wording is stale.
4. **Review rulings tagged process.** R-0242 (blind until Done), R-0250 (three stages to ground truth), R-0252 and R-0272 (names hidden during the vote), R-0254 (no AI on the ballot), R-0267 (the record reused across cuts) and R-0312 (unresolved never re-raised) carry the process tag, so about twelve review tests that prove them exactly say `no ruling`. Other suites cited mixed-tag rulings (R-0078, R-0087, R-0305, R-0322, R-0337) for their product clause. One rule for mixed tags settles both.
5. **Converting old diagrams.** `test_migrate_json.py::test_converts_once_and_is_idempotent` converts every pickled diagram to JSON. R-0241 says old diagrams stay pickle and converting one is its owner's later choice.
6. **Other tests that contradict a live ruling.** `web/test/chips.test.ts` tones chips in an offered message (dropped by R-0361). `web/test/picture.test.ts` draws two moments face to face (dropped by R-0286). Two tests in `web/test/search.test.ts` and one in `web/tests/visual/sessions.spec.ts` list families in the sessions sheet (against R-0347). `test_timeline.py::test_events_no_cluster_claims_stay_off_every_cluster` draws a two-event cluster (against R-0215). Three tests cite R-0008 for trend-line logic that R-0284 deferred.
7. **A ruling the tests name that the store lacks.** Two docstrings cite an owner ruling of 2026-09-09 that an event's words never repeat a linked person's name; it is not in the store, so those tests say `no ruling`.
