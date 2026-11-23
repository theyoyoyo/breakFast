"""
Shared test fixtures for the break FAST backend.

Each test function gets a fresh SQLite database via the `client` fixture,
which patches database.DATABASE_PATH before creating the FastAPI test client.
A test user is created and all requests include the auth token.
PINs are hashed at a tiny scrypt cost unless a test is marked real_scrypt, every test
starts with no failed logins counted, and it must end with no user's chat request slot held.

The tests run with their own settings, whatever the machine's `.env` or shell says: `.env` is
never loaded, every setting config.py reads starts at its default, and Ollama's address is one
that can't resolve. No test can reach the network: Ollama counts as unreachable unless a test
fakes it, and a test that still tries a real connection fails.
"""

import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

# The settings config.py reads, cleared so each starts at its default (a developer's .env or
# shell can't turn on the demo user, API docs or a model override), then the few the tests set.
_SETTINGS = ("DATABASE_PATH", "CORS_ORIGINS", "SERVE_FRONTEND", "API_DOCS", "DEMO_USER")
for _key in list(os.environ):
    if _key.startswith("OLLAMA_") or _key in _SETTINGS:
        del os.environ[_key]
os.environ["OLLAMA_BASE_URL"] = "http://ollama.invalid"  # .invalid never resolves (RFC 2606)
# A test that forgets its own database writes here, never to the real one
_SCRATCH = tempfile.mkdtemp(prefix="breakfast-tests-")
os.environ["DATABASE_PATH"] = str(Path(_SCRATCH) / "unused.db")

# config.py calls load_dotenv() at import; make it a no-op before anything imports config
import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *args, **kwargs: False

# Make backend/ importable without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


def pytest_sessionfinish(session, exitstatus):
    """Remove the scratch folder behind the tests' DATABASE_PATH."""
    shutil.rmtree(_SCRATCH, ignore_errors=True)


_LOCAL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1", "0.0.0.0"}


@pytest.fixture(autouse=True)
def no_network():
    """Fail any test that opens a real connection: an HTTP request through httpx's network
    transports (ASGI and mock transports stay allowed) or a name lookup or socket connect to a
    host that isn't this machine. The attempt also raises, as if the network were down, so code
    that catches the error can't hide it; the test fails at teardown either way. It keeps its own
    MonkeyPatch, so a test's monkeypatch.undo() can't lift it. Yields the attempts, so the guard's
    own test can check and clear them."""
    attempts = []
    monkeypatch = pytest.MonkeyPatch()

    def refuse(what):
        attempts.append(what)
        raise httpx.ConnectError(f"tests may not use the network: {what}")

    async def async_request(self, request):
        refuse(f"HTTP {request.method} {request.url}")

    def sync_request(self, request):
        refuse(f"HTTP {request.method} {request.url}")

    real_getaddrinfo = socket.getaddrinfo
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def getaddrinfo(host, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else host
        if name not in _LOCAL_HOSTS:
            refuse(f"name lookup {name}")
        return real_getaddrinfo(host, *args, **kwargs)

    def is_local(address):
        host = address[0] if isinstance(address, tuple) else None
        return not isinstance(address, tuple) or host in _LOCAL_HOSTS or str(host).startswith("127.")

    def connect(self, address):
        if not is_local(address):
            refuse(f"connect {address}")
        return real_connect(self, address)

    def connect_ex(self, address):
        if not is_local(address):
            refuse(f"connect {address}")
        return real_connect_ex(self, address)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_request)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", sync_request)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    yield attempts
    monkeypatch.undo()
    if attempts:
        pytest.fail(f"test tried the network: {attempts}")


@pytest.fixture(autouse=True)
def ollama_unreachable():
    """Ollama counts as unreachable unless a test fakes it (tests that need it up patch
    check_llm_availability or the call itself), so no test waits on a real connection. Its own
    MonkeyPatch, like no_network's."""
    from services import llm

    async def unreachable():
        return False

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(llm, "check_llm_availability", unreachable)
        yield


@pytest.fixture(autouse=True)
def no_model_settings_file(tmp_path):
    """Point the model picker's settings file at an empty folder, so a real backend/model_settings.json
    never changes which model a test's calls name. Set without monkeypatch, so a test's
    monkeypatch.undo() (the config reload tests) doesn't bring the real file back; first, so it's undone last."""
    from services import llm
    from services.model_settings import ModelSettingsFile

    saved = llm.MODEL_SETTINGS_PATH, llm._model_settings
    llm.MODEL_SETTINGS_PATH, llm._model_settings = tmp_path / "model_settings.json", ModelSettingsFile()
    yield
    llm.MODEL_SETTINGS_PATH, llm._model_settings = saved


@pytest.fixture(autouse=True)
def fast_pin_hashing(request, monkeypatch):
    """Hash PINs at a tiny scrypt cost, since the real one is slow on purpose."""
    if request.node.get_closest_marker("real_scrypt"):
        return
    import auth

    monkeypatch.setattr(auth, "SCRYPT_N", 2**4)
    monkeypatch.setattr(auth, "SCRYPT_P", 1)


@pytest.fixture(autouse=True)
def no_login_failures():
    """Start every test with no failed logins counted (they live in memory, like the tokens)."""
    import auth

    auth._login_failures.clear()


@pytest.fixture(autouse=True)
def no_held_request_slot():
    """Fail any test that ends with a user's request slot still taken (#266): every way a chat request
    ends must free it. Cleared either way, so one test's leftover can't make the next one busy."""
    from services import chat_tasks

    chat_tasks._running.clear()
    yield
    held = list(chat_tasks._running)
    chat_tasks._running.clear()
    if held:
        pytest.fail(f"a request slot was still held at the end of the test: users {held}")


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    """AsyncClient pointed at the FastAPI app with an isolated per-test database."""
    db_path = str(tmp_path / "test.db")

    import database

    monkeypatch.setattr(database, "DATABASE_PATH", db_path)

    # Initialize schema on the temp file (idempotent; uses IF NOT EXISTS)
    await database.init_db()

    # Create a test user
    from auth import create_token, hash_pin

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash, is_admin) VALUES (?, ?, ?)",
            ("testuser", hash_pin("1234"), 1),
        )
        await db.commit()
        async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
            row = await cur.fetchone()
            user_id = row[0]

    token = create_token(user_id)

    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db(client, tmp_path):
    """Direct database connection for tests that need to manipulate data beyond the API."""
    import database

    async with aiosqlite.connect(database.DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn
