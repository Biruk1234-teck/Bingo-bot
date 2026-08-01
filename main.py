# =========================================================
# 8. ADMIN DASHBOARD & CONTROLS
# =========================================================

def is_admin(user_id):
    return user_id == ADMIN_ID

@bot.message_handler(commands=['admin'])
def admin_dashboard(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ ይኸንን ትዕዛዝ ለመጠቀም ፈቃድ የለዎትም።")
        return

    markup = InlineKeyboardMarkup(row_width=2)
    btn_stats = InlineKeyboardButton("📊 የሲስተም ስታቲስቲክስ", callback_data="admin_stats")
    btn_add_bal = InlineKeyboardButton("➕ ሂሳብ ለመደመር", callback_data="admin_add_bal")
    btn_deduct_bal = InlineKeyboardButton("➖ ሂሳብ ለመቀነስ", callback_data="admin_deduct_bal")
    btn_game_control = InlineKeyboardButton("⚙️ የጨዋታ ቁጥጥር", callback_data="admin_game_ctrl")
    
    markup.add(btn_stats)
    markup.add(btn_add_bal, btn_deduct_bal)
    markup.add(btn_game_control)

    admin_txt = (
        "👑 **BKBINGO PRO - ADMIN DASHBOARD** 👑\n\n"
        "እንኳን ወደ አድሚን መቆጣጠሪያ ፓነል በደህና መጡ። ከታች ያሉትን አማራጮች በመጠቀም ሲስተሙን መቆጣጠር ይችላሉ።"
    )
    bot.send_message(message.chat.id, admin_txt, parse_mode="Markdown", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ ፈቃድ የለዎትም!", show_alert=True)
        return

    if call.data == "admin_stats":
        total_users = len(user_balances)
        total_balance_in_system = sum(user_balances.values())
        active_cards = len(game_state['selected_cards'])
        
        stats_txt = (
            "📊 **የሲስተም አጠቃላይ ስታቲስቲክስ**\n\n"
            f"👤 **ጠቅላላ ተጫዋቾች:** {total_users}\n"
            f"💰 **በሲስተሙ ያለ ጠቅላላ ገንዘብ:** {total_balance_in_system:.2f} ETB\n"
            f"🎯 **በአሁኑ ዙር የተያዙ ካርቴላዎች:** {active_cards}\n"
            f"🏆 **የአሁኑ ዙር ደራሽ (POT):** {game_state['derash']:.2f} ETB\n"
            f"🔄 **የጨዋታ ሁኔታ:** {game_state['status']}"
        )
        bot.send_message(call.message.chat.id, stats_txt, parse_mode="Markdown")

    elif call.data == "admin_add_bal":
        msg = bot.send_message(call.message.chat.id, "እባክዎን የቴሌግራም User ID እና የሚደመረውን መጠን በዚህ ቅርፅ ያስገቡ:\n\n`USER_ID AMOUNT`\nምሳሌ: `12345678 100`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_balance)

    elif call.data == "admin_deduct_bal":
        msg = bot.send_message(call.message.chat.id, "እባክዎን የቴሌግራም User ID እና የሚቀነሰውን መጠን በዚህ ቅርፅ ያስገቡ:\n\n`USER_ID AMOUNT`\nምሳሌ: `12345678 50`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_deduct_balance)

    elif call.data == "admin_game_ctrl":
        markup = InlineKeyboardMarkup(row_width=2)
        btn_reset = InlineKeyboardButton("🔄 ጨዋታውን Reset አድርግ", callback_data="admin_force_reset")
        markup.add(btn_reset)
        bot.send_message(call.message.chat.id, "⚙️ **የጨዋታ ቁጥጥር አማራጮች:**", parse_mode="Markdown", reply_markup=markup)

    elif call.data == "admin_force_reset":
        game_state['status'] = 'WAITING'
        game_state['time_left'] = 15
        game_state['selected_cards'] = {}
        game_state['player_cards'] = {}
        game_state['drawn_numbers'] = []
        game_state['derash'] = 0.0
        socketio.emit('reset_game')
        bot.answer_callback_query(call.id, "✅ ጨዋታው በሃይል (Force Reset) ተደርጓል!", show_alert=True)

def process_add_balance(message):
    try:
        parts = message.text.split()
        target_id = int(parts[0])
        amount = float(parts[1])

        user_balances[target_id] = user_balances.get(target_id, 0.0) + amount
        
        # በ Socket.io በኩል ለተጠቃሚው በቅጽበት ማሳወቅ
        socketio.emit('balance_update', {'user_id': target_id, 'balance': user_balances[target_id]})
        
        bot.reply_to(message, f"✅ ለተጠቃሚ `{target_id}` መጠን `{amount} ETB` ተደምሯል።\nአዲሱ ሂሳብ: `{user_balances[target_id]:.2f} ETB`", parse_mode="Markdown")
        
        # ለተጠቃሚው ማሳወቂያ መላክ
        try:
            bot.send_message(target_id, f"🎉 ሂሳብዎ ላይ **{amount:.2f} ETB** ተጨምሯል!\nወቅታዊ ሂሳብዎ: **{user_balances[target_id]:.2f} ETB**", parse_mode="Markdown")
        except:
            pass
    except Exception as e:
        bot.reply_to(message, "❌ ስህተት ተፈጥሯል! እባክዎን ቅርፁን አስተካክለው እንደገና ይሞክሩ።")

def process_deduct_balance(message):
    try:
        parts = message.text.split()
        target_id = int(parts[0])
        amount = float(parts[1])

        current_bal = user_balances.get(target_id, 0.0)
        if current_bal < amount:
            bot.reply_to(message, f"⚠️ ተጠቃሚው በቂ ሂሳብ የለውም። ያለው ሂሳብ: `{current_bal:.2f} ETB`", parse_mode="Markdown")
            return

        user_balances[target_id] -= amount
        
        socketio.emit('balance_update', {'user_id': target_id, 'balance': user_balances[target_id]})
        
        bot.reply_to(message, f"✅ ከተጠቃሚ `{target_id}` መጠን `{amount} ETB` የተቀነሰ።\nቀሪ ሂሳብ: `{user_balances[target_id]:.2f} ETB`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "❌ ስህተት ተፈጥሯል! እባክዎን ቅርፁን አስተካክለው እንደገና ይሞክሩ።")
