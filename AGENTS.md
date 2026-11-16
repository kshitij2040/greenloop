# Greenloop agent setup

When asked to set up Greenloop on Windows, perform these steps from the repository root and report the result.

1. If the source is missing, clone `https://github.com/kshitij2040/greenloop.git` or download and extract the ZIP from GitHub. Work in the folder containing `start.py`.
2. Check for Python 3.12 or newer with `py -3 --version` or `python --version`. Install it from [python.org](https://www.python.org/downloads/windows/) if needed. Use a Python executable that passes the version check.
3. Launch `Start Greenloop.bat` in a dedicated terminal and leave it running. You can also use `py -3 start.py` or `python start.py` with the verified interpreter. If port 8775 is already in use, rerun with `--port 8776` and use the new port in the next step.
4. Check that `http://127.0.0.1:8775/resident/` and `http://127.0.0.1:8775/collection/` respond. Confirm that the launcher printed the sample resident, coordinator, and crew logins. Point the user to the launcher window for those credentials and keep the server running for them to review.

The local website uses SQLite and the Python standard library. It requires no package install, cloud account, or C++ compiler. The launcher creates and reuses local demo data under `runtime/quickstart/`. For the walkthrough and separate C++ road-graph planner, see [README.md](README.md).
