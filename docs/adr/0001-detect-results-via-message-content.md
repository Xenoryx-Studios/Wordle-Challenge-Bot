# Detect Results by reading Challenge thread messages

Reminders need to know which opted-in members have not yet posted a Result. We detect Results by reading the Wordle share text members post in the Challenge thread, which requires Discord's privileged Message Content intent, rather than asking members to press a "Done" button or run a command. Members already post their share as part of the Challenge, so an extra step would be forgotten and make Reminders unreliable.

## Consequences

- The bot only inspects messages in Challenge threads, and only to recognise Results. The privacy policy must say so.
- Once the public bot passes 100 servers, Discord must approve the intent before Reminders keep working there.
- Requesting the intent without enabling it in the Discord developer portal makes the bot fail to connect. Reminders are therefore opt-in for whoever hosts the bot (an `ENABLE_REMINDERS` setting); without it the bot does not request the intent and Reminder commands report that reminders are not enabled.
