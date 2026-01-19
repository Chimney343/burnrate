#!/usr/bin/env just --justfile

set shell := ["powershell", "-c"]

default:
    @just --list

install:
    poetry install

download:
    cd src; poetry run python main.py

download-debug:
    cd src; $env:LOG_LEVEL = 'DEBUG'; poetry run python main.py

download-extended:
    cd src; $env:DAYS_BACK = '90'; poetry run python main.py

download-all:
    cd src; $env:DAYS_BACK = '0'; poetry run python main.py

download-slow:
    cd src; $env:ACTIVITY_LIMIT = '50'; poetry run python main.py

quickstart:
    python QUICKSTART.py

clean-data:
    @if (Test-Path data) { Remove-Item -Recurse -Force data; Write-Host "Cleaned data directory" } else { Write-Host "No data directory found" }

clean-tokens:
    @$tokenPath = "$env:USERPROFILE\.garminconnect"; if (Test-Path $tokenPath) { Remove-Item -Recurse -Force $tokenPath; Write-Host "Cleared tokens" } else { Write-Host "No tokens found" }

clean-all: clean-data clean-tokens
    @Write-Host "All data and tokens cleared"

show-config:
    @Write-Host "`nConfiguration:"
    @if (Test-Path .env) { Select-String -Path .env -Pattern '^[A-Z_]+=' | ForEach-Object { Write-Host $_.Line } } else { Write-Host ".env file not found" }

show-stats:
    @if (Test-Path data) { $size = (Get-ChildItem -Path data -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host "Data size: $([math]::Round($size, 2)) MB" } else { Write-Host "No data directory" }

setup:
    @if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env - please edit with your credentials" } else { Write-Host ".env already exists" }

open-data:
    @if (Test-Path data) { Invoke-Item data } else { Write-Host "No data directory found" }

help:
    @Write-Host "Garmin Data Downloader Commands:"
    @Write-Host "  just download        - Run download with default settings"
    @Write-Host "  just download-debug  - Run with debug logging"
    @Write-Host "  just download-extended - Download 90 days instead of 30"
    @Write-Host "  just download-slow   - Lower API request rate"
    @Write-Host "  just install         - Install dependencies"
    @Write-Host "  just setup           - Create .env from template"
    @Write-Host "  just clean-all       - Clear data and tokens"
    @Write-Host "  just open-data       - Open data directory"

list:
    @just --list --unsorted
