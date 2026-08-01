import os
import random
from threading import Thread
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
)

# =========================================================
# 1. SETUP & CONFIGURATION
# =========================================================
app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'bingo_secret_key_123'
socketio = SocketIO(app, cors_allowed_origins="*")

API_TOKEN = os.environ.get("BOT_TOKEN", "8623843462:AAG7e74RbOdQF5N4lsT2EsO8XJ0Hy5TYjkM")
bot = telebot.TeleBot(API_TOKEN)

RENDER_WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://bingo-bot-c90r.onrender.com")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "855985673"))
SUPPORT_LINK = os.environ.get("SUPPORT_LINK", "https://t.me/BkbingosupportBot")

CARD_PRICE = 10.0
COMMISSION_RATE = 0.10
MAX_CARDS_PER_PLAYER = 2

user_balances = {}

# =========================================================
# 2. BINGO CARDS DATABASE (1-104 CARDS)
# =========================================================
cards_database = {}

def generate_official_bingo_card(card_id):
    seed = int(card_id) * 997
    def get_col(min_v, max_v, count):
        nums = list(range(min_v, max_v + 1))
        nums.sort(key=lambda x: (abs(hash(str(seed + x)))))
        return sorted(nums[:count])

    b = get_col(1, 15, 5)
    i = get_col(16, 30, 5)
    n = get_col(31, 45, 4) 
    g = get_col(46, 60, 5)
    o = get_col(61, 75, 5)

    matrix = []
    for r in range(5):
        row = [
            b[r],
            i[r],
            'FREE' if r == 2 else (n[r] if r < 2 else n[r-1]),
            g[r],
            o[r]
        ]
        matrix.append(row)
    return matrix

for c_num in range(1, 105):
    cards_database[c_num] = generate_official_bingo_card(c_num)

# =========================================================
# 3. GAME STATE & WINNER CHECKER
# =========================================================
game_state = {
    "status": "WAITING",  # WAITING, COUNTDOWN, PLAYING, FINISHED
    "time_left": 15,
    "drawn_numbers": [],
    "selected_cards": {}, # card_id -> user_id
    "player_cards": {},   # user_id -> list of card_ids
    "derash": 0.0
}

def check_bingo_winner(matrix, drawn_set):
    def is_hit(val):
        return val == 'FREE' or val in drawn_set

    for row in matrix:
        if all(is_hit(v) for v in row): return True
    for col in range(5):
        if all(is_hit(matrix[row][col]) for row in range(5)): return True
    d1 = [matrix[i][i] for i in range(5)]
    d2 = [matrix[i][4-i] for i in range(5)]
    if all(is_hit(v) for v in d1) or all(is_hit(v) for v in d2): return True

    return False

# =========================================================
# 4. FLASK ROUTES & SOCKET.IO EVENTS
# =========================================================
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('get_user_balance')
def handle_get_balance(data):
    u_id = data.get('user_id')
    if u_id not in user_balances:
        user_balances[u_id] = 100.0  # መነሻ ቦነስ
    emit('balance_update', {'user_id': u_id, 'balance': user_balances[u_id]})

@socketio.on('select_card')
def handle_select_card(data):
    u_id = data.get('user_id')
    c_id = data.get('card_id')

    if game_state['status'] not in ['WAITING', 'COUNTDOWN']:
        emit('error_msg', {'msg': 'ጨዋታው ስለተጀመረ አሁን ካርቴላ መያዝ አይቻልም!'})
        return

    if c_id in game_state['selected_cards']:
        emit('error_msg', {'msg': 'ይህ ካርቴላ በሌላ ተጫዋች ተይዟል!'})
        return

    user_cards = game_state['player_cards'].get(u_id, [])
    if len(user_cards) >= MAX_CARDS_PER_PLAYER:
        emit('error_msg', {'msg': f'በአንድ ዙር ከ {MAX_CARDS_PER_PLAYER} ካርቴላ በላይ መያዝ አይቻልም!'})
        return

    current_bal = user_balances.get(u_id, 0.0)
    if current_bal < CARD_PRICE:
        emit('error_msg', {'msg': 'በቂ ሂሳብ የለዎትም! እባክዎን ዲፖዚት ያድርጉ።'})
        return

    user_balances[u_id] -= CARD_PRICE
    game_state['selected_cards'][c_id] = u_id
    if u_id not in game_state['player_cards']:
        game_state['player_cards'][u_id] = []
    game_state['player_cards'][u_id].append(c_id)

    total_sales = len(game_state['selected_cards']) * CARD_PRICE
    game_state['derash'] = total_sales * (1.0 - COMMISSION_RATE)

    emit('card_confirmed', {'card_id': c_id, 'new_balance': user_balances[u_id]})
    socketio.emit('game_update', {'selected_cards': game_state['selected_cards']})

@socketio.on('get_preview_matrix')
def handle_preview_matrix(data):
    c_id = data.get('card_id')
    if c_id in cards_database:
        emit('receive_preview_matrix', {'card_id': c_id, 'matrix': cards_database[c_id]})

@socketio.on('get_card_matrix')
def handle_card_matrix(data):
    c_id = data.get('card_id')
    if c_id in cards_database:
        emit('receive_card_matrix', {'card_id': c_id, 'matrix': cards_database[c_id]})

# =========================================================
# 5. BACKGROUND GAME ENGINE LOOP
# =========================================================
def game_engine_loop():
    while True:
        socketio.sleep(1)

        if game_state['status'] == 'WAITING':
            if len(game_state['selected_cards']) >= 1:
                game_state['status'] = 'COUNTDOWN'
                game_state['time_left'] = 15

        elif game_state['status'] == 'COUNTDOWN':
            game_state['time_left'] -= 1
            socketio.emit('timer_update', {
                'time_left': game_state['time_left'],
                'status': game_state['status']
            })

            if game_state['time_left'] <= 0:
                if len(game_state['selected_cards']) >= 1:
                    game_state['status'] = 'PLAYING'
                    game_state['drawn_numbers'] = []
                    socketio.emit('game_started', {'derash': game_state['derash']})
                else:
                    game_state['status'] = 'WAITING'
                    game_state['time_left'] = 15

        elif game_state['status'] == 'PLAYING':
            socketio.sleep(2.5)
            available = [n for n in range(1, 76) if n not in game_state['drawn_numbers']]

            if not available:
                game_state['status'] = 'FINISHED'
                continue

            num = random.choice(available)
            game_state['drawn_numbers'].append(num)
            drawn_set = set(game_state['drawn_numbers'])

            letter = 'B' if num <= 15 else 'I' if num <= 30 else 'N' if num <= 45 else 'G' if num <= 60 else 'O'
            ball_str = f"{letter}-{num}"

            socketio.emit('new_number', {
                'number': num,
                'ball': ball_str,
                'drawn_list': game_state['drawn_numbers']
            })

            winner_found = False
            for c_id, u_id in game_state['selected_cards'].items():
                matrix = cards_database[c_id]
                if check_bingo_winner(matrix, drawn_set):
                    winner_found = True
                    game_state['status'] = 'FINISHED'
                    
                    prize = game_state['derash']
                    user_balances[u_id] = user_balances.get(u_id, 0.0) + prize

                    try:
                        u_info = bot.get_chat(u_id)
                        winner_name = u_info.first_name or "Player"
                    except:
                        winner_name = f"Player ({u_id})"

                    socketio.emit('winner_announced', {
                        'winner_name': winner_name,
                        'prize': prize,
                        'card_num': c_id,
                        'card_matrix': matrix
                    })
                    break

            if winner_found:
                socketio.sleep(10)
                game_state['status'] = 'WAITING'
                game_state['time_left'] = 15
                game_state['selected_cards'] = {}
                game_state['player_cards'] = {}
                game_state['drawn_numbers'] = []
                game_state['derash'] = 0.0
                socketio.emit('reset_game')

# =========================================================
# 6. ADMIN CONTROL DASHBOARD
# =========================================================
def is_admin(user_id):
    return int(user_id) == int(ADMIN_ID)

@bot.message_handler(commands=['admin'])
def admin_dashboard(message):
    u_id = message.from_user.id
    if not is_admin(u_id):
        bot.reply_to(message, f"❌ ይኸንን ትዕዛዝ ለመጠቀም ፈቃድ የለዎትም።\nየእርስዎ ID: `{u_id}`", parse_mode="Markdown")
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
        msg = bot.send_message(
            call.message.chat.id, 
            "➕ **ሂሳብ ለመደመር፦**\n\nእባክዎን የ ተጫዋቹን User ID እና የሚደመረውን መጠን በባዶ ቦታ በመለየት ይጻፉ፦\n\n`USER_ID AMOUNT`\n\n*ምሳሌ:* `12345678 100`", 
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_add_balance)

    elif call.data == "admin_deduct_bal":
        msg = bot.send_message(
            call.message.chat.id, 
            "➖ **ሂሳብ ለመቀነስ፦**\n\nእባክዎን የ ተጫዋቹን User ID እና የሚቀነሰውን መጠን በባዶ ቦታ በመለየት ይጻፉ፦\n\n`USER_ID AMOUNT`\n\n*ምሳሌ:* `12345678 50`", 
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_deduct_balance)

    elif call.data == "admin_game_ctrl":
        markup = InlineKeyboardMarkup(row_width=1)
        btn_reset = InlineKeyboardButton("🔄 ጨዋታውን Reset አድርግ (Force Reset)", callback_data="admin_force_reset")
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
        parts = message.text.strip().split()
        target_id = int(parts[0])
        amount = float(parts[1])

        user_balances[target_id] = user_balances.get(target_id, 0.0) + amount
        socketio.emit('balance_update', {'user_id': target_id, 'balance': user_balances[target_id]})
        
        bot.reply_to(message, f"✅ ለተጠቃሚ `{target_id}` መጠን `{amount:.2f} ETB` ተደምሯል።\nአዲሱ ሂሳብ: `{user_balances[target_id]:.2f} ETB`", parse_mode="Markdown")
        try:
            bot.send_message(target_id, f"🎉 ሂሳብዎ ላይ **{amount:.2f} ETB** ተጨምሯል!\nወቅታዊ ሂሳብዎ: **{user_balances[target_id]:.2f} ETB**", parse_mode="Markdown")
        except:
            pass
    except Exception as e:
        bot.reply_to(message, "❌ ስህተት ተፈጥሯል! እባክዎን አጻጻፉን አስተካክለው እንደገና ይሞክሩ።\nምሳሌ: `12345678 100`", parse_mode="Markdown")

def process_deduct_balance(message):
    try:
        parts = message.text.strip().split()
        target_id = int(parts[0])
        amount = float(parts[1])

        current_bal = user_balances.get(target_id, 0.0)
        if current_bal < amount:
            bot.reply_to(message, f"⚠️ ተጠቃሚው በቂ ሂሳብ የለውም። ያለው ሂሳብ: `{current_bal:.2f} ETB`", parse_mode="Markdown")
            return

        user_balances[target_id] -= amount
        socketio.emit('balance_update', {'user_id': target_id, 'balance': user_balances[target_id]})
        
        bot.reply_to(message, f"✅ ከተጠቃሚ `{target_id}` መጠን `{amount:.2f} ETB` የተቀነሰ።\nቀሪ ሂሳብ: `{user_balances[target_id]:.2f} ETB`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "❌ ስህተት ተፈጥሯል! እባክዎን አጻጻፉን አስተካክለው እንደገና ይሞክሩ።\nምሳሌ: `12345678 50`", parse_mode="Markdown")

# =========================================================
# 7. TELEGRAM BOT HANDLERS
# =========================================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    u_id = message.from_user.id
    if u_id not in user_balances:
        user_balances[u_id] = 100.0

    markup = InlineKeyboardMarkup(row_width=1)
    web_app_url = f"{RENDER_WEBAPP_URL}?user_id={u_id}"
    btn_play = InlineKeyboardButton("🎮 ጨዋታውን ጀምር (Play Now)", web_app_url=WebAppInfo(url=web_app_url))
    btn_support = InlineKeyboardButton("💬 የደንበኞች አገልግሎት", url=SUPPORT_LINK)
    markup.add(btn_play, btn_support)

    welcome_txt = (
        f"👋 ሰላም {message.from_user.first_name}!\n\n"
        f"እንኳን ወደ **BKBingo Pro** በደህና መጡ! 🎰\n\n"
        f"💰 ወቅታዊ ሂሳብዎ፦ **{user_balances[u_id]:.2f} ETB**\n\n"
        f"ጨዋታውን ለመጀመር ከታች ያለውን **'ጨዋታውን ጀምር'** የሚለውን ቁልፍ ይጫኑ።"
    )
    bot.send_message(message.chat.id, welcome_txt, parse_mode="Markdown", reply_markup=markup)

def start_bot():
    bot.infinity_polling(skip_pending_callbacks=True)

# =========================================================
# 8. MAIN ENTRY POINT
# =========================================================
if __name__ == '__main__':
    Thread(target=start_bot, daemon=True).start()
    socketio.start_background_task(target=game_engine_loop)

    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
