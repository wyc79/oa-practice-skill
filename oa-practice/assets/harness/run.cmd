@echo off
rem Run the sample tests only. This is your "Run Code" button.
setlocal
cd /d "%~dp0"
if defined OA_PYTHON goto :go
rem `py` first: the launcher is the real interpreter, while python3.exe on PATH is
rem usually the Microsoft Store stub, which exists but refuses to run anything.
for %%P in (py python3 python) do (
    %%P -c "import sys; sys.exit(sys.version_info[0] < 3)" >nul 2>&1 && (
        set "OA_PYTHON=%%P" & goto :go
    )
)
rem Nothing on PATH works. .oa\python-path holds the interpreter that scaffolded this
rem workspace, which is a working Python 3 by construction. PATH is tried first so the
rem folder stays portable; this is the backstop.
if not exist ".oa\python-path" goto :nopy
set /p OA_PYTHON=<".oa\python-path"
"%OA_PYTHON%" -c "import sys; sys.exit(sys.version_info[0] < 3)" >nul 2>&1 && goto :go
:nopy
echo No working Python 3 found ^(tried py, python3, python^).>&2
echo Install Python 3 from https://www.python.org/downloads/, or set OA_PYTHON.>&2
exit /b 127
:go
"%OA_PYTHON%" oa.py run %*
exit /b %errorlevel%
