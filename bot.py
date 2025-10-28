import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from db import SessionLocal, User, Alert
import yfinance as yf
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
scheduler = BackgroundScheduler()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    tg_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    user = session.query(User).filter_by(telegram_id=tg_id).first()
    if not user:
        user = User(telegram_id=tg_id, username=username)
        session.add(user)
        session.commit()
    session.close()
    await update.message.reply_text("Welcome! Use /setalert <symbol> <price> to set an alert.")

async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /setalert <symbol> <price>")
        return
    symbol = context.args[0].upper()
    try:
        price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid price.")
        return
    session = SessionLocal()
    tg_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=tg_id).first()
    alert = Alert(user_id=user.id, stock_symbol=symbol, target_price=price)
    session.add(alert)
    session.commit()
    session.close()
    await update.message.reply_text(f"Alert set for {symbol} at ₹{price}")

async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    tg_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=tg_id).first()
    if not user or not user.alerts:
        await update.message.reply_text("You have no active alerts.")
    else:
        text = "\n".join([f"{a.stock_symbol} → ₹{a.target_price}" for a in user.alerts])
        await update.message.reply_text(f"Your alerts:\n{text}")
    session.close()

async def remove_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removealert <symbol>")
        return
    symbol = context.args[0].upper()
    session = SessionLocal()
    tg_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=tg_id).first()
    deleted = session.query(Alert).filter_by(user_id=user.id, stock_symbol=symbol).delete()
    session.commit()
    session.close()
    if deleted:
        await update.message.reply_text(f"Removed alert for {symbol}")
    else:
        await update.message.reply_text(f"No alert found for {symbol}")

async def check_alerts(app):
    session = SessionLocal()
    alerts = session.query(Alert).all()
    for alert in alerts:
        ticker = yf.Ticker(alert.stock_symbol + ".NS")
        try:
            current_price = ticker.history(period="1d")["Close"].iloc[-1]
        except Exception:
            continue
        if current_price >= alert.target_price:
            user = session.query(User).filter_by(id=alert.user_id).first()
            await app.bot.send_message(chat_id=user.telegram_id, text=f"{alert.stock_symbol} hit ₹{current_price:.2f} (target: ₹{alert.target_price})")
            session.delete(alert)
            session.commit()
    session.close()

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setalert", set_alert))
    app.add_handler(CommandHandler("listalerts", list_alerts))
    app.add_handler(CommandHandler("removealert", remove_alert))
    scheduler.add_job(lambda: asyncio.run(check_alerts(app)), "interval", minutes=1)
    scheduler.start()
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
