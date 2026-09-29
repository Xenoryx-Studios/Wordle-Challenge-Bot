# Wordle Challenge

A Discord bot that gives a server a shared Starter Word each day, so every member opens their Wordle game with the same guess and compares how they get from there to the answer.

## Language

**Challenge**:
One day's Wordle played by a server's members, all opening with the same Starter Word. The day follows the server's timezone, which a Server Admin chooses, and each day's Challenge posts at 00:00 in that timezone, when the new Wordle puzzle unlocks, or as soon as the bot is back online if it missed 00:00. A server never gets more than one Challenge per day. Each Challenge has exactly one thread, where members post their Results.

**Starter Word**:
The word every member of a server uses as their first guess in a Challenge. It must be a guess accepted by the NYT Wordle.
_Avoid_: Wordle word, today's word, daily word

**Replacement**:
Swapping a Challenge's Starter Word for a new one because the original was unplayable (rejected by the NYT Wordle, offensive, or too obscure). The Challenge stays the same; only its Starter Word changes.
_Avoid_: skip, reroll, extra round

**Result**:
A member's Wordle share (the "Wordle 1,234 4/6" squares) posted in a Challenge's thread. Posting a Result is how a member completes a Challenge; shares posted anywhere else do not count.
_Avoid_: score, share, submission

**Reminder**:
A single ping, sent at the server's Reminder Time, to every opted-in member who has not yet posted a Result for the day's Challenge. Members opt in once per server and stay opted in until they opt out.
_Avoid_: nudge, notification

**Reminder Time**:
Three hours before the end of the Challenge's day (21:00 in the server's timezone). If the Challenge has not posted by then, there is no Reminder that day.

**Stopped**:
A server whose Challenges have been turned off by a Server Admin. A Stopped server gets no Challenges and no Reminders, but keeps its Used Words and members' Reminder opt-ins.
_Avoid_: paused, disabled

**Used Words**:
The Starter Words a server has already been given from a Theme, kept so they are not repeated. Each Theme has its own Used Words, and a reset clears only the current Theme's.
_Avoid_: word history, used-words history

**Theme**:
A named set of Starter Words with its own presentation (for example Christmas or Halloween), chosen for a server by a Server Admin. A server stays on its chosen Theme until a Server Admin changes it, and a change applies from the next Challenge.

**Server Admin**:
A server member allowed to configure the bot for that server.
_Avoid_: admin, moderator, manager
