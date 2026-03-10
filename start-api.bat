@echo off
title Content Engine AI - API Server
cd /d %~dp0
call .venv\Scripts\activate
python run.py
pause
