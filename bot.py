import telebot
from telebot import types
import time
import os
from flask import Flask, request
import threading

# ==================== YOUR BOT TOKEN ====================
BOT_TOKEN = "8234675036:AAFIWLxSxeaT0-VGt_wUwDySCJbHS_0NTN0"
# ========================================================

bot = telebot.TeleBot(BOT_TOKEN)

# Create Flask app for port binding
app = Flask(__name__)

# Store user data temporarily
user_data = {}

# Available solar panel wattages
SOLAR_PANEL_WATTAGES = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750]

# Available battery voltages
BATTERY_VOLTAGES = [12, 12.8, 22.8, 24, 25.6, 36, 48, 51.2, 60, 72, 96, 102.4]

# Battery types
BATTERY_TYPES = ["LiFePO4", "Lead-Acid", "Gel"]

# Product catalog from the image (updated with Dyness battery)
PRODUCT_CATALOG = {
    "Trinasolar": [
        {"Type": "N-Type i-TOPCon Bifacial Dual Glass", "Model": "TSM-NEG21C.20", "Watt": "710W", "Wholesale": "420,000", "Retail": "440,000", "Warranty": "12 Years"},
        {"Type": "N-Type i-TOPCon", "Model": "TSM-NEG19R", "Watt": "620W", "Wholesale": "330,000", "Retail": "340,000", "Warranty": "12 Years"}
    ],
    "Solis": [
        {"Type": "Single Phase", "Model": "S6-EH1P6K-L-Plus", "Capacity": "6 KW", "Wholesale": "3,200,000", "Retail": "3,400,000", "Warranty": "5 Years"},
        {"Type": "Single Phase", "Model": "S6-EH1P8K-L-Plus", "Capacity": "8 KW", "Wholesale": "4,300,000", "Retail": "4,600,000", "Warranty": "5 Years"},
        {"Type": "Single Phase", "Model": "S6-EH1P12K03-NV-YD-L", "Capacity": "12 KW", "Wholesale": "6,350,000", "Retail": "6,750,000", "Warranty": "5 Years"},
        {"Type": "Three Phase", "Model": "S6-EH3P12K02-NV-YD-L", "Capacity": "12 KW", "Wholesale": "6,450,000", "Retail": "6,850,000", "Warranty": "5 Years"},
        {"Type": "Three Phase", "Model": "S6-EH3P15K02-NV-YD-L", "Capacity": "15 KW", "Wholesale": "7,300,000", "Retail": "7,700,000", "Warranty": "5 Years"}
    ],
    "Dyness": [
        {"Type": "Low Voltage Battery", "Model": "POWER BRICK", "Capacity": "51.2V, 280Ah", "Wholesale": "7,190,000", "Retail": "7,490,000", "Warranty": "5+5 Years"}
    ]
}

# Step 1: Calculate total daily energy consumption
def calculate_daily_consumption(total_w, hours):
    return total_w * hours

# Step 2: Calculate battery size based on battery type
def calculate_battery_size(daily_wh, battery_voltage, battery_type="lifepo4"):
    if battery_type.lower() == "lifepo4":
        dod_factor = 0.8
        battery_ah = (daily_wh / battery_voltage) * (1 / dod_factor)
    elif battery_type.lower() == "gel":
        dod_factor = 0.6
        battery_ah = (daily_wh / battery_voltage) * (1 / dod_factor)
    else:
        dod_factor = 0.5
        battery_ah = (daily_wh / battery_voltage) * (1 / dod_factor)
    return battery_ah, dod_factor

# Step 3: Calculate solar panel requirements
def calculate_solar_panels(daily_wh, panel_wattage, sun_hours=5, efficiency=0.85):
    solar_w = (daily_wh / sun_hours) * (1 / efficiency)
    num_panels = round(solar_w / panel_wattage)
    if num_panels < 1:
        num_panels = 1
    return solar_w, num_panels

# Step 4: Calculate inverter size
def calculate_inverter_size(total_w):
    inverter_w = total_w * 1.3
    return inverter_w

# Step 5: Calculate charge controller size
def calculate_charge_controller(solar_w, battery_voltage):
    controller_amps = (solar_w / battery_voltage) * 1.25
    if solar_w <= 1000 and battery_voltage <= 24:
        controller_type = "PWM"
    else:
        controller_type = "MPPT"
    return controller_type, controller_amps

# Function to calculate with specific products
def calculate_with_specific_products(total_w, hours):
    daily_wh = calculate_daily_consumption(total_w, hours)
    
    # Use Trinasolar 710W panel
    panel_wattage = 710
    solar_w, num_panels = calculate_solar_panels(daily_wh, panel_wattage)
    
    # Use Dyness battery (51.2V, 280Ah)
    battery_voltage = 51.2
    battery_capacity_ah = 280
    battery_wh = battery_voltage * battery_capacity_ah
    
    # Calculate how many batteries needed
    batteries_needed = max(1, round(daily_wh / (battery_wh * 0.8)))  # Using 80% DOD for LiFePO4
    
    # Calculate inverter size
    inverter_w = calculate_inverter_size(total_w)
    
    # Find suitable Solis inverter
    suitable_inverter = None
    for inverter in PRODUCT_CATALOG["Solis"]:
        capacity_kw = float(inverter["Capacity"].split()[0])
        if capacity_kw * 1000 >= inverter_w:
            suitable_inverter = inverter
            break
    
    # If no suitable inverter found, use the largest one
    if not suitable_inverter:
        suitable_inverter = PRODUCT_CATALOG["Solis"][-1]
    
    # Calculate charge controller
    controller_type, controller_amps = calculate_charge_controller(solar_w, battery_voltage)
    
    # Calculate total cost (only retail prices)
    panel_cost = num_panels * int(PRODUCT_CATALOG["Trinasolar"][0]["Retail"].replace(",", ""))
    battery_cost = batteries_needed * int(PRODUCT_CATALOG["Dyness"][0]["Retail"].replace(",", ""))
    inverter_cost = int(suitable_inverter["Retail"].replace(",", ""))
    total_cost = panel_cost + battery_cost + inverter_cost
    
    return {
        "daily_wh": daily_wh,
        "panel_wattage": panel_wattage,
        "num_panels": num_panels,
        "battery_voltage": battery_voltage,
        "battery_capacity_ah": battery_capacity_ah,
        "batteries_needed": batteries_needed,
        "inverter_w": inverter_w,
        "suitable_inverter": suitable_inverter,
        "controller_type": controller_type,
        "controller_amps": controller_amps,
        "panel_cost": panel_cost,
        "battery_cost": battery_cost,
        "inverter_cost": inverter_cost,
        "total_cost": total_cost
    }

@app.route('/')
def home():
    return "Solar Calculator Bot is running!"

# Webhook route for Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# Set webhook on startup
def set_webhook():
    # Get your Render app URL
    render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://hsuchoflask.onrender.com')
    webhook_url = f"{render_url}/webhook"
    
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        print(f"Webhook set to: {webhook_url}")
    except Exception as e:
        print(f"Error setting webhook: {e}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        welcome_text = """
☀️ *Hsu Cho Solar Calculator Bot မှ ကြိုဆိုပါတယ်!*

ဆိုလာစနစ်တွက်ချက်မှုအတွက် အဆင့် ၅ ဆင့်ဖြင့် တွက်ချက်ပေးပါမယ်:

1. စုစုပေါင်းစွမ်းအင်သုံးစွဲမှု
2. ဘက်ထရီအရွယ်အစား
3. ဆို�လာပြားလိုအပ်ချက်
4. အင်ဗာတာအရွယ်အစား
5. *Charger Controller*

🔧 *အသုံးပြုနည်း:*
/calculate - တွက်ချက်ရန်
/help - အကူအညီ
        """
        bot.reply_to(message, welcome_text, parse_mode='Markdown')
    except Exception as e:
        print("Error in start:", e)

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
📖 *အဆင့် ၅ ဆင့်ဖြင့် ဆိုလာစနစ်တွက်ချက်နည်း*

/calculate ကိုနှိပ်ပြီး စတင်တွက်ချက်ပါ။
        """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['calculate'])
def start_calculation(message):
    try:
        user_data[message.chat.id] = {}
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True, row_width=2)
        buttons = [
            types.KeyboardButton("သိပါသည်"),
            types.KeyboardButton("မသိပါ")
        ]
        markup.add(*buttons)
        
        msg = bot.reply_to(message, "🔌 *သင့်စုစုပေါင်းဝပ်အား (W) ကိုသိပါသလား?*\n\nအောက်က လေးထောင့်ခလုတ်မှနှိပ်၍ ရွေးချယ်ပါ", reply_markup=markup, parse_mode='Markdown')
        bot.register_next_step_handler(msg, handle_wattage_knowledge)
    except Exception as e:
        print("Error in calculate:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

def handle_wattage_knowledge(message):
    try:
        chat_id = message.chat.id
        response = message.text
        
        if response == "သိပါသည်":
            msg = bot.reply_to(message, "🔌 *ကျေးဇူးပြု၍ စုစုပေါင်းဝပ်အား (W) ထည့်ပါ*\n\nဥပမာ: 500", reply_markup=types.ReplyKeyboardRemove(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, ask_usage_hours)
        elif response == "မသိပါ":
            wattage_guide = """
*အဆင့် 1- သင့်စွမ်းအင်သုံးစွဲမှုကို အကဲဖြတ်ခြင်း။*

*HP to Watt Conversion:*
- 1 HP = 746 Watt
- 1.5 HP = 1119 Watt  
- 2 HP = 1492 Watt
- 3 HP = 2238 Watt
- 5 HP = 3730 Watt
- 10 HP = 7460 Watt

*ပစ္စည်းစာရင်းများကြည့်ရန်:*

🏠 *အိမ်သုံးပစ္စည်း�များ:*
- LED မီးသီး (10W): 10-15W
- ပန်ကာ (သေးငယ်သော): 50-75W
- ပန်ကာ (ကြီးမားသော): 75-100W
- တီဗီ (LED 32-inch): 30-50W
- တီဗီ (LED 55-inch): 60-100W
- ရေခဲသေတ္တာ (သေးငယ်သော): 100-150W
- ရေခဲသေတ္တာ (ပုံမှန်): 150-250W
- ရေခဲသေတ္တာ (ကြီးမားသော): 250-350W
- �မိုက်ခရိုဝေ့ဖ်: 800-1200W
- လျှပ်စစ်အိုး: 1000-1500W
- ရေနွေးအိုး: 1500-2000W
- လေအေးပေး�စက် (1 HP): 746W
- လေအေးပေးစက် (1.5 HP): 1119W
- လေအေးပေး�စက် (2 HP): 1492W
- ကြိတ်စက်: 300-500W
- အဝတ်လျှော်စက်: 500-1000W
- အဝတ်ခြောက်စက်: 1000-1500W

🏢 *ရုံးသုံးပစ္စည်း�များ:*
- ကွန်ပျူတာ (Desktop): 200-300W
- ကွန်ပျူတာ (Laptop): 50-100W
- ပရင်�တာ: 50-150W
- မော်နီတာ: 20-50W
- ပရိုဂျက်တာ: 200-300W
- ဖက်စ်�စက်: 50-100W
- ရုံးမီးသီးများ: 20-40W
- ရုံးပန်ကာများ: 75-150W

🏭 *စက်ရုံသုံးပစ္စည်း�များ:*
- ပန်ကာ (စက်ရုံ): 200-500W
- မီးသီး (စက်ရုံ): 50-100W
- ပန့်အား (သေးငယ်သော): 750-1500W
- ပန့်အား (အလတ်စား): 1500-3000W
- ပန့်အား (ကြီးမားသော): 3000-5000W
- ကွန်ပရက်ဆာ (သေးငယ်သော): 1000-2000W
- ကွန်ပရက်ဆာ (အလတ်�စား): 2000-4000W
- ကွန်ပရက်ဆာ (ကြီးမားသော): 4000-7500W
- ဂျင်�နရေတာ (အရန်သုံး): 500-2000W
- လျှပ်စစ်�ကိရိယာများ: 500-3000W
- စက်ကိရိယာများ: 1000-5000W

*တွက်ချက်�နည်း:*
*Watt (W) = Voltage (V) × Current (A)*
*စုစုပေါင်း�ဝပ်အား = ပစ္စည်း�တစ်ခုချင်းစီ၏ ဝပ်အား ပေါင်းခြင်း*

*ဥပမာ ၁ (အိမ်သုံး):*
- LED မီးသီး ၁၀ လုံး (10W) = 10 × 10W = 100W
- ပန်ကာ ၂ လုံး (75W) = 2 × 75W = 150W  
- တီဗီ ၁ လုံး (100W) = 1 × 100W = 100W
- စုစုပေါင်း = 100W + 150W + 100W = 350W

*ဥပမာ ၂ (စက်ရုံသုံး):*
- ပန်ကာ ၅ လုံး (300W) = 5 × 300W = 1500W
- မီးသီး ၂၀ လုံး (50W) = 20 × 50W = 1000W
- စက်ကိရိယာ (2000W) = 1 × 2000W = 2000W
- စုစုပေါင်း = 1500W + 1000W + 2000W = 4500W

🔌 *ကျေးဇူးပြု၍ စုစုပေါင်းဝပ်အား (W) ထည့်ပါ*\n\nဥပမာ: 1500
            """
            msg = bot.reply_to(message, wattage_guide, parse_mode='Markdown', reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(msg, ask_usage_hours)
        else:
            bot.reply_to(message, "❌ ကျေးဇူးပြု၍ 'သိပါသည်' သို့မဟုတ် 'မသိပါ' ကိုရွေးချယ်ပါ")
            
    except Exception as e:
        print("Error in handle_wattage_knowledge:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

def ask_usage_hours(message):
    try:
        chat_id = message.chat.id
        total_w = int(message.text)
        
        if total_w <= 0:
            bot.reply_to(message, "❌ ဝပ်အားသည် 0 ထက်ကြီးရပါမယ်")
            return
            
        user_data[chat_id]['total_w'] = total_w
        msg = bot.reply_to(message, f"⏰ *တစ်ရက်ကိုဘယ်နှနာရီသုံးမှာလဲ?*\n\nဥပမာ: 6", parse_mode='Markdown')
        bot.register_next_step_handler(msg, ask_product_selection)
    except ValueError:
        bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ဂဏန်းမှန်မှန်ထည့်ပါ\n\nဥပမာ: 500")
    except Exception as e:
        print("Error in ask_usage_hours:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

def ask_product_selection(message):
    try:
        chat_id = message.chat.id
        hours = float(message.text)
        
        if hours <= 0 or hours > 24:
            bot.reply_to(message, "❌ သုံးမည့်နာရီသည် 1 မှ 24 ကြား�ရှိရပါမယ်")
            return
            
        user_data[chat_id]['hours'] = hours
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True, row_width=2)
        buttons = [
            types.KeyboardButton("A To Z ပစ္စည်းသုံးမည်"),
            types.KeyboardButton("အခြားပစ္စည်းသုံးမည်")
        ]
        markup.add(*buttons)
        
        msg = bot.reply_to(message, "🔧 *ဘယ်လိုပစ္စည်းတွေသုံးမှာလဲ?*", reply_markup=markup, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_product_selection)
    except ValueError:
        bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ဂဏန်းမှန်မှန်ထည့်ပါ\n\nဥပမာ: 6")
    except Exception as e:
        print("Error in ask_product_selection:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

def process_product_selection(message):
    try:
        chat_id = message.chat.id
        selection = message.text
        
        if selection == "A To Z ပစ္စည်းသုံး�မည်":
            total_w = user_data[chat_id]['total_w']
            hours = user_data[chat_id]['hours']
            
            # Calculate with specific products
            result = calculate_with_specific_products(total_w, hours)
            
            # Format the result
            response = f"""
📊 *Hsu Cho Solar Calculator - တွက်ချက်မှုရလဒ်များ (A To Z ပစ္စည်းများဖြင့်)*

📝 *စွမ်းအင်သုံးစွဲမှုစာရင်း:*
• *စုစုပေါင်းဝပ်အား:* {total_w}W
• *နေ့စဉ်သုံး�စွဲမည့်နာရီ:* {hours}h
• *စုစုပေါင်း�စွမ်းအင်သုံးစွဲမှု:* {result['daily_wh']:.0f} Wh/ရက်

🏭 *အကြံပြုထားသော ပစ္စည်းများ:*

☀️ *ဆိုလာပြား (Trinasolar):*
   - {result['num_panels']} ချပ် × {PRODUCT_CATALOG['Trinasolar'][0]['Model']} ({PRODUCT_CATALOG['Trinasolar'][0]['Watt']})
   - စျေးနှုန်း: {result['panel_cost']:,} ကျပ်
   - အမျိုးအစား: {PRODUCT_CATALOG['Trinasolar'][0]['Type']}
   - အာမခံ: {PRODUCT_CATALOG['Trinasolar'][0]['Warranty']}

🔋 *ဘက်ထရီ (Dyness):*
   - {result['batteries_needed']} လုံး × {PRODUCT_CATALOG['Dyness'][0]['Model']} ({PRODUCT_CATALOG['Dyness'][0]['Capacity']})
   - စျေး�နှုန်း: {result['battery_cost']:,} ကျပ်
   - အမျိုးအစား: {PRODUCT_CATALOG['Dyness'][0]['Type']}
   - အာမခံ: {PRODUCT_CATALOG['Dyness'][0]['Warranty']}

⚡ *အင်ဗာတာ (Solis):*
   - 1 လုံး × {result['suitable_inverter']['Model']} ({result['suitable_inverter']['Capacity']})
   - စျေး�နှုန်း: {result['inverter_cost']:,} ကျပ်
   - အမျိုးအစား: {result['suitable_inverter']['Type']}
   - အာမခံ: {result['suitable_inverter']['Warranty']}

🎛️ *Charger Controller:*
   - {result['controller_type']} {result['controller_amps']:.1f}A အရွယ်အစား

💰 *စုစုပေါင်းကုန်ကျစရိတ်:* {result['total_cost']:,} ကျပ်

💡 *အထူးအကြံပြုချက်များ:*
   - *LiFePO4 ဘက်ထရီများသည် သက်တမ်းရှည်ပြီး စိတ်ချရမှုရှိသည်*
   - *80% Depth of Discharge အထိ အသုံးပြုနိုင်ပါသည်*
   - *ဆိုလာပြား�များ�ကို နေရောင်ကောင်းစွာရသော နေရာတွင် တပ်ဆင်ပါ*
   - *အင်ဗာတာကို �လေဝင်လေထွက်ကောင်းသော နေရာတွင် ထားရှိပါ*

📞 *အသေးစိတ်သိရှိလိုပါက ဆက်သွယ်ရန်: Hsu Cho Solar*
            """
            
            # Add "Calculate Again" button
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
            markup.add(types.KeyboardButton("🔄 ထပ်တွက်ရန်"))
            
            bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=markup)
            
        elif selection == "အခြားပစ္စည်းသုံးမည်":
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True, row_width=2)
            buttons = [types.KeyboardButton(b_type) for b_type in BATTERY_TYPES]
            markup.add(*buttons)
            
            msg = bot.reply_to(message, "🔋 *ဘက်ထရီအမျိုးအစားရွေးချယ်ပါ*", reply_markup=markup, parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_battery_type)
        else:
            bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ပေးထားသော option များထဲကရွေးချယ်ပါ")
            
    except Exception as e:
        print("Error in process_product_selection:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

def process_battery_type(message):
    try:
        chat_id = message.chat.id
        battery_type = message.text
        
        if battery_type not in BATTERY_TYPES:
            bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ပေးထားသော option များထဲကရွေးချယ်ပါ", reply_markup=types.ReplyKeyboardRemove())
            return
            
        user_data[chat_id]['battery_type'] = battery_type
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True, row_width=3)
        buttons = [types.KeyboardButton(f"{wattage}W") for wattage in SOLAR_PANEL_WATTAGES]
        markup.add(*buttons)
        
        msg = bot.reply_to(message, "☀️ *ဆိုလာပြား Wattage ရွေးချယ်ပါ*", reply_markup=markup, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_solar_panel)
    except Exception as e:
        print("Error in process_battery_type:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

def process_solar_panel(message):
    try:
        chat_id = message.chat.id
        panel_text = message.text
        
        panel_wattage = int(panel_text.replace("W", ""))
        
        if panel_wattage not in SOLAR_PANEL_WATTAGES:
            bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ပေးထားသော option များထဲကရွေးချယ်ပါ", reply_markup=types.ReplyKeyboardRemove())
            return
            
        user_data[chat_id]['panel_wattage'] = panel_wattage
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True, row_width=3)
        buttons = [types.KeyboardButton(f"{voltage}V") for voltage in BATTERY_VOLTAGES]
        markup.add(*buttons)
        
        msg = bot.reply_to(message, "⚡ *ဘက်ထရီဗို့အားရွေးချယ်ပါ*", reply_markup=markup, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_battery_voltage)
    except ValueError:
        bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ပေးထားသော option များထဲကရွေးချယ်ပါ", reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        print("Error in process_solar_panel:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

def process_battery_voltage(message):
    try:
        chat_id = message.chat.id
        voltage_text = message.text
        
        battery_voltage = float(voltage_text.replace("V", ""))
        
        if battery_voltage not in BATTERY_VOLTAGES:
            bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ပေးထားသော option များထဲကရွေးချယ်ပါ", reply_markup=types.ReplyKeyboardRemove())
            return
        
        total_w = user_data[chat_id]['total_w']
        hours = user_data[chat_id]['hours']
        panel_wattage = user_data[chat_id]['panel_wattage']
        battery_type = user_data[chat_id]['battery_type']
        
        daily_wh = calculate_daily_consumption(total_w, hours)
        battery_ah, dod_factor = calculate_battery_size(daily_wh, battery_voltage, battery_type.lower())
        solar_w, num_panels = calculate_solar_panels(daily_wh, panel_wattage)
        inverter_w = calculate_inverter_size(total_w)
        controller_type, controller_amps = calculate_charge_controller(solar_w, battery_voltage)
        
        result = f"""
📊 *Hsu Cho Solar Calculator - တွက်ချက်�မှုရလဒ်များ*

🔋 *ဘက်ထရီအမျိုးအစား:* {battery_type}
⚡ *ဘက်ထရီဗို့အား:* {battery_voltage}V
☀️ *ဆိုလာပြား:* {panel_wattage}W
        
📝 *စွမ်းအင်သုံး�စွဲမှုစာရင်း:*
• *စုစုပေါင်း�ဝပ်အား:* {total_w}W
• *နေ့စဉ်သုံး�စွဲမည့်နာရီ:* {hours}h
• *စုစုပေါင်း�စွမ်းအင်သုံးစွဲမှု:* {daily_wh:.0f} Wh/ရက်

🔋 *ဘက်ထရီအရွယ်အစား:* _{battery_ah:.0f} Ah {battery_voltage}V_
   - {battery_type} ဘက်ထရီ (DOD: {dod_factor*100:.0f}%)
   - {battery_ah:.0f}Ah ဘက်ထရီ ၁လုံး (သို့) သေးငယ်သောဘက်ထရီများကို parallel ချိတ်ဆက်အသုံးပြုနိုင်သည်

☀️ *ဆို�လာပြားလိုအပ်ချက်:* _{solar_w:.0f} W_
   - {panel_wattage}W ဆို�လာပြား {num_panels} ချပ်

⚡ *အင်ဗာတာအရွယ်အစား:* _{inverter_w:.0f} W Pure Sine Wave_
   - စုစုပေါင်း�ဝပ်အားထက် 30% ပိုကြီးသော အင်ဗာတာရွေးချယ်ထားသည်

🎛️ *Charger Controller:* _{controller_type} {controller_amps:.1f}A_
   - {controller_type} controller {controller_amps:.1f}A အရွယ်အစား

💡 *အထူးအကြံပြုချက်များ:*
"""
        
        if battery_type.lower() == "lifepo4":
            result += """
   - *LiFePO4 ဘက်ထရီများသည် သက်တမ်းရှည်ပြီး စိတ်ချရမှုရှိသည်*
   - *80% Depth of Discharge အထိ အသုံးပြုနိုင်ပါသည်*
"""
        elif battery_type.lower() == "gel":
            result += """
   - *Gel ဘက်ထရီများသည် maintenance-free ဖြစ်ပြီး အတွင်းပိုင်းဖိအားနည်းပါသည်*
   - *60% Depth of Discharge အထိ အသုံးပြုနိုင်ပါသည်*
"""
        else:
            result += """
   - *Lead-Acid ဘက်ထရီများသည် စျေးနှုန်းချိုသာပြီး ရေပြန်ဖြည့်ရန် လိုအပ်ပါသည်*
   - *50% Depth of Discharge အထိ အသုံးပြုနိုင်ပါသည်*
"""
        
        result += """
   - *ဆိုလာပြားများကို နေရောင်ကောင်းစွာရသော နေရာတွင် တပ်ဆင်ပါ*
   - *အင်ဗာတာကို လေဝင်လေထွက်ကောင်းသော နေရာတွင် ထားရှိပါ*

📞 *အသေးစိတ်သိရှိလိုပါက ဆက်သွယ်ရန်: Hsu Cho Solar*
"""
        
        # Add "Calculate Again" button
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(types.KeyboardButton("🔄 ထပ်တွက်ရန်"))
        
        bot.send_message(chat_id, result, parse_mode='Markdown', reply_markup=markup)
        
    except Exception as e:
        print("Error in process_battery_voltage:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

# Handle "Calculate Again" button
@bot.message_handler(func=lambda message: message.text == "🔄 ထပ်တွက်ရန်")
def handle_calculate_again(message):
    start_calculation(message)

if __name__ == "__main__":
    # Set webhook on startup
    set_webhook()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
