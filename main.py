import os
import json
import pytesseract
import re
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# === Load memory and history ===
def load_data(file, default):
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump(default, f)
    with open(file, 'r') as f:
        return json.load(f)

def save_data(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

history = load_data("history.json", {})
memory = load_data("memory.json", {})

# === Core Prediction Logic ===
def get_prediction(serial):
    digits = [int(d) for d in serial if d.isdigit()]
    digit_sum = sum(digits)
    last_digit = digits[-1]

    if serial in memory:
        return memory[serial]["color"], memory[serial]["size"]

    if digit_sum % 3 == 0:
        color = "GREEN"
    elif last_digit == 0 or last_digit == 5:
        color = "VIOLET"
    else:
        color = "RED"

    size = "SMALL" if last_digit <= 4 else "BIG"
    return color, size

# === Chart Pattern Analysis ===
def analyze_chart_text(text):
    lines = text.splitlines()
    data = []
    for line in lines:
        match = re.search(r'(\\d{5,})\\D*(RED|GREEN|VIOLET)', line.upper())
        if match:
            serial = match.group(1)
            color = match.group(2)
            data.append((serial, color))

    analysis = []
    colors = [c for _, c in data[-5:]]
    if "VIOLET" in colors:
        idx = colors.index("VIOLET")
        if idx > 0 and colors[idx - 1] != "VIOLET":
            analysis.append("🟪 VIOLET follows RED or GREEN often.")
    if colors == ["RED", "GREEN", "RED", "GREEN", "RED"]:
        analysis.append("🔁 RED-GREEN alternate pattern seen.")

    if data:
        next_serial = str(int(data[-1][0]) + 1)
        color, size = get_prediction(next_serial)
        analysis.append(f"🔮 Prediction: {color}, {size} (Next Serial: {next_serial})")

    return "\n".join(analysis) if analysis else "No strong pattern found."

# === START Command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 *Welcome to Wingo Color Prediction Bot!*\n\n"
        "📸 Send a screenshot of your color chart.\n"
        "🔢 Or enter a serial number like `10775` to get prediction.\n"
        "✅ If I'm wrong, reply like: `Correct: GREEN BIG`\n\n"
        "🛡️ Works in groups, channels, and private chat."
    )

# === TEXT Handling ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_input = update.message.text.strip().upper()
    chat_id = str(update.effective_chat.id)

    # Correction Handler
    if user_input.startswith("CORRECT:"):
        parts = user_input.replace("CORRECT:", "").strip().split()
        if len(parts) >= 2 and chat_id in history:
            last_serial = history[chat_id]["last_serial"]
            memory[last_serial] = {"color": parts[0], "size": parts[1]}
            save_data("memory.json", memory)
            await update.message.reply_text(
                f"✅ Updated memory: {last_serial} → {parts[0]} {parts[1]}"
            )
        else:
            await update.message.reply_text("❌ No serial found or invalid format.")
        return

    # Serial Number Prediction
    if user_input.isdigit():
        serial = user_input
        color, size = get_prediction(serial)
        history[chat_id] = {"last_serial": serial, "color": color, "size": size}
        save_data("history.json", history)
        await update.message.reply_text(
            f"🎯 Serial: {serial}\n🎨 Color: {color}\n🔸 Size: {size}"
        )
    else:
        await update.message.reply_text("❌ Please send a valid 5-digit serial or image.")

# === PHOTO HANDLER ===
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Received image. Analyzing...")

    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    image = Image.open(BytesIO(photo_bytes))
    text = pytesseract.image_to_string(image)
    result = analyze_chart_text(text)

    await update.message.reply_text(f"📊 Analysis Complete:\n\n{result}")

# === MAIN APP ===
async def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.PRIVATE), handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
