import os
import logging
import yfinance as yf
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from db import SessionLocal, User, Alert

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Request received: /start from tg_id={update.effective_user.id}")
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
    logging.info(f"Request received: /setalert from tg_id={update.effective_user.id} with args={context.args}")
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
    logging.info(f"Alert stored: tg_id={tg_id} symbol={symbol} target={price}")
    await update.message.reply_text(f"Alert set for {symbol} at ₹{price}")


async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Request received: /listalerts from tg_id={update.effective_user.id}")
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
    logging.info(f"Request received: /removealert from tg_id={update.effective_user.id} with args={context.args}")
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
        logging.info(f"Alert removed: tg_id={tg_id} symbol={symbol}")
        await update.message.reply_text(f"Removed alert for {symbol}")
    else:
        await update.message.reply_text(f"No alert found for {symbol}")


async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Job triggered: Checking alerts")
    session = SessionLocal()
    alerts = session.query(Alert).all()
    for alert in alerts:
        try:
            ticker = yf.Ticker(alert.stock_symbol + ".NS")
            hist = ticker.history(period="1d")
            if hist.empty:
                continue
            current_price = hist["Close"].iloc[-1]
            if current_price >= alert.target_price:
                user = session.query(User).filter_by(id=alert.user_id).first()
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"{alert.stock_symbol} hit ₹{current_price:.2f} (target: ₹{alert.target_price})"
                )
                logging.info(f"Alert triggered: tg_id={user.telegram_id} symbol={alert.stock_symbol} target={alert.target_price} price={current_price}")
                session.delete(alert)
                session.commit()
        except Exception as e:
            logging.error(f"Error when checking alert for {alert.stock_symbol}: {e}")
            continue
    session.close()


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setalert", set_alert))
    app.add_handler(CommandHandler("listalerts", list_alerts))
    app.add_handler(CommandHandler("removealert", remove_alert))

    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts_job, interval=60, first=10)

    print("✅ Bot started and checking prices every 60 seconds...")
    app.run_polling()
