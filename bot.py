import os
import sys
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.error import Conflict, NetworkError, TimedOut

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

#############################################
# CONFIGURATION
#############################################

# Load bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Validate BOT_TOKEN
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable is not set!")
    print("📋 Please set your bot token:")
    print("   - Railway: Add BOT_TOKEN in Variables tab")
    print("   - Local: export BOT_TOKEN='your_token_here'")
    print("\n🔗 Get your token from: https://t.me/Botfather")
    sys.exit(1)

# Database file path
DB_PATH = "study_bot.db"

# Conversation states for /deadline command
WAITING_FOR_FILE = 1

#############################################
# MANUAL MEMBER LIST
#############################################

# All study group members
MEMBERS = [
    (1387393147, "Vamsee"),    # ADMIN
    (8095569186, "Umesh"),     # ADMIN 
    (6931175630, "Chetan"),
    (6544711761, "Yashwanth"),
    (5477604530, "Karthik"),
    (6643208192, "Sanjith"),   # ADMIN
    (5801384729, "Raghunandan"),
    (103419413, "Pavan"),
]

# Admin user IDs (excluded from mentions when they use /tagall)
ADMINS = [
    1387393147,    # Vamsee
    8095569186,    # Umesh
    6643208192,    # Sanjith
]

#############################################
# DATABASE SETUP
#############################################

def init_database():
    """
    Initialize SQLite database with all required tables.
    Creates tables if they don't exist.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Members table - auto-registered users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Deadlines table - study materials posted
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deadlines (
            deadline_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Completions table - tracks who completed what
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS completions (
            deadline_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (deadline_id, user_id),
            FOREIGN KEY (deadline_id) REFERENCES deadlines(deadline_id),
            FOREIGN KEY (user_id) REFERENCES members(user_id)
        )
    """)
    
    # Schedules table - scheduled reminders
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_time TIMESTAMP NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

#############################################
# HELPER FUNCTIONS
#############################################

async def is_admin(update: Update) -> bool:
    """
    Check if the user who sent the message is an admin.
    Returns True if admin, False otherwise.
    """
    try:
        chat_member = await update.effective_chat.get_member(update.effective_user.id)
        return chat_member.status in ["administrator", "creator"]
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False

def get_member_count() -> int:
    """Get total number of registered members (DB + Hardcoded)."""
    return len(get_all_member_ids())

def get_all_member_ids() -> list:
    """Get list of all registered member user IDs (DB + Hardcoded)."""
    members_set = {}
    
    # 1. Add hardcoded members first
    for user_id, name in MEMBERS:
        members_set[user_id] = name
        
    # 2. Add/Override with DB members (might have updated names)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name FROM members")
        db_members = cursor.fetchall()
        
        for user_id, first_name in db_members:
            members_set[user_id] = first_name
            
        conn.close()
    except Exception as e:
        print(f"Error getting member IDs from DB: {e}")
        # Continue with just hardcoded members if DB fails
        
    # Convert back to list of tuples
    return list(members_set.items())

def get_deadline_count() -> int:
    """Get total number of deadlines posted."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM deadlines")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"Error getting deadline count: {e}")
        return 0

def get_latest_deadline():
    """Get the most recent deadline."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT deadline_id, title, created_at 
            FROM deadlines 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        deadline = cursor.fetchone()
        conn.close()
        return deadline
    except Exception as e:
        print(f"Error getting latest deadline: {e}")
        return None

#############################################
# AUTO-REGISTRATION SYSTEM
#############################################

async def auto_register_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Automatically register members when they send any message in the group.
    Runs silently in the background.
    """
    # Only register in groups
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    
    # Ignore bots
    if update.effective_user.is_bot:
        return
    
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "User"
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Insert or ignore (prevents duplicates)
        cursor.execute("""
            INSERT OR IGNORE INTO members (user_id, first_name)
            VALUES (?, ?)
        """, (user_id, first_name))
        
        # Update first_name if user changed it
        cursor.execute("""
            UPDATE members 
            SET first_name = ?
            WHERE user_id = ?
        """, (first_name, user_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error auto-registering member {user_id}: {e}")

#############################################
# COMMAND HANDLERS
#############################################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    await update.message.reply_text(
        "📚 *Study Group Management Bot*\n\n"
        "Welcome! This bot helps manage study materials and deadlines.\n\n"
        "Use /help to see all available commands.\n\n"
        "💡 You're automatically registered when you send any message!",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show comprehensive help message."""
    help_text = (
        "📚 *Study Group Bot Commands*\n\n"
        "🔔 /mention - Notify all registered students (admin only)\n"
        "   Example: `/mention Important announcement`\n\n"
        "📎 /deadline <title> - Post study material & track completion\n"
        "   • `/deadline Assignment 1` - Start posting a deadline\n"
        "   • `/deadline status` - View completion stats\n"
        "   • `/deadline remind` - Remind pending students\n\n"
        "⏰ /schedule YYYY-MM-DD HH:MM <message> - Schedule reminder\n"
        "   Example: `/schedule 2026-02-15 09:00 Class today!`\n"
        "   ⚠️ Time is in IST (Indian Standard Time)\n\n"
        "📊 /status - Show group statistics\n"
        "ℹ️ /help - Show this message\n\n"
        "💡 *Auto-Registration*\n"
        "All members are automatically registered when they send any message in the group!\n\n"
        "👨‍💼 *Admin Commands*\n"
        "Commands marked 'admin only' require group admin privileges."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def mention_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Mention all registered members using tg://user format.
    Admin-only command.
    """
    # Only allow in groups
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ This command only works in groups.")
        return
    
    # Admin check
    if not await is_admin(update):
        await update.message.reply_text("❌ Only admins can use /mention")
        return
    
    # Get all registered members
    members = get_all_member_ids()
    
    if not members:
        await update.message.reply_text(
            "⚠️ No members registered yet!\n\n"
            "Members are auto-registered when they send any message in the group.\n\n"
            "💡 Quick fix:\n"
            "1. Send any message (like 'hello')\n"
            "2. Run /status to verify\n"
            "3. Try /mention again"
        )
        return
    
    # Build mention list
    mention_text = ""
    failed_count = 0
    
    for user_id, first_name in members:
        try:
            # Use tg://user format for real mentions
            mention_text += f"[{first_name}](tg://user?id={user_id}) "
        except Exception as e:
            print(f"Error mentioning user {user_id}: {e}")
            failed_count += 1
    
    # Get optional custom message
    message_text = " ".join(context.args) if context.args else None
    
    # Send mention message
    if message_text:
        await update.message.reply_text(
            f"📢 *Notification*\n\n{message_text}\n\n{mention_text}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"📢 *Mention All*\n\n{mention_text}",
            parse_mode="Markdown"
        )
    
    # Delete command message for cleaner chat
    try:
        await update.message.delete()
    except Exception:
        pass
    
    if failed_count > 0:
        print(f"⚠️ Could not mention {failed_count} users")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show group statistics.
    Admin-only command.
    """
    # Admin check
    if not await is_admin(update):
        await update.message.reply_text("❌ Only admins can use /status")
        return
    
    member_count = get_member_count()
    deadline_count = get_deadline_count()
    latest = get_latest_deadline()
    
    status_text = f"📊 *Group Statistics*\n\n"
    status_text += f"👥 Total Members: *{member_count}*\n"
    status_text += f"📎 Total Deadlines: *{deadline_count}*\n"
    
    if latest:
        deadline_id, title, created_at = latest
        status_text += f"📌 Latest Deadline: *{title}*\n"
        status_text += f"   Posted: {created_at}\n"
    else:
        status_text += f"📌 Latest Deadline: *None*\n"
    
    await update.message.reply_text(status_text, parse_mode="Markdown")

#############################################
# DEADLINE COMMAND SYSTEM
#############################################

async def deadline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main /deadline command handler.
    Routes to subcommands or starts new deadline flow.
    """
    # Admin check
    if not await is_admin(update):
        await update.message.reply_text("❌ Only admins can use /deadline")
        return
    
    # Check for subcommands
    if context.args:
        subcommand = context.args[0].lower()
        
        if subcommand == "status":
            await deadline_status(update, context)
            return
        elif subcommand == "remind":
            await deadline_remind(update, context)
            return
        else:
            # Treat as deadline title
            title = " ".join(context.args)
            context.user_data["deadline_title"] = title
            await update.message.reply_text(
                f"📎 *Creating Deadline: {title}*\n\n"
                "Please send the study material file (PDF, image, document, etc.)",
                parse_mode="Markdown"
            )
            return WAITING_FOR_FILE
    else:
        await update.message.reply_text(
            "📎 *Deadline Command Usage*\n\n"
            "`/deadline <title>` - Post study material\n"
            "`/deadline status` - View completion stats\n"
            "`/deadline remind` - Remind pending students",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

async def deadline_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receive file for deadline and post it with completion button.
    """
    title = context.user_data.get("deadline_title", "Study Material")
    
    # Get the file
    file = None
    file_id = None
    
    if update.message.document:
        file = update.message.document
        file_id = file.file_id
    elif update.message.photo:
        file = update.message.photo[-1]  # Get highest resolution
        file_id = file.file_id
    elif update.message.video:
        file = update.message.video
        file_id = file.file_id
    else:
        await update.message.reply_text("⚠️ Please send a valid file (document, photo, or video)")
        return WAITING_FOR_FILE
    
    # Store deadline in database first
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # We'll update message_id after posting
        cursor.execute("""
            INSERT INTO deadlines (title, message_id, chat_id, file_id)
            VALUES (?, ?, ?, ?)
        """, (title, 0, update.effective_chat.id, file_id))
        
        deadline_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Create inline button for completion
        keyboard = [[InlineKeyboardButton("✅ Mark as Completed", callback_data=f"complete_{deadline_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Post the file with button
        caption = f"📌 *Deadline: {title}*\n\nClick button when completed."
        
        if update.message.document:
            sent_message = await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        elif update.message.photo:
            sent_message = await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        elif update.message.video:
            sent_message = await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        # Update database with message_id
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE deadlines 
            SET message_id = ?
            WHERE deadline_id = ?
        """, (sent_message.message_id, deadline_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Deadline posted successfully!")
        
        # Clean up
        context.user_data.pop("deadline_title", None)
        
        return ConversationHandler.END
        
    except Exception as e:
        print(f"Error posting deadline: {e}")
        await update.message.reply_text(f"❌ Error posting deadline: {e}")
        return ConversationHandler.END

async def completion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle completion button clicks.
    Records completion and updates message.
    """
    query = update.callback_query
    await query.answer()
    
    # Extract deadline_id from callback data
    callback_data = query.data
    deadline_id = int(callback_data.split("_")[1])
    user_id = update.effective_user.id
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if already completed
        cursor.execute("""
            SELECT * FROM completions 
            WHERE deadline_id = ? AND user_id = ?
        """, (deadline_id, user_id))
        
        if cursor.fetchone():
            await query.answer("✅ You already marked this as completed!", show_alert=True)
            conn.close()
            return
        
        # Insert completion
        cursor.execute("""
            INSERT INTO completions (deadline_id, user_id)
            VALUES (?, ?)
        """, (deadline_id, user_id))
        
        # Get completion count
        cursor.execute("""
            SELECT COUNT(*) FROM completions 
            WHERE deadline_id = ?
        """, (deadline_id,))
        completed_count = cursor.fetchone()[0]
        
        # Get total members
        total_members = get_member_count()
        
        # Get deadline title
        cursor.execute("SELECT title FROM deadlines WHERE deadline_id = ?", (deadline_id,))
        title = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        # Update message caption
        new_caption = (
            f"📌 *Deadline: {title}*\n\n"
            f"Click button when completed.\n\n"
            f"✅ Completed: *{completed_count} / {total_members}*"
        )
        
        keyboard = [[InlineKeyboardButton("✅ Mark as Completed", callback_data=f"complete_{deadline_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_caption(
                caption=new_caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception:
            pass
        
        await query.answer(f"✅ Marked as completed! ({completed_count}/{total_members})", show_alert=True)
        
    except Exception as e:
        print(f"Error recording completion: {e}")
        await query.answer("❌ Error recording completion", show_alert=True)

async def deadline_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show completion status for all deadlines."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT d.deadline_id, d.title, d.created_at,
                   COUNT(c.user_id) as completed_count
            FROM deadlines d
            LEFT JOIN completions c ON d.deadline_id = c.deadline_id
            GROUP BY d.deadline_id
            ORDER BY d.created_at DESC
        """)
        
        deadlines = cursor.fetchall()
        conn.close()
        
        if not deadlines:
            await update.message.reply_text("📎 No deadlines posted yet.")
            return
        
        total_members = get_member_count()
        status_text = "📊 *Deadline Status*\n\n"
        
        for deadline_id, title, created_at, completed_count in deadlines:
            pending_count = total_members - completed_count
            status_text += f"📌 *{title}*\n"
            status_text += f"   ✅ Completed: {completed_count}\n"
            status_text += f"   ⏳ Pending: {pending_count}\n\n"
        
        await update.message.reply_text(status_text, parse_mode="Markdown")
        
    except Exception as e:
        print(f"Error getting deadline status: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def deadline_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remind users who haven't completed the latest deadline."""
    try:
        # Get latest deadline
        latest = get_latest_deadline()
        
        if not latest:
            await update.message.reply_text("📎 No deadlines posted yet.")
            return
        
        deadline_id, title, _ = latest
        
        # Get all members
        all_members = get_all_member_ids()
        
        # Get users who completed
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id FROM completions 
            WHERE deadline_id = ?
        """, (deadline_id,))
        completed_users = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        # Build mention list for pending users
        mention_text = ""
        pending_count = 0
        
        for user_id, first_name in all_members:
            if user_id not in completed_users:
                mention_text += f"[{first_name}](tg://user?id={user_id}) "
                pending_count += 1
        
        if pending_count == 0:
            await update.message.reply_text(f"✅ Everyone has completed: *{title}*", parse_mode="Markdown")
            return
        
        # Send reminder
        await update.message.reply_text(
            f"⏰ *Reminder: {title}*\n\n"
            f"Pending students ({pending_count}):\n{mention_text}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        print(f"Error sending reminder: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def cancel_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel deadline creation."""
    context.user_data.pop("deadline_title", None)
    await update.message.reply_text("❌ Deadline creation cancelled.")
    return ConversationHandler.END

#############################################
# SCHEDULE COMMAND
#############################################

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Schedule a reminder to be sent at a specific time.
    Format: /schedule YYYY-MM-DD HH:MM Message text
    """
    # Admin check
    if not await is_admin(update):
        await update.message.reply_text("❌ Only admins can use /schedule")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "⏰ *Schedule Command Usage*\n\n"
            "`/schedule YYYY-MM-DD HH:MM <message>`\n\n"
            "*Example:*\n"
            "`/schedule 2026-02-15 09:00 Class starting soon!`\n\n"
            "⚠️ Time is in IST (Indian Standard Time)",
            parse_mode="Markdown"
        )
        return
    
    try:
        # Parse date and time
        date_str = context.args[0]
        time_str = context.args[1]
        message = " ".join(context.args[2:])
        
        datetime_str = f"{date_str} {time_str}"
        scheduled_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        
        # Check if time is in the future
        if scheduled_time <= datetime.now():
            await update.message.reply_text("⚠️ Scheduled time must be in the future!")
            return
        
        # Store in database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO schedules (run_time, message)
            VALUES (?, ?)
        """, (scheduled_time, message))
        schedule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Schedule the job
        context.job_queue.run_once(
            send_scheduled_message,
            when=scheduled_time,
            data={
                "schedule_id": schedule_id,
                "message": message,
                "chat_id": update.effective_chat.id
            },
            name=f"schedule_{schedule_id}"
        )
        
        await update.message.reply_text(
            f"✅ *Reminder Scheduled*\n\n"
            f"📅 Date: {date_str}\n"
            f"🕐 Time: {time_str} IST\n"
            f"💬 Message: {message}",
            parse_mode="Markdown"
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date/time format!\n\n"
            "Use: `YYYY-MM-DD HH:MM`\n"
            "Example: `2026-02-15 09:00`",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error scheduling reminder: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def send_scheduled_message(context: ContextTypes.DEFAULT_TYPE):
    """
    Send scheduled message and tag all members.
    Called by JobQueue at scheduled time.
    """
    job_data = context.job.data
    schedule_id = job_data["schedule_id"]
    message = job_data["message"]
    chat_id = job_data["chat_id"]
    
    try:
        # Get all members for tagging
        members = get_all_member_ids()
        mention_text = ""
        
        for user_id, first_name in members:
            mention_text += f"[{first_name}](tg://user?id={user_id}) "
        
        # Send message with mentions
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ *Scheduled Reminder*\n\n{message}\n\n{mention_text}",
            parse_mode="Markdown"
        )
        
        # Remove from database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedules WHERE schedule_id = ?", (schedule_id,))
        conn.commit()
        conn.close()
        
        print(f"✅ Scheduled message sent: {message}")
        
    except Exception as e:
        print(f"Error sending scheduled message: {e}")

async def restore_scheduled_jobs(application):
    """
    Restore scheduled jobs from database on bot restart.
    Called during bot initialization.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT schedule_id, run_time, message 
            FROM schedules 
            WHERE run_time > datetime('now')
        """)
        schedules = cursor.fetchall()
        conn.close()
        
        for schedule_id, run_time_str, message in schedules:
            run_time = datetime.strptime(run_time_str, "%Y-%m-%d %H:%M:%S")
            
            # We need chat_id, but it's not stored. This is a limitation.
            # For now, we'll skip restoration. In production, store chat_id in schedules table.
            logger.warning(f"Scheduled job found but skipped (chat_id not stored): {message}")
        
        if schedules:
            logger.warning(f"Note: {len(schedules)} scheduled jobs found but not restored (need to add chat_id to DB)")
        
    except Exception as e:
        print(f"Error restoring scheduled jobs: {e}")

#############################################
# MAIN
#############################################

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Handle specific error types
    if isinstance(context.error, Conflict):
        logger.error("⚠️ CONFLICT ERROR: Multiple bot instances running!")
        logger.error("Solution: Stop old deployments in Railway or stop local bot")
    elif isinstance(context.error, NetworkError):
        logger.warning("Network error, will retry...")
    elif isinstance(context.error, TimedOut):
        logger.warning("Request timed out, will retry...")

async def post_init(application) -> None:
    """Called after the application is initialized."""
    # Delete any existing webhook to ensure we're using polling
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook cleared, using polling mode")
    except Exception as e:
        logger.warning(f"Could not clear webhook: {e}")
    
    # Restore scheduled jobs
    await restore_scheduled_jobs(application)

def main():
    """
    Main entry point.
    """
    print("🤖 Starting Study Management Bot...")
    logger.info("Bot starting up...")
    
    # Initialize database
    init_database()
    
    # Build application
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Set post_init handler
    app.post_init = post_init
    
    # Register error handler
    app.add_error_handler(error_handler)
    
    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("mention", mention_command))
    app.add_handler(CommandHandler("tagall", mention_command))  # Alias for backward compatibility
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    
    # Deadline conversation handler
    deadline_conv = ConversationHandler(
        entry_points=[CommandHandler("deadline", deadline_command)],
        states={
            WAITING_FOR_FILE: [
                MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO, deadline_receive_file)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_deadline)]
    )
    app.add_handler(deadline_conv)
    
    # Completion button callback
    app.add_handler(CallbackQueryHandler(completion_callback, pattern=r"^complete_\d+$"))
    
    # Auto-registration handler (must be last)
    app.add_handler(MessageHandler(filters.ALL, auto_register_member))
    
    member_count = get_member_count()
    print(f"✅ Bot is running...")
    print(f"📊 Registered members: {member_count}")
    print(f"📡 Using polling mode (Railway compatible)")
    print(f"💾 Database: {DB_PATH}")
    print(f"\n⚠️ If you see 'Conflict' errors, stop other bot instances!\n")
    
    logger.info("Starting polling...")
    
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True  # Ignore old updates on restart
        )
    except Conflict:
        logger.error("\n" + "="*50)
        logger.error("⚠️ CONFLICT ERROR: Another bot instance is running!")
        logger.error("="*50)
        logger.error("\nSOLUTIONS:")
        logger.error("1. Stop old Railway deployments:")
        logger.error("   - Go to Railway dashboard")
        logger.error("   - Stop or delete old deployments")
        logger.error("\n2. If testing locally, stop the local bot")
        logger.error("\n3. Wait 1-2 minutes after stopping old instances\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
