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
3. ဆိုလာပြားလိုအပ်ချက်
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
def send