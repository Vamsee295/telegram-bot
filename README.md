# Telegram Study Group Bot - Manual User ID Version 📚

A simple Telegram bot for study groups where member IDs are manually stored in the code. Perfect for small, stable groups (up to 30 members).

## ✨ Features

- 🆔 **Manual User ID Storage** - Simple hardcoded list in the code
- 👥 **Tag-All Command** - Mention all registered members with `/tagall`
- 🔍 **Get ID Helper** - `/getid` command to easily collect user IDs
- 🔒 **Admin-Only** - Tag commands restricted to group admins
- ☁️ **Railway Compatible** - Polling mode, ready for cloud deployment
- 🎯 **Simple & Clean** - No database, no auto-registration, just works!

## 🚀 Quick Start

### 1. Deploy the Bot

**Set Environment Variable:**
- Railway → Variables → `BOT_TOKEN` = `YOUR_TOKEN_HERE`

**Deploy:**
```bash
git add .
git commit -m "Manual user ID bot"
git push origin main
```

### 2. Collect User IDs

**Each group member should:**
1. Start a private chat with your bot
2. Send `/getid`
3. Bot replies with their user ID
4. Share their ID with you (the admin)

**Example:**
```
User sends: /getid
Bot replies:
👤 Your Information

Name: Ravi
Username: @ravi_kumar
User ID: 123456789

Share this ID with your group admin
```

### 3. Add IDs to Code

**Edit `bot.py` lines 30-36:**

```python
MEMBERS = [
    123456789,    # @umesh404
    987654321,    # @Siva_chandra_ganesh
    111222333,    # @YASHWANTMNV
    444555666,    # @m_sanjith
    777888999,    # @karthik_kl
    121314151,    # @Raghunandan9999
    # Add more IDs here...
]
```

### 4. Redeploy

```bash
git add bot.py
git commit -m "Add member IDs"
git push origin main
```

Railway will auto-deploy.

### 5. Test

In your group:
```
/tagall Test notification!
```

All members get mentioned! 🎉

## 📖 Commands

### For Everyone

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message |
| `/help` | Show command list |
| `/getid` | Get your Telegram user ID |

### For Admins Only

| Command | Description |
|---------|-------------|
| `/tagall` | Mention all members |
| `/tagall <message>` | Tag with custom message |
| `/listmembers` | Show current member count |

## 💻 Local Development

### Installation

```bash
# Clone repository
git clone <your-repo>
cd telegram-bot

# Install dependencies
pip install -r requirements.txt

# Set environment variable
export BOT_TOKEN="8309637561:AAGKtOv8Vwzj6xihTHanqH3kAhdE_ecAZy0"

# Run bot
python bot.py
```

## 🏗️ Project Structure

```
telegram-bot/
├── bot.py              # Main bot script (~180 lines)
├── requirements.txt    # python-telegram-bot==20.3
├── railway.json        # Railway config
├── .gitignore          # Git ignore
└── README.md           # This file
```

## 🔧 How It Works

### Member Storage
```python
# Simple list at top of bot.py
MEMBERS = [123456789, 987654321, ...]
```

### Tag-All Flow
```
Admin: /tagall → Check admin → Loop MEMBERS → Fetch names → Build mentions → Send
```

### Getting IDs Flow
```
User: /getid (private chat) → Bot replies with ID → User shares with admin
```

## ✅ Advantages

**vs Auto-Registration Bot:**
- ✅ No database needed
- ✅ No complex auto-registration
- ✅ Simple to understand
- ✅ You control who gets tagged
- ✅ Perfect for small groups

**vs Channel System:**
- ✅ Simpler setup
- ✅ Works in existing group
- ✅ No channel creation needed

## ⚠️ When NOT to Use

**Use Channel System instead if:**
- Group has 50+ members
- Members change frequently
- You need 100% notification guarantee (even for silent members)
- You want to notify people who never message

## 📝 Updating Members

### Add a New Member
1. New member sends `/getid` to bot
2. They share ID with you
3. Add ID to `MEMBERS` list in code
4. Commit and push
5. Railway redeploys automatically

### Remove a Member
1. Delete their ID from `MEMBERS` list
2. Commit and push
3. Done!

## 🐛 Troubleshooting

### Bot doesn't respond to /getid

**Check:**
- Bot is running (Railway logs)
- BOT_TOKEN is set correctly
- User started a private chat with bot (not group)

### /tagall says "No members added"

**Fix:**
- Add user IDs to `MEMBERS` list in bot.py
- Redeploy

### Some users not mentioned

**Possible causes:**
- User left the group
- User blocked the bot
- User ID incorrect

**Solution:**
- Use `/listmembers` to verify IDs
- Ask user to send `/getid` again

## 🔐 Security Note

⚠️ **BOT_TOKEN in Railway only!** Never commit the actual token to code. Always use environment variables.

## 📊 Capacity

- **Recommended**: 5-30 members
- **Maximum**: 40 members (Telegram mention limit)
- **Best for**: Study groups, small teams, friend groups

## 🛠️ Tech Stack

- **Language**: Python 3.12
- **Framework**: python-telegram-bot v20.3
- **Storage**: Hardcoded list (no database)
- **Hosting**: Railway
- **Mode**: Polling

## 📄 License

MIT License - Free to use and modify

---

## 🎓 Next Steps

**Right now:**
1. Deploy the bot
2. Add bot to your group (make it admin)
3. Collect IDs with `/getid`
4. Update `MEMBERS` list
5. Test `/tagall`

**Later:**
- Add new members easily
- Customize messages
- Enjoy simple notifications!

---

**Version**: 2.0 (Manual ID)
**Status**: ✅ Production-Ready
**Perfect for**: Small study groups with stable membership

Built with ❤️ for simplicity