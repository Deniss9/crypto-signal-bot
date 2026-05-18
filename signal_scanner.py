name: Crypto Signal Scanner

on:
  push:
    branches: [ main ]
  schedule:
    - cron: '*/5 * * * *'

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Run scanner
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          MIN_SIGNALS: ${{ secrets.MIN_SIGNALS }}
        run: |
          pip install requests
          python signal_scanner.py
