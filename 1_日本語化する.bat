@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PYTHONUTF8=1
set "PY="
where py > nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python > nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY goto nopython
%PY% -c "import sys" > nul 2>&1
if errorlevel 1 goto nopython
echo === EVO 日本語化（適用） ===
%PY% evo_ja.py apply
echo.
pause
exit /b 0
:nopython
echo Python が見つかりません。
echo https://www.python.org/downloads/ からインストールしてください。
echo （インストール時に「Add python.exe to PATH」にチェックを入れてください）
pause
exit /b 1
