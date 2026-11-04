# Server test: auth hardening + chat route checks (PR #151)

Temporary: delete this file before PR #151 merges.

Branch `claude/auth-hardening-21bfaa`, level with master. No new pip or npm packages; the frontend needs a rebuild (the login screen changed).

The plan: keep the database, delete every user but `demo`, add your own account with a new PIN, and keep `DEMO_USER=true` while you're the only one on the network. The result is the database going forward, not a test copy.

**Don't switch the server back to master before #151 merges.** Logins on this branch re-hash PINs with scrypt, which master can't check. To go back early, restore `old-db` as well (see the end).

Run these in PowerShell or cmd, starting in the repo folder.

## 1. Stop the backend and switch

Close the start-server window first: SQLite runs in WAL mode, so the database should only be copied once nothing has it open. Switching doesn't touch the database (git ignores every `.db`, `-wal` and `-shm` file).

```
git status
git fetch
git switch claude/auth-hardening-21bfaa
git pull
git log --oneline -3
```

`git status` should be clean, since local changes can block the switch. The log shows `69bc6e4 docs: 6-10 digit PINs and the per-device login limit` below the commit that added this file.

## 2. Back up the database

Copy, don't move:

```
cd backend
mkdir old-db
copy breakFAST.db* old-db\
```

## 3. Users

Still in `backend`:

```
python manage.py list-users
python manage.py delete-user "OldName"
python manage.py add-user "YourName" --admin
python manage.py list-users
```

- `delete-user` once per name except demo; each user's data goes with them.
- `add-user` asks for a 6-10 digit PIN twice. A 5- or 11-digit PIN is refused ("A PIN needs 6-10 digits").
- The last `list-users` shows demo and you.

## 4. Keep demo open for now

`backend\.env` keeps `DEMO_USER=true`: on this branch demo's empty PIN logs in only while it's on. Set it to false (or remove it) before anyone else gets on the network; that locks demo without deleting it.

## 5. Rebuild and start

```
cd ..\frontend
npm run build
cd ..
start-server.bat
```

## 6. Log in

Log in as yourself and as demo. A login takes a moment now (about a quarter second, longer on a slow CPU). Demo's first login upgrades its old hash. In a second window, in `backend`:

```
python -c "import sqlite3,config; db=sqlite3.connect(config.DATABASE_PATH); print([(n, h[:6] == 'scrypt') for n, h in db.execute('SELECT name, pin_hash FROM users')])"
```

It prints True for both of you.

## 7. Change your PIN

```
python manage.py set-pin "YourName"
```

It asks twice and prints "PIN changed for 'YourName'." Log in with the new PIN.

## 8. Lockout

```
python manage.py add-user "Tester"
```

On one device, type a wrong PIN for Tester five times:

- tries 1-4: "Invalid name or PIN";
- try 5: "Too many failed logins. Try again in 30 seconds.";
- Tester's right PIN during the wait gets the same message;
- during the wait you can still log in as yourself on that device, and Tester can log in from another device;
- after 30 s, Tester's right PIN logs in.

Then:

```
python manage.py delete-user "Tester"
```

## 9. Chat

Send a chat message and press Suggest. Both work as before, and the server window shows no new errors.

## If something goes wrong

- A login fails unexpectedly: `python manage.py set-pin "Name"` resets the PIN, and restarting the backend clears the failed-login counts.
- Undo everything: close the start-server window, delete `breakFAST.db`, `breakFAST.db-wal` and `breakFAST.db-shm` in `backend` (a leftover `-wal` from this test would be read into the old database), copy the files from `backend\old-db` back into `backend`, then `git switch master`.

## After the test

Once everything passes and #151 is merged: `git switch master`, `git pull`, and delete `backend\old-db`.
