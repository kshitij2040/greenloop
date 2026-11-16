# Greenloop

Two workspaces for one collection operation:

- **Resident** at `/resident/`: sign in, save a pickup point, request or cancel a pickup, track its status, and see past outcomes.
- **Collection** at `/collection/`: coordinators assign requests; crew members see their own stops and mark arrival, collection, or an exception.

Both workspaces share one database. Each account has one role. The API enforces those roles independently of what the browser displays.

## Run on your computer

Install **Python 3.12 or newer**, then clone the repository or use **Code → Download ZIP** on GitHub. Open a terminal in the extracted project folder and run:

```sh
python3 start.py
```

**Windows:** After extracting the ZIP, double-click **Start Greenloop.bat**, or run `py -3 start.py` in Command Prompt. Keep the launcher window open while using Greenloop. The command opens the site, prints three sample logins, and saves them under the ignored `runtime/quickstart/` directory. Use the same command each time; it keeps your local review data. If a browser does not open, visit [127.0.0.1:8775](http://127.0.0.1:8775/). If that port is busy, add `--port 8776`. Stop with Ctrl+C.

No package installation, API account, database signup, or compiler is needed for the website or the Dispatch **Generate route** button. A C++17 compiler is only needed to run the separate road-graph planner.

## Walk through one collection round

1. Sign in as the sample **resident**. Choose **Set pickup point**. Enter a gate or agreed meeting point and a fictional unit number for review.
2. Choose **Pick on map**, **Use current location**, or enter coordinates manually. For a location walkthrough, use a public gate or meeting point you can verify. Using current location requires browser permission; check and adjust the pin before saving.
3. Save the pickup point and select **Request pickup**. A repeated request cannot create a second open pickup.
4. Sign out and open **Collection**. Sign in as the **coordinator**, select a crew, and assign the request.
5. Sign out and sign in as **crew**. Open the assigned stop, choose **Mark arrived**, then **Mark collected** or **Couldn’t collect** with a reason.
6. Return to the resident account to see the result in history. Use separate browser profiles if you want multiple roles open at once; tabs in one profile share a session.

OpenStreetMap links open the saved pin, not a calculated route. The Leaflet picker loads OpenStreetMap tiles on demand and needs internet access. Coordinates can be entered without the map. Opening the map or a map link contacts an external map provider. Use an agreed gate, not someone's private doorstep, when presenting the project. The public tile service is for light review use subject to its [usage policy](https://operations.osmfoundation.org/policies/tiles/); select an appropriate provider before a wider rollout.

## Create your own accounts

Use a separate database for actual pilot data. Keep one deployment/database per society for now; the coordinator has visibility across the whole deployment.

```sh
python3 manage.py init
python3 manage.py add-account coordinator dispatch@example.test "Dispatch"
python3 manage.py add-account crew crew@example.test "Collection crew"
python3 manage.py add-account resident resident@example.test "Resident"
python3 manage.py serve
```

Replace the example addresses with accounts you intend to provision. The terminal prompts for passwords without echoing them. Use distinct strong passwords, then deliver them through a private channel. There is no self-service registration or password reset in this review build. To operate a real pilot, agree an account recovery and removal procedure before inviting residents.

## GitHub and Vercel

**GitHub** holds the source and runs the included checks when you push. Create a repository and upload the contents of this folder (including hidden config files). Clone the repository on another computer and follow the local steps above. The repository and ZIP exclude credentials, databases, deployment credentials, and prior demo data. Use a fresh repo; do not upload the parent workspace.

**GitHub Pages** only serves static files. It cannot run the Python API, so it is not a standalone host for the working product. Use GitHub as the source repo and import it into Vercel for a shared online instance. See [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) and [Vercel Git integration](https://vercel.com/docs/git/vercel-for-github).

For a fresh Vercel project:

1. Create a **new Turso/libSQL database**. Do not reuse the public demo database. Set `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` in your local terminal environment using your secret manager or shell's private input. Never paste credentials into a GitHub issue, README, or chat.
2. From the repo root run `python3 manage.py --remote init`. Use `python3 manage.py --remote add-account ROLE EMAIL NAME` to provision the three roles. Do not use the local sample passwords online.
3. Import the GitHub repo in Vercel, selecting the repo root and the **Other** preset. Use the checked-in `vercel.json`; static files are in `public/` and Python runs at `api/index.py`. Add the same two variables as server-side secrets in the intended deployment environment. Keep preview and real pilot databases separate.
4. Deploy and open both workspaces. Run the walkthrough above with review accounts and verify that anonymous access to `/api/state` returns 401, crews see only their own work, and neither the SQLite file nor environment files are served.
5. Keep database backups and rotate its token as needed. Verify the plans and terms for your intended usage before deploying. No paid service is needed to run locally.

This project includes a Vercel configuration and the same shared API logic locally. A new Vercel deployment and a fresh Turso integration have **not** been created or smoke-tested for this build. The existing online demo has not been replaced.

## Tests and structure

```sh
python3 -m unittest discover -s tests -v
node --check public/assets/app.js
```

Node is optional and used only for the JavaScript syntax check. The unit suite verifies account isolation, crew assignment scope, login lockout, logout, concurrent duplicate prevention, persistence, cancellation, immutable pickup coordinates, and both completion outcomes. The local HTTP and browser walkthrough also passed, including loading the pickup map and the resident → coordinator → crew flow. GPS permission was not exercised with a real device location.

- `public/`: separate entry points and shared UI assets.
- `api/index.py`: HTTP adapter with JSON, session cookies, and cross-origin write checks.
- `greenloop.py`: role permissions, password hashing, state transitions, and SQLite/libSQL adapters.
- `schema.sql`: accounts, sessions, saved locations, and pickup snapshots.
- `manage.py`: schema setup, account creation, sample data, and local server.

## First review and pilot scope

This version implements an on-demand queue with manual assignment. Residents can cancel before dispatch. Once a pickup is created, its point is copied into the request, so editing a saved location does not redirect an already queued crew. Exact matching names and pins group stops visually; each household keeps a separate request.

The UI refreshes open screens periodically and stores outcomes server-side. It does not send SMS, WhatsApp, or push alerts. Automatic routing, vehicle capacity planning, full activity audit, self-service account recovery, offline submission, multi-society tenancy, and a field-tested real-data rollout are separate milestones. Before inviting actual households, review account lifecycle, database retention and backup/recovery, external map usage, and field connectivity with the operator.

## Project 25: route finder

The original pickup workflow remains unchanged. The crew view now includes optional **Route tools** to export assigned stops and load a route report. The separate [C++ route finder](route_tools/README.md) works offline and exports both JSON and a shareable HTML report. A C++17 compiler is required only to compute routes; it is not required to run the website. Start with `python3 route_tools/run.py --sample` from this project folder. Real route planning needs a road graph with travel times and a depot. This module does not yet do fleet capacity routing or recycling allocation.

### Plan directly in Dispatch

Sign in as coordinator, select **Generate route**, enter the depot coordinates, and select **Calculate route**. The planner uses distinct pickup points from requested and assigned stops (excluding stops already marked arrived). It returns to the depot and shows the estimated distance, nearest-stop baseline, and suggested stop order. The calculation runs offline in the browser with straight-line distances: exact for up to 12 stops, heuristic above that. It does not assign crews or account for roads, traffic, or vehicle capacity. Use the separate C++ tool with a road graph when you have road travel times.
