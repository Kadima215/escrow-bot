import logging
import sqlite3
from tronpy import Tron
from tronpy.keys import PrivateKey
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler

TOKEN = '7797048819:AAF80kK8PeOZdqBy8xDFora7Be_9QhYC63s'
ADMIN_USERNAME = 'xrevhaxor137'

# Database
conn = sqlite3.connect("escrow.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS escrows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller TEXT,
    buyer TEXT,
    amount REAL,
    address TEXT,
    private_key TEXT,
    status TEXT
)
""")
conn.commit()

logging.basicConfig(level=logging.INFO)

# /start
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🤖 *Welcome to Escrow Bot!*\n\n"
        "Use /help to view available commands.",
        parse_mode=ParseMode.MARKDOWN
    )

# /help
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🛠 *Escrow Bot Help Menu*\n\n"
        "1️⃣ /create_escrow @buyer 100 – Start a deal\n"
        "2️⃣ Confirm & Release via buttons\n"
        "3️⃣ /dispute – Flag an issue\n"
        "4️⃣ /resolve [id] released/canceled – Admin only\n\n"
        "Need help? Contact @" + ADMIN_USERNAME,
        parse_mode=ParseMode.MARKDOWN
    )

# /create_escrow @buyer 100
def create_escrow(update: Update, context: CallbackContext):
    try:
        seller = update.message.from_user.username
        buyer = context.args[0].lstrip('@')
        amount = float(context.args[1])

        # Generate new TRON wallet
        priv_key = PrivateKey.random()
        address = priv_key.public_key.to_base58check_address()

        cursor.execute("INSERT INTO escrows (seller, buyer, amount, address, private_key, status) VALUES (?, ?, ?, ?, ?, ?)",
                       (seller, buyer, amount, address, priv_key.hex(), "pending"))
        escrow_id = cursor.lastrowid
        conn.commit()

        buttons = [[InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_{escrow_id}")]]
        reply_markup = InlineKeyboardMarkup(buttons)

        update.message.reply_text(
            f"✅ *New Escrow Created* (#`{escrow_id}`)\n\n"
            f"*Seller:* @{seller}\n"
            f"*Buyer:* @{buyer}\n"
            f"*Amount:* {amount} USDT (TRC20)\n"
            f"*Deposit address:*\n`{address}`\n\n"
            f"@{buyer}, please send USDT to the address above and press Confirm.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    except Exception as e:
        update.message.reply_text(f"Error: {str(e)}")

# Button: Confirm
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user = query.from_user.username

    if data.startswith("confirm_"):
        escrow_id = int(data.split("_")[1])
        cursor.execute("SELECT buyer, status FROM escrows WHERE id=?", (escrow_id,))
        result = cursor.fetchone()

        if result and result[0] == user and result[1] == "pending":
            cursor.execute("UPDATE escrows SET status='confirmed' WHERE id=?", (escrow_id,))
            conn.commit()

            buttons = [
                [InlineKeyboardButton("🟢 Release Funds", callback_data=f"release_{escrow_id}")],
                [InlineKeyboardButton("⚠️ Dispute", callback_data=f"dispute_{escrow_id}")]
            ]
            query.edit_message_text(
                f"⚠️ *Payment confirmed by @{user}*\n\n"
                f"Seller, please choose an action below.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            query.answer("Not authorized or already confirmed.")

    elif data.startswith("release_"):
        escrow_id = int(data.split("_")[1])
        cursor.execute("SELECT seller, status FROM escrows WHERE id=?", (escrow_id,))
        result = cursor.fetchone()

        if result and result[0] == user and result[1] == "confirmed":
            cursor.execute("UPDATE escrows SET status='released' WHERE id=?", (escrow_id,))
            conn.commit()
            query.edit_message_text(f"✅ *Funds released!* Escrow #{escrow_id} is complete.", parse_mode=ParseMode.MARKDOWN)
        else:
            query.answer("You can’t release this.")

    elif data.startswith("dispute_"):
        escrow_id = int(data.split("_")[1])
        cursor.execute("SELECT buyer, seller, status FROM escrows WHERE id=?", (escrow_id,))
        result = cursor.fetchone()
        if result and result[2] == "confirmed" and (user == result[0] or user == result[1]):
            cursor.execute("UPDATE escrows SET status='disputed' WHERE id=?", (escrow_id,))
            conn.commit()
            query.edit_message_text(f"🚨 *Escrow #{escrow_id} is now in dispute.*\nAdmin @{ADMIN_USERNAME} has been notified.", parse_mode=ParseMode.MARKDOWN)
        else:
            query.answer("You can't dispute this.")

# /resolve <id> released/canceled
def resolve(update: Update, context: CallbackContext):
    user = update.message.from_user.username
    if user != ADMIN_USERNAME:
        update.message.reply_text("❌ You are not authorized.")
        return

    if len(context.args) != 2:
        update.message.reply_text("Usage: /resolve <escrow_id> released/canceled")
        return

    escrow_id, action = context.args
    if action not in ["released", "canceled"]:
        update.message.reply_text("Invalid action.")
        return

    cursor.execute("UPDATE escrows SET status=? WHERE id=?", (action, escrow_id))
    conn.commit()
    update.message.reply_text(f"🔧 Escrow #{escrow_id} has been *{action}*.", parse_mode=ParseMode.MARKDOWN)

# Main
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("create_escrow", create_escrow))
    dp.add_handler(CommandHandler("resolve", resolve))
    dp.add_handler(CallbackQueryHandler(button_handler))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
