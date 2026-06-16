"""VSE Local Transcript Runner — Windows Service (pywin32).

CO: Natywny Windows Service wrapper dla runner.py, używa pywin32.

Instalacja:   python service.py install  (jako Administrator)
Start:        python service.py start    (lub: net start VSELocalRunner)
Stop:         python service.py stop     (lub: net stop VSELocalRunner)
Debug:        python service.py debug    (bez instalacji, jako zwykły user)
Deinstalacja: python service.py remove   (jako Administrator)

Alternatywnie — Task Scheduler (nie wymaga Admina przy startowaniu):
  Task: VSELocalRunner
  Action: python service.py debug
  WorkingDir: <sciezka do local-runner/>
  Trigger: AtLogOn
"""
import logging
import os
import sys
import threading

# KRYTYCZNE: ustaw ścieżki ZANIM cokolwiek zaimportujemy z local-runner
# Gdy Windows startuje service, cwd = C:\Windows\System32 — nie nasz katalog
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SERVICE_DIR)

# Katalog logów: próbuj ProgramData, fallback do lokalnego katalogu
LOG_DIR_SYSTEM = os.path.join(
    os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "VSELocalRunner"
)

try:
    os.makedirs(LOG_DIR_SYSTEM, exist_ok=True)
    _test_file = os.path.join(LOG_DIR_SYSTEM, ".write_test")
    with open(_test_file, "w") as _tf:
        _tf.write("ok")
    os.remove(_test_file)
    LOG_DIR = LOG_DIR_SYSTEM
except (PermissionError, OSError):
    LOG_DIR = SERVICE_DIR  # fallback — lokalny katalog

LOG_FILE = os.path.join(LOG_DIR, "runner.log")

# Konfiguracja loggera
_log_handlers: list = []
try:
    _log_handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))
except (PermissionError, OSError) as e:
    # Spróbuj lokalny katalog jako fallback
    _fallback_log = os.path.join(SERVICE_DIR, "runner.log")
    try:
        _log_handlers.append(logging.FileHandler(_fallback_log, encoding="utf-8"))
        LOG_FILE = _fallback_log
    except (PermissionError, OSError):
        pass

if sys.stdout and hasattr(sys.stdout, "write"):
    try:
        _log_handlers.append(logging.StreamHandler(sys.stdout))
    except Exception:
        pass

if not _log_handlers:
    _log_handlers = [logging.NullHandler()]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_log_handlers,
)
log = logging.getLogger("vse_service")
log.info("service.py starting | SERVICE_DIR=%s | LOG_FILE=%s", SERVICE_DIR, LOG_FILE)

# Wczytaj .env ZANIM zaimportujemy pywin32
_env_path = os.path.join(SERVICE_DIR, ".env")
if os.path.exists(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)
        log.info("Loaded .env from %s", _env_path)
    except ImportError:
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    os.environ.setdefault(_k.strip(), _v.strip())
        log.info("Loaded .env manually")
else:
    log.warning(".env not found at %s", _env_path)

try:
    import win32event
    import win32service
    import win32serviceutil
    import servicemanager
    PYWIN32_OK = True
except ImportError as e:
    log.error("pywin32 not available: %s", e)
    PYWIN32_OK = False

# ---------------------------------------------------------------------------
# Globalna flaga stopu
# ---------------------------------------------------------------------------
_stop_requested = threading.Event()


def _runner_loop():
    """Pętla pollowania jobów."""
    import time
    try:
        import runner as r

        poll_interval = int(os.environ.get("POLL_INTERVAL", "10"))
        log.info(
            "Runner loop started | API=%s | poll=%ds | token_set=%s",
            r.API_BASE, poll_interval, bool(r.TOKEN),
        )

        if not r.TOKEN:
            log.error(
                "LOCAL_RUNNER_TOKEN not set! "
                "Edit .env at: %s", _env_path
            )
            return

        while not _stop_requested.is_set():
            try:
                jobs = r.get_pending_jobs()
                if jobs:
                    log.info("%d pending job(s)", len(jobs))
                    for job in jobs:
                        if _stop_requested.is_set():
                            break
                        r.process_job(job)
            except Exception as e:
                log.error("Loop error: %s", e)

            _stop_requested.wait(timeout=poll_interval)

        log.info("Runner loop stopped cleanly")

    except Exception as e:
        log.error("Runner fatal error: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Windows Service class
# ---------------------------------------------------------------------------

if PYWIN32_OK:
    class VSELocalRunnerService(win32serviceutil.ServiceFramework):
        _svc_name_ = "VSELocalRunner"
        _svc_display_name_ = "VSE Local Transcript Runner"
        _svc_description_ = (
            "Pobiera transkrypty YouTube lokalnie dla PressAI Video SEO Engine."
        )

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._hWaitStop = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            log.info("SvcStop called")
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            _stop_requested.set()
            win32event.SetEvent(self._hWaitStop)

        def SvcDoRun(self):
            log.info("SvcDoRun — service starting | cwd=%s", os.getcwd())
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            os.chdir(SERVICE_DIR)
            _stop_requested.clear()
            t = threading.Thread(target=_runner_loop, name="runner_loop", daemon=True)
            t.start()
            log.info("Service running — waiting for stop")
            win32event.WaitForSingleObject(self._hWaitStop, win32event.INFINITE)
            _stop_requested.set()
            t.join(timeout=15)
            log.info("Service stopped")


def main():
    if not PYWIN32_OK:
        print("ERROR: pywin32 not available. Install with: pip install pywin32")
        sys.exit(1)

    args = sys.argv[1:] if len(sys.argv) > 1 else []
    cmd = args[0].lower() if args else ""

    if cmd == "debug":
        # Debug / Task Scheduler mode: uruchom bez instalacji
        print(f"=== VSE Runner DEBUG mode ===")
        print(f"SERVICE_DIR: {SERVICE_DIR}")
        print(f"LOG_FILE:    {LOG_FILE}")
        print(f"TOKEN set:   {bool(os.environ.get('LOCAL_RUNNER_TOKEN'))}")
        print(f"API_BASE:    {os.environ.get('VSE_API_BASE', 'https://vse.impresjapr.pl')}")
        print("Starting loop (Ctrl+C to stop)...")
        os.chdir(SERVICE_DIR)
        try:
            _runner_loop()
        except KeyboardInterrupt:
            print("\nStopped.")
    elif not args:
        # Uruchomiony przez SCM
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(VSELocalRunnerService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(VSELocalRunnerService)


if __name__ == "__main__":
    main()
