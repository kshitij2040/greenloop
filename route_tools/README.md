# Greenloop route finder

This is the first Project 25 algorithm module. It runs offline and can be copied independently of the website. It plans a **single crew round trip**, starting and ending at a supplied depot. It does not assign vehicles, model load capacity, find directions on a public map, or allocate recycling.

## Quick run

Install Python 3.12 and a C++17 compiler. On macOS, use the Xcode Command Line Tools; on Linux, use GCC or Clang; on Windows, use MinGW on PATH or run from a Visual Studio Developer Command Prompt. From this folder:

```sh
python3 run.py --sample --out route-report
```

On Windows replace `python3` with `py -3.12`. The script compiles the C++ executable for **this** machine and saves `route-report/route-plan.html` and `route-report/route-plan.json`. Open the HTML report in any browser or send it to another computer; viewing it requires neither Python nor a compiler. The package includes a small **illustrative graph**, not surveyed roads or traffic.

With CMake instead: `cmake -S . -B .build/cmake` then `cmake --build .build/cmake --config Release`. The C++ program prints JSON to stdout. Positional args: `nodes.tsv roads.tsv stops.tsv depot [max-snap-metres]`.

## Use with Collection

1. Sign in as a crew member. Under **Route tools**, click **Export stops**. The downloaded TSV contains point names, request IDs used as stop identifiers, and coordinates. It omits resident names and unit numbers. Keep real exports and reports private.
2. Provide your approved road graph (see below), and run:
   ```sh
   python3 run.py --nodes nodes.tsv --roads roads.tsv --stops greenloop-stops.tsv --depot D --out route-report
   ```
3. Open the standalone HTML report, or in Collection choose **Load route plan** and select `route-plan.json`. The browser reads it locally and checks that it matches the currently assigned stops. The plan is a preview only; it does not alter assignments or pickup status. Export and rerun after stops change.

## Road data and assumptions

All three input files are UTF-8 TSV (tab-separated), with a header and one record per line. Use the sample files as templates.

| File | Columns |
|---|---|
| nodes.tsv | id, latitude, longitude |
| roads.tsv | from, to, seconds |
| stops.tsv | id, label, latitude, longitude |

Edges are directed and their positive integer times are in seconds. Add both directions separately if allowed. Represent junctions and legal entry points; if a turn restriction matters, encode it in the road graph. Coordinates only match a pickup to the nearest graph node; they never substitute for travel times. Default snap radius is 150 m; use a smaller value where there are nearby parallel roads or opposite gates. Confirm each match for a real walkthrough. Stops too far from the graph or without a path both to and from the depot are listed as **unrouted**, never silently dropped. A shortest road path can pass a stop before its scheduled service.

The tool caps inputs at 10,000 nodes, 100,000 directed edges and 100 stops. Travel estimates exclude loading time, traffic changes and access delays. Real use needs a locally validated graph and depot; exported website pins alone are insufficient.

## Implemented algorithms

- **Dijkstra** builds a shortest travel-time matrix over the depot and routable stops.
- **Nearest neighbour** supplies the baseline.
- **Held–Karp subset DP** gives an exact minimum-cost round trip for up to 12 routable stops on this matrix: O(n²·2ⁿ) time and O(n·2ⁿ) space.
- Above 12 stops, the tool improves the baseline with bounded pair swaps; no optimality claim. Each comparison recalculates directed leg costs including the return to depot.

For the sample, nearest neighbour is **375 seconds** and the exact route is **356 seconds**. These are fixture results, not measured savings. The JSON timings cover strategy evaluation, not graph loading, snapping or Dijkstra. Full syllabus coverage, benchmark reporting, multi-vehicle capacity routing and recycling allocation are later work.
