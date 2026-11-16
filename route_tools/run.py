"""Build the C++ planner on this computer and save an offline route report."""
import argparse
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def build():
    out = HERE / '.build'
    out.mkdir(exist_ok=True)
    source = HERE / 'route.cpp'
    executable = out / ('greenloop-route.exe' if os.name == 'nt' else 'greenloop-route')
    if executable.exists() and executable.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return executable
    compiler = os.environ.get('CXX') or next(
        (path for name in ('c++', 'g++', 'clang++', 'cl') if (path := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError('Install a C++17 compiler. On Windows, use a Visual Studio Developer Command Prompt or MinGW on PATH.')
    if Path(compiler).name.lower() in ('cl', 'cl.exe'):
        command = [compiler, '/nologo', '/std:c++17', '/EHsc', '/utf-8', '/W4', '/O2', str(source), '/Fe:' + str(executable)]
    else:
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Wpedantic', '-O2', str(source), '-o', str(executable)]
    subprocess.run(command, cwd=out, check=True, stdout=sys.stderr)
    return executable


def render(report):
    esc = lambda value: html.escape(str(value))
    baseline, plan = report['plans']
    saved = baseline['seconds'] - plan['seconds']
    rows = ''.join(f'<tr><td>{i}</td><td>{esc(stop["label"])}</td><td>{stop["leg_seconds"]} s</td><td>{stop["snap_metres"]:.1f} m</td></tr>'
                   for i, stop in enumerate(plan['stops'], 1))
    rows = rows or '<tr><td colspan="4">No routable stops</td></tr>'
    skipped = ''.join(f'<li>{esc(stop["id"])}: {esc(stop["reason"])}</li>' for stop in report['unrouted'])
    qualification = 'Exact for the routed stops and supplied road times.' if report['optimal_for_served_stops'] else 'Heuristic result; optimality is not guaranteed.'
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Greenloop route plan</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f6f5;color:#182923;font:16px system-ui}}main{{max-width:800px;margin:auto;padding:28px 18px}}
header{{border-bottom:1px solid #dce5e0;padding-bottom:14px}}h1{{margin:.4em 0}}h2{{font-size:18px}}p{{line-height:1.5}}
section{{background:white;border:1px solid #dce5e0;border-radius:12px;margin-top:14px;padding:16px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:9px 5px;text-align:left;border-top:1px solid #dce5e0}}
small{{color:#52665e}}strong{{color:#18553f}}@media print{{body{{background:white}}main{{padding:0}}}}
</style><main><header><strong>Greenloop · Collection</strong><h1>Route plan</h1><small>Start and return: {esc(report['depot'])}</small></header>
<section><h2>{esc(plan['strategy'])}</h2><p><strong>{plan['seconds']} s</strong> estimated travel · {len(plan['stops'])}/{report['requested']} stops routed</p>
<p>Nearest neighbour: {baseline['seconds']} s · Difference: {saved} s</p><small>{qualification} Travel only; service time excluded.</small></section>
<section><h2>Stop order</h2><table><thead><tr><th>#</th><th>Pickup point</th><th>Travel</th><th>Pin offset</th></tr></thead><tbody>{rows}</tbody></table><p>Return to depot: {plan['return_seconds']} s</p></section>
{('<section><h2>Unrouted stops</h2><ul>'+skipped+'</ul></section>') if skipped else ''}
</main></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', action='store_true')
    for name in ('nodes', 'roads', 'stops', 'depot'):
        parser.add_argument('--' + name)
    parser.add_argument('--max-snap', default='150', help='Maximum pin-to-road-node distance in metres')
    parser.add_argument('--out', type=Path, default=HERE.parent / 'runtime' / 'route-report')
    args = parser.parse_args()
    if args.sample:
        if any((args.nodes, args.roads, args.stops, args.depot)):
            parser.error('--sample cannot be combined with custom inputs')
        args.nodes, args.roads, args.stops = [HERE/'sample'/(name+'.tsv') for name in ('nodes','roads','stops')]
        args.depot = 'D'
    elif not all((args.nodes, args.roads, args.stops, args.depot)):
        parser.error('Provide --sample or all of --nodes --roads --stops --depot')
    try:
        cmd = [str(build()), str(args.nodes), str(args.roads), str(args.stops), args.depot, args.max_snap]
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, encoding='utf-8')
        report = json.loads(result.stdout)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out/'route-plan.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        (args.out/'route-plan.html').write_text(render(report), encoding='utf-8')
        print(f"Routed {len(report['plans'][1]['stops'])}/{report['requested']} stops. Report: {args.out.resolve()/'route-plan.html'}")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
