CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('resident','crew','coordinator')), password TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0, locked_until INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id), expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires);
CREATE TABLE IF NOT EXISTS locations (resident_id TEXT PRIMARY KEY REFERENCES accounts(id), point TEXT NOT NULL, unit TEXT NOT NULL, note TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL);
CREATE TABLE IF NOT EXISTS pickups (id TEXT PRIMARY KEY, resident_id TEXT NOT NULL REFERENCES accounts(id), assigned_to TEXT REFERENCES accounts(id), status TEXT NOT NULL CHECK(status IN ('requested','assigned','arrived','collected','unavailable','cancelled')), point TEXT NOT NULL, unit TEXT NOT NULL, note TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL, reason TEXT NOT NULL DEFAULT '');
CREATE UNIQUE INDEX IF NOT EXISTS one_open_pickup ON pickups(resident_id) WHERE status IN ('requested','assigned','arrived');
CREATE INDEX IF NOT EXISTS pickups_crew ON pickups(assigned_to, status, created);
