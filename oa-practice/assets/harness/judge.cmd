@echo off
rem Submit: run every hidden test and print a score. This is your "Submit" button.
rem Arguments are forwarded to oa.py: --reveal N, --force, and --llm (an LLM
rem post-mortem after a 100% score; opt-in, and it sends your code off the machine).
setlocal
cd /d "%~dp0"
if defined OA_PYTHON goto :go
rem See run.cmd — python3.exe on PATH is usually the Microsoft Store stub, and the
rem recorded .oa\python-path is the backstop when nothing on PATH works.
for %%P in (py python3 python) do (
    %%P -c "import sys; sys.exit(sys.version_info[0] < 3)" >nul 2>&1 && (
        set "OA_PYTHON=%%P" & goto :go
    )
)
if not exist ".oa\python-path" goto :nopy
set /p OA_PYTHON=<".oa\python-path"
"%OA_PYTHON%" -c "import sys; sys.exit(sys.version_info[0] < 3)" >nul 2>&1 && goto :go
:nopy
echo No working Python 3 found ^(tried py, python3, python^).>&2
echo Install Python 3 from https://www.python.org/downloads/, or set OA_PYTHON.>&2
exit /b 127
:go
"%OA_PYTHON%" oa.py judge %*
exit /b %errorlevel%
