import itertools
import json
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from route_tools.run import build, render

SAMPLE = Path(__file__).resolve().parents[1]/'route_tools'/'sample'


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = build()

    def run_plan(self, nodes, roads, stops):
        result = subprocess.run([str(self.binary), str(nodes), str(roads), str(stops), 'D', '50'],
                                check=True, capture_output=True, encoding='utf-8')
        return json.loads(result.stdout)

    def test_sample(self):
        report = self.run_plan(*(SAMPLE/(x+'.tsv') for x in ('nodes','roads','stops')))
        self.assertEqual([p['seconds'] for p in report['plans']], [375,356])
        self.assertEqual(report['unrouted'],[])
        self.assertIn('356 s',render(report))

    def fixture(self, count, *, disconnected=False):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        folder = Path(folder.name)
        ids = ['D']+[str(i) for i in range(1,count+1)]
        rng=random.Random(123)
        times=[[0 if a==b else rng.randint(20,200) for b in ids] for a in ids]
        def save(file, header, rows):
            (folder/file).write_text(header+'\n'+'\n'.join('\t'.join(map(str,row)) for row in rows)+'\n',encoding='utf-8')
            return folder/file
        nodes=save('nodes.tsv','id\tlatitude\tlongitude',[(id,i/100,0) for i,id in enumerate(ids)])
        roads=save('roads.tsv','from\tto\tseconds',[(a,b,times[i][j]) for i,a in enumerate(ids)
                    for j,b in enumerate(ids) if i!=j and (not disconnected or i!=count)])
        stop_rows=[(id, 'Point <'+id+'>',i/100,0) for i,id in enumerate(ids) if i]
        if disconnected:stop_rows.append(('far','Far pin',40,40))
        stops=save('stops.tsv','id\tlabel\tlatitude\tlongitude',stop_rows)
        return (nodes,roads,stops),times

    def test_exact_matches_brute_force(self):
        paths,times = self.fixture(6)
        n=len(times)
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    times[i][j]=min(times[i][j],times[i][k]+times[k][j])
        expected=min(sum(times[a][b] for a,b in zip((0,)+order,order+(0,))) for order in itertools.permutations(range(1,n)))
        report=self.run_plan(*paths)
        self.assertEqual(report['plans'][1]['seconds'],expected)
        self.assertTrue(report['optimal_for_served_stops'])
        self.assertIn('Point &lt;', render(report))

    def test_heuristic_does_not_worsen_baseline(self):
        paths,_=self.fixture(18)
        report=self.run_plan(*paths)
        self.assertFalse(report['optimal_for_served_stops'])
        baseline,improved=report['plans']
        self.assertLessEqual(improved['seconds'],baseline['seconds'])
        self.assertEqual({p['id'] for p in improved['stops']},{str(i) for i in range(1,19)})

    def test_one_way_and_outside_snap(self):
        paths,_=self.fixture(3,disconnected=True)
        report=self.run_plan(*paths)
        self.assertEqual({p['id']:p['reason'] for p in report['unrouted']},
                         {'3':'No round trip to depot','far':'No road node within snap limit'})

    def test_invalid_road_time_fails(self):
        paths,_=self.fixture(2)
        paths[1].write_text('from\tto\tseconds\nD\t1\t-5\n',encoding='utf-8')
        proc=subprocess.run([str(self.binary),*(str(p) for p in paths),'D'],capture_output=True)
        self.assertNotEqual(proc.returncode,0)
        self.assertIn(b'Road time',proc.stderr)
