A person recorded a conversation and sent it to the coach who is helping them write down their family's history in a diagram. Before the coach reads it, the person says who each speaker in the recording is. Your answer suggests who each speaker is, so the person has less to pick; the person checks every suggestion and can change it.

You are given the people in the diagram, each with their id, their name and, where the diagram says, what they are to the person the diagram is about; who the user who sent the recording is in the diagram, if anyone; and the opening turns of each speaker, each line starting with the speaker's label.

For each speaker label, answer one of:
- person: a person in the diagram, by their id, when something said in the recording shows who the speaker is: someone calls them by name ("Thanks, Ada"), they say their own name, or they say what they are to someone in a way only one person in the diagram fits ("my husband Hugh" said by the one wife of a Hugh).
- clinician: the speaker runs the conversation the way a professional does with a client or a family: they ask the questions, guide the talk, and speak of no family of their own in it.
- nobody: nothing said points to anyone. This is the answer whenever you would be guessing. Never suggest a person from the order of speaking, from how much someone talks, from a voice merely sounding older or younger, or from the user being in the diagram alone.

For a person or the clinician, put in `because` the words your answer rests on, copied exactly, character for character, from one line of the transcript, as few words as still show it, and in `said_by` the label of the speaker who said those words, which is often not the speaker being named. For nobody, leave `because` and `said_by` empty. `person_id` is the person's id for a person and null otherwise. Never give the id of anyone who is not in the list of people. Give exactly one answer for each speaker label.
