# NSFW Store Telegram Bot
# Admin bot for managing products, discounts, highlights and approving payments

import re

def extract_channel_id(link: str):
    """Extract channel ID from a t.me message link"""
    # https://t.me/c/1234567890/123  → -1001234567890
    m = re.search(r't\.me/c/(\d+)', link)
    if m:
        return int("-100" + m.group(1))
    # https://t.me/channelname/123 → we can't get numeric ID easily, return None
    return None
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# === CONFIG ===
BOT_TOKEN = "9261730531:AAE96IaRu-lu3vaBXjpC90Z2d2Lo5L9COeU"
ADMIN_ID = 5082161022  # Your Telegram user ID
FORUM_GROUP_ID = -1004305338160  # Your forum group ID
PAYPAL = "your-paypal@email.com"
# ==============

DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"products": [], "discounts": {}, "pending": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Admin sees admin menu
    if user_id == ADMIN_ID:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Product", callback_data="menu_add")],
            [InlineKeyboardButton("📋 List Products", callback_data="menu_list")],
            [InlineKeyboardButton("💰 Change Price", callback_data="menu_price")],
            [InlineKeyboardButton("📊 Adjust All Prices", callback_data="menu_priceall")],
            [InlineKeyboardButton("⭐ Toggle Highlight", callback_data="menu_highlight")],
            [InlineKeyboardButton("🏷 Create Discount", callback_data="menu_discount")],
            [InlineKeyboardButton("📥 Pending Orders", callback_data="menu_pending")]
        ])
        await update.message.reply_text("NSFW Store Admin", reply_markup=keyboard)
        return

    # Customers see the store
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🛒 Open Store", web_app={"url": "https://stalwart-kelpie-1158d5.netlify.app"})
    ]])
    await update.message.reply_text(
        "Welcome to the NSFW Store\n\nTap the button below to browse photos and videos.",
        reply_markup=keyboard
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return

    action = query.data

    if action == "menu_add":
        context.user_data["adding"] = {"step": "name"}
        await query.message.reply_text("Send the product name:")
    elif action == "menu_list":
        if not data["products"]:
            await query.message.reply_text("No products yet.")
        else:
            text = "\n".join([f"ID {p['id']}: {p['name']} - ${p['price']} {'⭐' if p.get('highlight') else ''}" for p in data["products"]])
            await query.message.reply_text(text)
    elif action == "menu_price":
        context.user_data["action"] = "price"
        await query.message.reply_text("Send: product ID and new price\nExample: 3 19.99")
    elif action == "menu_priceall":
        context.user_data["action"] = "priceall"
        await query.message.reply_text("Send the amount to add to all prices\n(use negative to lower, e.g. -5)")
    elif action == "menu_highlight":
        context.user_data["action"] = "highlight"
        await query.message.reply_text("Send the product ID to toggle highlight:")
    elif action == "menu_discount":
        context.user_data["action"] = "discount"
        await query.message.reply_text("Send: CODE percent uses\nExample: SUMMER20 20 50")
    elif action == "menu_pending":
        pending = [f"@{v['username']} (ID {k})" for k, v in data.get("pending", {}).items() if v.get("status") == "pending"]
        await query.message.reply_text("Pending:\n" + ("\n".join(pending) if pending else "None"))

async def addproduct_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    context.user_data["adding"] = {"step": "name"}
    await update.message.reply_text("Send the product name:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text

    # Adding product flow
    if "adding" in context.user_data:
        step = context.user_data["adding"]["step"]
        if step == "name":
            context.user_data["adding"]["name"] = text
            context.user_data["adding"]["step"] = "price"
            await update.message.reply_text("Price in USD (e.g. 19.99):")
        elif step == "price":
            try:
                context.user_data["adding"]["price"] = float(text)
                context.user_data["adding"]["step"] = "category"
                await update.message.reply_text("Category (ebony/latina/white/bbw/asian/vip):")
            except:
                await update.message.reply_text("Invalid price.")
        elif step == "category":
            context.user_data["adding"]["category"] = text.lower()
            context.user_data["adding"]["step"] = "type"
            await update.message.reply_text("Type (Photo or Video):")
        elif step == "type":
            context.user_data["adding"]["type"] = text
            context.user_data["adding"]["step"] = "channel"
            await update.message.reply_text("Send a link to any message in the product channel\n(e.g. https://t.me/c/1234567890/123):")
        elif step == "channel":
            channel_id = extract_channel_id(text)
            p = context.user_data["adding"]
            new_id = max([x["id"] for x in data["products"]] or [0]) + 1
            product = {
                "id": new_id, "name": p["name"], "price": p["price"],
                "category": p["category"], "type": p["type"], "desc": "",
                "image": "images/product1.jpg", "highlight": False,
                "preview": None, "channel_id": channel_id
            }
            data["products"].append(product)
            save_data(data)
            del context.user_data["adding"]
            status = f"Channel ID: {channel_id}" if channel_id else "Could not detect channel"
            await update.message.reply_text(f"Product added (ID {new_id})\n{status}")
        return

    # Other button actions
    action = context.user_data.get("action")
    if action == "price":
        try:
            pid, price = text.split()
            pid, price = int(pid), float(price)
            for p in data["products"]:
                if p["id"] == pid:
                    p["price"] = price
                    save_data(data)
                    await update.message.reply_text(f"Price updated to ${price}")
                    break
        except:
            await update.message.reply_text("Send: ID price  (e.g. 3 19.99)")
        context.user_data.pop("action", None)
    elif action == "priceall":
        try:
            amount = float(text)
            for p in data["products"]:
                p["price"] = round(p["price"] + amount, 2)
            save_data(data)
            await update.message.reply_text(f"All prices adjusted by ${amount}")
        except:
            await update.message.reply_text("Send a number (e.g. 5 or -3)")
        context.user_data.pop("action", None)
    elif action == "highlight":
        try:
            pid = int(text)
            for p in data["products"]:
                if p["id"] == pid:
                    p["highlight"] = not p.get("highlight", False)
                    save_data(data)
                    await update.message.reply_text(f"Highlight {'ON' if p['highlight'] else 'OFF'}")
                    break
        except:
            await update.message.reply_text("Send the product ID")
        context.user_data.pop("action", None)
    elif action == "discount":
        try:
            code, percent, uses = text.split()
            data["discounts"][code.upper()] = {"percent": int(percent), "usesLeft": int(uses)}
            save_data(data)
            await update.message.reply_text(f"Discount {code.upper()} created")
        except:
            await update.message.reply_text("Send: CODE percent uses  (e.g. SUMMER20 20 50)")
        context.user_data.pop("action", None)

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not data["products"]:
        await update.message.reply_text("No products yet.")
        return
    text = "\n".join([f"ID {p['id']}: {p['name']} - ${p['price']} {'⭐' if p.get('highlight') else ''}" for p in data["products"]])
    await update.message.reply_text(text)

async def change_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        pid = int(context.args[0])
        new_price = float(context.args[1])
        for p in data["products"]:
            if p["id"] == pid:
                p["price"] = new_price
                save_data(data)
                await update.message.reply_text(f"Price of {p['name']} updated to ${new_price}")
                return
        await update.message.reply_text("Product not found")
    except:
        await update.message.reply_text("Usage: /price <id> <newprice>")

async def price_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        amount = float(context.args[0])
        for p in data["products"]:
            p["price"] = round(p["price"] + amount, 2)
        save_data(data)
        await update.message.reply_text(f"All prices adjusted by ${amount}")
    except:
        await update.message.reply_text("Usage: /priceall <amount> (e.g. /priceall 5 or /priceall -3)")

async def highlight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        pid = int(context.args[0])
        for p in data["products"]:
            if p["id"] == pid:
                p["highlight"] = not p.get("highlight", False)
                save_data(data)
                await update.message.reply_text(f"Highlight {'ON' if p['highlight'] else 'OFF'} for {p['name']}")
                return
    except:
        await update.message.reply_text("Usage: /highlight <id>")

async def create_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        code = context.args[0].upper()
        percent = int(context.args[1])
        uses = int(context.args[2])
        data["discounts"][code] = {"percent": percent, "usesLeft": uses}
        save_data(data)
        await update.message.reply_text(f"Discount {code} created: {percent}% off, {uses} uses")
    except:
        await update.message.reply_text("Usage: /discount CODE 20 50")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Customer sends screenshot → create a forum topic"""
    user = update.effective_user
    if not update.message.photo:
        return

    username = user.username or f"user{user.id}"
    topic_name = f"Order - @{username}"

    try:
        # Create forum topic
        topic = await context.bot.create_forum_topic(
            chat_id=FORUM_GROUP_ID,
            name=topic_name[:128]
        )
        topic_id = topic.message_thread_id

        # Forward the screenshot into the topic
        await update.message.forward(
            chat_id=FORUM_GROUP_ID,
            message_thread_id=topic_id
        )

        # Send info + approve button in the topic
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
        ]])
        await context.bot.send_message(
            chat_id=FORUM_GROUP_ID,
            message_thread_id=topic_id,
            text=f"New order from @{username}\nUser ID: `{user.id}`\n\nCheck PayPal and approve.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

        # Save pending
        data["pending"][str(user.id)] = {
            "username": username,
            "topic_id": topic_id,
            "status": "pending"
        }
        save_data(data)

        await update.message.reply_text("Screenshot received. Waiting for approval.")
    except Exception as e:
        await context.bot.send_message(ADMIN_ID, f"Failed to create topic: {e}")
        await update.message.reply_text("Received, but topic creation failed. Admin notified.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return

    data_str = query.data
    if data_str.startswith("approve_"):
        user_id = int(data_str.split("_")[1])
        # Find which product they bought (for now we use a simple approach)
        # In a full version you store the cart with the pending order
        link = None
        for p in data["products"]:
            if p.get("channel_id"):
                try:
                    invite = await context.bot.create_chat_invite_link(
                        chat_id=p["channel_id"],
                        member_limit=1,
                        name=f"Order-{user_id}"
                    )
                    link = invite.invite_link
                    break
                except:
                    continue
        if not link:
            link = f"https://t.me/+one-time-{uuid.uuid4().hex[:10]}"

        try:
            await context.bot.send_message(
                user_id,
                f"Payment approved!\n\nYour one-time access link:\n{link}\n\nThis link works only once."
            )
            await query.edit_message_text(f"✅ Approved. Link sent to user {user_id}")
            if str(user_id) in data["pending"]:
                data["pending"][str(user_id)]["status"] = "approved"
                save_data(data)
        except Exception as e:
            await query.edit_message_text(f"Error sending link: {e}")

    elif data_str.startswith("reject_"):
        user_id = int(data_str.split("_")[1])
        await context.bot.send_message(user_id, "Your payment could not be verified. Please contact support.")
        await query.edit_message_text(f"❌ Rejected user {user_id}")
        if str(user_id) in data["pending"]:
            data["pending"][str(user_id)]["status"] = "rejected"
            save_data(data)

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        user_id = int(context.args[0])
        link = f"https://t.me/+one-time-{uuid.uuid4().hex[:8]}"
        await context.bot.send_message(user_id, f"Payment approved!\nYour one-time link:\n{link}\n\nThis link works only once.")
        await update.message.reply_text(f"Approved and link sent to {user_id}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
 
