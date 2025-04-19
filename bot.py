import logging
import sqlite3
import random
from tronpy import Tron
from tronpy.keys import PrivateKey
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

TOKEN = '7797048819:AAF80kK8PeOZdqBy8xDFora7Be_9QhYC63s'
ADMIN_USERNAME = 'xrevhaxor137'

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

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome to the Escrow Bot. Use /create_escrow to begin.")

def create_escrow(update: Update, context: CallbackContext):
    try:
        seller = update.message.from_user.username
        buyer = context.args[0].lstrip('@')
        amount = float(context.args[1])

        # Generate TRC20 wallet
        priv_key = PrivateKey.random()
        address = priv_key.public_key.to_base58check_address()

        cursor.execute("INSERT INTO escrows (seller, buyer, amount, address, private_key, status) VALUES (?, ?, ?, ?, ?, ?)",
                       (seller, buyer, amount, address, priv_key.hex(), "pending"))
        escrow_id = cursor.lastrowid
        conn.commit()

        update.message.reply_text(
            f"Escrow #{escrow_id} created:\n"
            f"Buyer: @{buyer}\n"
            f"Amount: {amount} USDT (TRC20)\n"
            f"Deposit address: `{address}`\n\n"
            f"Buyer, send USDT to the address above then run /confirm"
        )

    except Exception as e:
        update.message.reply_text(f"Error: {str(e)}")

def confirm(update: Update, context: CallbackContext):
    user = update.message.from_user.username
    cursor.execute("SELECT id FROM escrows WHERE buyer=? AND status='pending'", (user,))
    result = cursor.fetchone()
    if result:
        escrow_id = result[0]
        cursor.execute("UPDATE escrows SET status='confirmed' WHERE id=?", (escrow_id,))
        conn.commit()
        update.message.reply_text(f"Payment confirmed for escrow #{escrow_id}. Waiting for seller to /release.")
    else:
        update.message.reply_text("No pending escrow found.")

def release(update: Update, context: CallbackContext):
    user = update.message.from_user.username
    cursor.execute("SELECT id FROM escrows WHERE seller=? AND status='confirmed'", (user,))
    result = cursor.fetchone()
    if result:
        escrow_id = result[0]
        cursor.execute("UPDATE escrows SET status='released' WHERE id=?", (escrow_id,))
        conn.commit()
        update.message.reply_text(f"Funds released for escrow #{escrow_id}.")
    else:
        update.message.reply_text("No confirmed escrow found.")

def dispute(update: Update, context: CallbackContext):
    user = update.message.from_user.username
    cursor.execute("SELECT id FROM escrows WHERE (buyer=? OR seller=?) AND status='confirmed'", (user, user))
    result = cursor.fetchone()
    if result:
        escrow_id = result[0]
        cursor.execute("UPDATE escrows SET status='disputed' WHERE id=?", (escrow_id,))
        conn.commit()
        update.message.reply_text(f"Escrow #{escrow_id} is now in dispute. Admin @{ADMIN_USERNAME} has been notified.")
    else:
        update.message.reply_text("No active escrow found.")

def resolve(update: Update, context: CallbackContext):
    user = update.message.from_user.username
    if user != ADMIN_USERNAME:
        update.message.reply_text("You are not authorized.")
        return

    if len(context.args) != 2:
        update.message.reply_text("Usage: /resolve <escrow_id> released/canceled")
        return

    escrow_id, action = context.args
    if action not in ["released", "canceled"]:
        update.message.reply_text("Invalid action. Use released or canceled.")
        return

    cursor.execute("UPDATE escrows SET status=? WHERE id=?", (action, escrow_id))
    conn.commit()
    update.message.reply_text(f"Escrow #{escrow_id} has been {action}.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("create_escrow", create_escrow))
    dp.add_handler(CommandHandler("confirm", confirm))
    dp.add_handler(CommandHandler("release", release))
    dp.add_handler(CommandHandler("dispute", dispute))
    dp.add_handler(CommandHandler("resolve", resolve))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
