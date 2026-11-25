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

Deadlines and follow-ups are shown in the app. Background notifications and Gmail integration are outside this release. Match scores are based on skills you enter and words found in the chosen CV.
The semantic search reranks up to 120 keyword-ranked candidates. AI output can be incomplete
and should be checked against the displayed evidence.

## Local data

Data is stored in \`data/\` (or \`APP_DATA_DIR\` if set). Stop the app before backing it up:

    python3 backup.py backup /absolute/path/to/new-backup
    python3 backup.py restore /absolute/path/to/existing-backup

Restore requires the data directory to be absent. To uninstall, stop the app, back up data you
want to keep, and remove the project folder. The public landing page contains project information.
