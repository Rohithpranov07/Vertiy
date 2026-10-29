# Telegram bot (stretch)

```bash
export TELEGRAM_BOT_TOKEN=...   # from @BotFather; never commit it
make api                        # the bot only calls POST /check
python -m bot.telegram_bot
```

The bot stores nothing and imports no engine code. Long polling is used, so no public URL is needed.
