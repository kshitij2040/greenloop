import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path
from greenloop import APIError, Database, Service, create_account


class PickupFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(Path(self.tmp.name) / 'test.sqlite3')
        self.db.setup()
        self.api = Service(self.db)
        self.password = 'test-password-only'
        self.cookies = {}
        for name,role in [('maya','resident'),('dev','resident'),('north','crew'),('south','crew'),('dispatch','coordinator')]:
            email = name+'@example.test'
            create_account(self.db,role,email,name,self.password)
            _,cookie = self.api.handle('POST','/api/login',{'email':email,'password':self.password,
                        'portal':'resident' if role=='resident' else 'collection'},secure=True)
            self.assertIn('HttpOnly; SameSite=Strict; Secure',cookie)
            self.cookies[name] = cookie.split(';')[0]

    def call(self, who, path, data=None):
        result,_ = self.api.handle('GET' if data is None else 'POST','/api/'+path,data or {},self.cookies.get(who,''))
        return result

    def fails(self, status, *args):
        with self.assertRaises(APIError) as e:
            self.call(*args)
        self.assertEqual(e.exception.status,status)

    def test_dispatch_and_persistence(self):
        self.fails(401,'anonymous','state')
        self.fails(409,'maya','request',{})
        self.call('maya','location',dict(point='East gate',unit='B-204',note='Security desk',lat=19.076,lon=72.8777))
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _:self.call('maya','request',{}),range(4)))
        pickup, = self.call('maya','state')['pickups']
        self.assertEqual(pickup['status'],'requested')
        self.assertEqual(self.call('dev','state')['pickups'],[])
        self.assertEqual(self.call('north','state')['pickups'],[])
        self.call('maya','location',dict(point='West gate',unit='B-204',note='',lat=19.075,lon=72.877))
        self.assertEqual(self.call('maya','state')['pickups'][0]['point'],'East gate')
        self.assertEqual(self.call('maya','state')['location']['point'],'West gate')
        crew = {c['name']:c['id'] for c in self.call('dispatch','state')['crew']}
        self.fails(403,'maya','assign',{'id':pickup['id'],'crew':crew['north']})
        self.call('dispatch','assign',{'id':pickup['id'],'crew':crew['north']})
        self.fails(409,'maya','cancel',{'id':pickup['id']})
        self.fails(409,'south','status',{'id':pickup['id'],'status':'arrived'})
        self.fails(409,'north','status',{'id':pickup['id'],'status':'collected'})
        self.call('north','status',{'id':pickup['id'],'status':'arrived'})
        self.fails(409,'dispatch','assign',{'id':pickup['id'],'crew':crew['south']})
        self.assertEqual(self.call('maya','state')['pickups'][0]['status'],'arrived')
        self.api = Service(Database(self.db.path))
        self.call('north','status',{'id':pickup['id'],'status':'collected'})
        self.assertEqual(self.call('maya','state')['pickups'][0]['status'],'collected')
        self.call('maya','request',{})
        current = self.call('maya','state')['pickups'][0]
        self.call('maya','cancel',{'id':current['id']})
        self.call('maya','request',{})
        current = self.call('maya','state')['pickups'][0]
        self.call('dispatch','assign',{'id':current['id'],'crew':crew['north']})
        self.call('north','status',{'id':current['id'],'status':'arrived'})
        self.fails(400,'north','status',{'id':current['id'],'status':'unavailable'})
        self.call('north','status',{'id':current['id'],'status':'unavailable','reason':'Access blocked'})
        rows = {p['id']:p for p in self.call('maya','state')['pickups']}
        self.assertEqual(rows[current['id']]['reason'],'Access blocked')

    def test_role_and_logout(self):
        self.fails(403,'north','location',{})
        self.fails(400,'maya','location',dict(point='A',unit='1',lat='nan',lon='0'))
        self.fails(403,'anonymous','login',dict(email='maya@example.test',password=self.password,portal='collection'))
        self.call('maya','logout',{})
        self.fails(401,'maya','state')

    def test_login_lockout(self):
        payload = dict(email='maya@example.test',password='incorrect',portal='resident')
        for _ in range(5):
            self.fails(401,'anonymous','login',payload)
        self.fails(429,'anonymous','login',{**payload,'password':self.password})

    def test_storage_does_not_contain_cleartext_credentials(self):
        self.assertNotIn(self.password,self.db.sql('SELECT password FROM accounts LIMIT 1')[0]['password'])
        self.assertNotIn(self.cookies['maya'].split('=')[1],{row['digest'] for row in self.db.sql('SELECT digest FROM sessions')})


if __name__=='__main__':
    unittest.main()
