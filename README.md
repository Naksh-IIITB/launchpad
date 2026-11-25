# LAUNCHPAD

A local internship application tracker and interview workspace.

- Track applications in table, Kanban, and date agenda views
- Compare CVs against explicit required skills
- Record timed practice and review application analytics

## Run locally

Install Python 3.11+ and clone or download this repository. For Git imports, install Git.
Ollama is optional for the offline workflows. For AI, start Ollama with local models such as
Qwen3 4B and Nomic Embed Text.

    sh install.sh
    sh run.sh

Open http://127.0.0.1:8503. Ctrl+C stops the server.
Run \`python3 test_workflows.py\` for the workflow test.

## Scope

Optional macOS notifications cover upcoming deadlines and follow-ups. Gmail setup requires your own Google Desktop OAuth client and read-only consent. Review each proposed stage or date change.
The semantic search reranks up to 120 keyword-ranked candidates. AI output can be incomplete
and should be checked against the displayed evidence.

## Local data

Data is stored in \`data/\` (or \`APP_DATA_DIR\` if set). Stop the app before backing it up:

    python3 backup.py backup /absolute/path/to/new-backup
    python3 backup.py restore /absolute/path/to/existing-backup

Restore requires the data directory to be absent. To uninstall, stop the app, back up data you
want to keep, and remove the project folder. The public landing page contains project information.

## Optional Gmail and macOS reminders

In Google Cloud, enable the Gmail API, configure the OAuth consent screen, and create a
Desktop app OAuth client. If the app is in testing, add your Gmail account as a test user.
Keep the downloaded JSON outside the repository. Start the app from the same Terminal after
setting LAUNCHPAD_GOOGLE_CLIENT to the absolute path of that JSON file. Use the Gmail tab to
connect and review suggested changes. The app requests read-only access, keeps tokens in
the local data directory with restricted file access, and never sends mail.

Preview reminders with the first command. Install or remove the optional per-user macOS task
with the next commands. Review notifications in macOS Settings if no banners appear.

    .venv/bin/python reminders.py --dry-run
    .venv/bin/python install_reminders.py install
    .venv/bin/python install_reminders.py uninstall

The scheduled task runs at 09:00 and 18:00 local time. Each upcoming deadline or follow-up
is notified once and appears when it falls within the next two days.
