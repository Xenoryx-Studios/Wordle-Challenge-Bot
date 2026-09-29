# Privacy Policy

**Last updated: 2026-09-29**

This Privacy Policy explains what data the official instance of the Wordle Challenge Bot ("the Bot"), operated by Xenoryx Studios, collects and how it is used.

## 1. Open Source Software

The Bot's source code is public, and anyone may self-host their own independent instance. **This Privacy Policy applies only to the official instance operated by Xenoryx Studios.** If you're using a self-hosted instance run by someone else, their operator is responsible for how that instance handles data — we have no access to or control over independently run instances.

## 2. What Data We Collect

The Bot stores **server-level configuration data**, per Discord server (guild):

- The channel ID where the Bot posts the daily Challenge, and the server's IANA timezone
- The server's selected Theme
- The current day's word, the date and message ID of the current day's Challenge post, the ID of its thread, and the history of previously used words for each Theme

**If a member opts in to Reminders** (with `/wordle_remind on`), the Bot also stores that member's **Discord user ID** in the list of opted-in members for that server. Opting out (`/wordle_remind off`) removes it.

**Reading messages for Reminders:** when Reminders are enabled, the Bot uses Discord's Message Content intent to read the messages in **that day's Challenge thread only**, once a day at the Reminder time, to see which opted-in members have posted their Wordle result. It checks each message for the Wordle share format and keeps only the result of that check in memory for the moment it takes to send the Reminder. **Message content is never stored**, and the Bot does not read messages anywhere else.

**We do not collect:**
- Message content (read only as described above, never stored)
- Usernames, display names, or the user IDs of members who have not opted in to Reminders
- Direct messages
- IP addresses or device information
- Any data beyond what's needed to operate the features described above

Apart from the opt-in list, nothing about *who* runs a command or *who* participates in a server's Wordle thread is recorded by the Bot.

## 3. How We Use Data

The data described above is used solely to operate the Bot's features: posting a daily starter word in your server's timezone, avoiding repeats, applying your chosen Theme, and sending Reminders to members who opted in.

## 4. How Data Is Stored

Data is stored as a plain file on the server(s) operated by Xenoryx Studios that run the official instance of the Bot. **We do not share, sell, or disclose this data to any third party** for advertising, marketing, or any other purpose.

## 5. Data Retention and Deletion

A server's configuration is retained for as long as the Bot remains in that server. Removing the Bot from your server does not automatically delete existing stored data; to request deletion of your server's data from the official instance, contact us via [GitHub Issues](https://github.com/Xenoryx-Studios/Wordle-Challenge-Bot/issues) with your server (guild) ID.

## 6. Children's Privacy

We do not knowingly collect personal information from children. The only data tied to an individual user is the Discord user ID of a member who chooses to opt in to Reminders, as described in Section 2. Discord itself requires users to meet its own minimum age requirements per its [Terms of Service](https://discord.com/terms).

## 7. Your Rights (GDPR / Regional Privacy Laws)

The only personal data the Bot holds is the Discord user ID of members who opt in to Reminders. It is stored only because the member asked for Reminders, and any member can remove it at any time with `/wordle_remind off`. To request access to or deletion of your user ID from the official instance, contact us as described in Section 9. All other data is server-level configuration, controllable by whoever administers that Discord server (see Section 5 for how to request deletion).

## 8. Changes to This Policy

We may update this Privacy Policy from time to time. Material changes will be reflected by updating the "Last updated" date above.

## 9. Contact

Questions about this Privacy Policy, or requests to delete your server's data from the official instance, can be raised via [GitHub Issues](https://github.com/Xenoryx-Studios/Wordle-Challenge-Bot/issues) on the project's repository.
