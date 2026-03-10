@echo off
title Content Engine AI - Temporal Worker
cd /d %~dp0
call .venv\Scripts\activate
python -m app.temporal.worker
pause
