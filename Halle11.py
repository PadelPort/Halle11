import streamlit as st
import pandas as pd
from rapidfuzz import fuzz, process
from datetime import datetime, date, timedelta
import io
import gspread
from google.oauth2.service_account import Credentials
import time
import numpy as np
import plotly.graph_objects as go
from calendar import monthrange
import random
import hashlib
import re


# ========================================
# KONSTANTEN & KONFIGURATION
# ========================================

WELLPASS_WERT = 12.50
WELLPASS_QR_LINK = "https://cdn.jsdelivr.net/gh/PadelPort/PP/Wellpass.jpeg"

PRODUCT_TYPES = {
    'User booking registration': 'Reservierung',
    'Open match registration': 'Open Match',
    'Product extra - BALLS': 'Bälle',
    'Product extra - RACKET': 'Schläger',
}

MITARBEITER = {
    'Andy Schneiderhan', 'Andreas Schneiderhan', 'Tanja Schneiderhan', 'Mattia Mauta', 'Marcel Sidorov',
    'Spieler 1', 'Spieler 2', 'Spieler 3', 'Spieler 4', 'Playtomic'
}

# ✅ Diese Check-ins sind IMMER grün (Familie/Bekannte ohne Wellpass-Pflicht)
ALWAYS_GREEN_CHECKINS = {
    'marcel sidorov', 'mattia niklas mauta', 'thomas otto', 'andrea otto',
    'andreas schneiderhan', 'ludmila sidorov', 'tanja schneiderhan'
}

# 🎾 PADEL-WÖRTERBUCH FÜR EASTER EGGS
PADEL_TERMS = {
    'laden': [
        '🔄 Chiquita wird geladen...',
        '⚡ Gancho im Einsatz...',
        '🎯 Cuchilla schärft...',
        '💥 Remate kommt...',
        '🏆 Andy checkt die Stats...',
        '🎾 halle11 dreht auf...',
        '⚡ Famiglia Schneiderhan powered!'
    ],
    'verarbeite': [
        '🌍 Globo dreht sich...',
        '💫 Smashes & Specials kommen...',
        '👑 Por tres wird gezählt...',
        '🚀 Por cuatro knallt...',
        '🏃 Mattia analysiert...',
        '🎯 Marcel rechnet...',
        '⚡ Tanja organisiert...',
        '🎾 Der Berg wird gerockt!',
        '💪 halle11 Power Mode!'
    ],
    'speichere': [
        '📝 Rulo wird aufgerollt...',
        '🎭 Amago de remate aktiviert...',
        '🏐 Rebote wird gebucht...',
        '🚪 Verja geschlossen...',
        '💾 Stats im Berg gespeichert...',
        '✨ halle11 Daten sicher!',
        '🎾 Dein Spiel ist dokumentiert!',
        '👑 Andy nickt zustimmend...',
        '🏆 Noch so ein Match und du bist Top 10!'
    ],
    'fehler': [
        '❌ Salida de pista!',
        '⚠️ Aus dem Netz!',
        '🔥 Fehlerquote hoch!',
        '😅 Oops - Check-In vergessen?',
        '🤔 Andy fragt nach...',
        '📱 Wellpass-Check erforderlich!',
        '⚠️ halle11 braucht deine Signatur!'
    ],
}


# ========================================
# ✅ DYNAMISCHE CSV PARSER FUNKTIONEN
# ========================================

def parse_playtomic_csv(file_obj):
    """
    Dynamically parses Playtomic CSV files regardless of header row count.
    Automatically detects where the actual data starts by looking for key columns.
    """
    try:
        content = file_obj.read()
        file_obj.seek(0)
        
        text = None
        for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
            try:
                text = content.decode(encoding)
                break
            except:
                continue
        
        if text is None:
            st.error("❌ CSV-Encoding konnte nicht erkannt werden")
            return pd.DataFrame()
        
        lines = text.strip().split('\n')
        required_columns = ['User name', 'Product SKU', 'Service date', 'Total']
        
        header_row_idx = None
        for i, line in enumerate(lines):
            if all(col in line for col in required_columns):
                header_row_idx = i
                break
        
        if header_row_idx is None:
            st.error(f"❌ Header-Zeile nicht gefunden. Benötigte Spalten: {required_columns}")
            st.info("📋 Erste 15 Zeilen der CSV:")
            for i, line in enumerate(lines[:15]):
                st.text(f"{i}: {line[:100]}...")
            return pd.DataFrame()
        
        st.info(f"✅ Header gefunden in Zeile {header_row_idx + 1}")
        
        file_obj.seek(0)
        df = pd.read_csv(
            file_obj,
            sep=';',
            skiprows=header_row_idx,
            engine='python',
            on_bad_lines='skip',
            encoding='utf-8-sig'
        )
        
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            st.error(f"❌ Fehlende Spalten: {missing_cols}")
            return pd.DataFrame()
        
        st.success(f"✅ {len(df)} Zeilen geladen")
        return df
        
    except Exception as e:
        st.error(f"❌ CSV-Parsing Fehler: {e}")
        return pd.DataFrame()


def parse_checkins_csv(file_obj):
    """Parses Wellpass Checkins CSV files."""
    try:
        content = file_obj.read()
        file_obj.seek(0)
        
        text = None
        for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
            try:
                text = content.decode(encoding)
                break
            except:
                continue
        
        if text is None:
            st.error("❌ Checkins CSV-Encoding nicht erkannt")
            return pd.DataFrame()
        
        sample = text[:2000]
        semicolon_count = sample.count(';')
        comma_count = sample.count(',')
        delimiter = ';' if semicolon_count > comma_count else ','
        
        lines = text.strip().split('\n')
        header_row_idx = 0
        for i, line in enumerate(lines):
            if 'Nachname' in line or ('Name' in line and 'Datum' in line):
                header_row_idx = i
                break
        
        file_obj.seek(0)
        df = pd.read_csv(
            file_obj,
            sep=delimiter,
            skiprows=header_row_idx,
            engine='python',
            on_bad_lines='skip',
            encoding='utf-8-sig'
        )
        
        df.columns = df.columns.str.strip().str.replace('\ufeff', '').str.replace('"', '')
        
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'nachname' in col_lower or col_lower == 'name':
                column_mapping[col] = 'Vor- & Nachname'
            elif 'datum' in col_lower or 'date' in col_lower:
                column_mapping[col] = 'Datum'
            elif 'zeit' in col_lower or 'time' in col_lower:
                column_mapping[col] = 'Zeit'
        
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        st.success(f"✅ {len(df)} Check-ins geladen")
        return df
        
    except Exception as e:
        st.error(f"❌ Checkins CSV Fehler: {e}")
        return pd.DataFrame()


# ========================================
# HELPER FUNCTIONS
# ========================================

def get_random_padel_message(msg_type: str) -> str:
    """Return a random Padel-themed Easter Egg message."""
    messages = PADEL_TERMS.get(msg_type, ['⏳ Loading...'])
    return random.choice(messages)

def get_wellpass_wert(for_date: date) -> float:
    """Gibt den passenden Wellpass-Payout für ein Datum zurück."""
    return 12.50

def send_wellpass_whatsapp_to_player(fehler_row: pd.Series) -> bool:
    """Sendet WhatsApp-Template-Nachricht an den Spieler."""
    try:
        from twilio.rest import Client
        import json

        twilio_conf = st.secrets.get("twilio", {})
        account_sid = twilio_conf.get("account_sid")
        auth_token = twilio_conf.get("auth_token")
        from_number = twilio_conf.get("whatsapp_from")
        content_sid = twilio_conf.get("content_sid", "HXe817b0a8d139ff7fcc7e5e476989bcb9")

        if not all([account_sid, auth_token, from_number, content_sid]):
            st.error("❌ Twilio-Konfiguration unvollständig.")
            return False

        customers = loadsheet("customers")
        if customers.empty or "name" not in customers.columns:
            st.error("❌ Customers-Sheet leer oder 'name'-Spalte fehlt.")
            return False

        player_name_norm = normalize_name(fehler_row["Name"])
        match = customers[customers["name"].apply(normalize_name) == player_name_norm]

        if match.empty or "phone_number" not in match.columns or pd.isna(match.iloc[0]["phone_number"]):
            st.error(f"❌ Keine Telefonnummer für {fehler_row['Name']} gefunden.")
            return False

        raw_phone = str(match.iloc[0]["phone_number"]).strip().replace(" ", "").replace("-", "")

        if raw_phone.startswith("whatsapp:"):
            to_number = raw_phone
        else:
            e164 = raw_phone if raw_phone.startswith("+") else "+49" + raw_phone.lstrip("0")
            to_number = f"whatsapp:{e164}"

        full_name = str(fehler_row.get("Name", "")).strip()
        firstname = full_name.split()[0] if full_name else "Spieler"
        spielzeit = str(fehler_row.get("Service_Zeit", "") or "").strip() or "deiner gebuchten Zeit"

        service_date = fehler_row.get("Datum", "")
        try:
            service_date_str = pd.to_datetime(service_date).strftime("%d.%m.%Y") if service_date else ""
        except:
            service_date_str = str(service_date) if service_date else ""

        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=content_sid,
            content_variables=json.dumps({
                "1": firstname, "2": spielzeit, "3": WELLPASS_QR_LINK, "4": service_date_str,
            }),
        )

        st.success(f"✅ WhatsApp an {full_name} gesendet (SID: {msg.sid})")
        log_whatsapp_sent(fehler_row, to_number)
        return True

    except Exception as e:
        st.error(f"❌ WhatsApp-Fehler: {e}")
        return False


def send_wellpass_whatsapp_test(fehler_row: pd.Series) -> bool:
    """Sendet Test-WhatsApp an Admin-Nummer."""
    try:
        from twilio.rest import Client
        import json

        twilio_conf = st.secrets.get("twilio", {})
        account_sid = twilio_conf.get("account_sid")
        auth_token = twilio_conf.get("auth_token")
        from_number = twilio_conf.get("whatsapp_from")
        admin_phone = twilio_conf.get("whatsapp_to")
        content_sid = twilio_conf.get("content_sid", "HXe817b0a8d139ff7fcc7e5e476989bcb9")

        if not all([account_sid, auth_token, from_number, admin_phone, content_sid]):
            st.error("❌ Twilio-Konfiguration unvollständig.")
            return False

        raw_phone = str(admin_phone).strip().replace(" ", "").replace("-", "")
        if raw_phone.startswith("whatsapp:"):
            to_number = raw_phone
        else:
            e164 = raw_phone if raw_phone.startswith("+") else "+49" + raw_phone.lstrip("0")
            to_number = f"whatsapp:{e164}"

        full_name = str(fehler_row.get("Name", "")).strip()
        firstname = full_name.split()[0] if full_name else "Spieler"
        spielzeit = str(fehler_row.get("Service_Zeit", "") or "").strip() or "deiner gebuchten Zeit"

        service_date = fehler_row.get("Datum", "")
        try:
            service_date_str = pd.to_datetime(service_date).strftime("%d.%m.%Y") if service_date else ""
        except:
            service_date_str = str(service_date) if service_date else ""

        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=content_sid,
            content_variables=json.dumps({
                "1": firstname + " (TEST)", "2": spielzeit, "3": WELLPASS_QR_LINK, "4": service_date_str,
            }),
        )

        st.success(f"✅ Test-Template an Admin gesendet (SID: {msg.sid})")
        return True

    except Exception as e:
        st.error(f"❌ WhatsApp-Fehler (Test): {e}")
        return False

    
def validate_secrets():
    required = ["gcp_service_account", "google_sheets", "passwords"]
    missing = [k for k in required if k not in st.secrets]
    if missing:
        st.error(f"❌ Fehlende Secrets: {', '.join(missing)}")
        st.stop()

def normalize_name(name):
    if pd.isna(name):
        return ''
    return (str(name).strip().lower()
            .replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
            .replace('ß', 'ss').replace('-', ' ').replace('  ', ' '))

def parse_date_safe(date_val):
    """Robust date parsing that handles multiple formats."""
    if pd.isna(date_val) or date_val == '' or date_val == '-':
        return None
    
    date_str = str(date_val).strip()
    formats = [
        '%d/%m/%Y %H:%M', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d',
        '%d.%m.%Y %H:%M', '%d.%m.%Y', '%Y%m%d'
    ]
    
    for fmt in formats:
        try:
            return pd.to_datetime(date_str, format=fmt, errors='raise').date()
        except:
            continue
    
    try:
        return pd.to_datetime(date_str, dayfirst=True, errors='raise').date()
    except:
        return None

def parse_csv(f):
    """Generic CSV parser with auto-detection."""
    try:
        content = f.read()
        f.seek(0)
        
        text = None
        for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
            try:
                text = content.decode(encoding)
                break
            except:
                continue
        
        if text is None:
            return pd.DataFrame()
        
        sample = text[:2000]
        semicolon_count = sample.count(';')
        comma_count = sample.count(',')
        tab_count = sample.count('\t')
        
        if semicolon_count > comma_count and semicolon_count > tab_count:
            delimiter = ';'
        elif tab_count > comma_count and tab_count > semicolon_count:
            delimiter = '\t'
        else:
            delimiter = ','
        
        df = pd.read_csv(io.StringIO(text), sep=delimiter, engine='python', on_bad_lines='skip', encoding_errors='ignore')
        
        if len(df.columns) > 1:
            return df
    except:
        pass
    
    for sep in [None, ';', ',', '\t']:
        try:
            f.seek(0)
            df = pd.read_csv(f, sep=sep, engine='python', encoding='utf-8-sig', on_bad_lines='skip')
            if len(df.columns) > 1:
                return df
        except:
            continue
    
    return pd.DataFrame()


def color_status(val):
    """Färbt Ja grün und Nein rot."""
    if val == 'Ja':
        return 'background-color: #d4edda; color: #155724; font-weight: bold'
    elif val == 'Nein':
        return 'background-color: #f8d7da; color: #721c24; font-weight: bold'
    return ''


def optimize_dataframe(df):
    for col in df.columns:
        col_type = df[col].dtype
        if col_type == 'float64':
            df[col] = pd.to_numeric(df[col], downcast='float')
        elif col_type == 'int64':
            df[col] = pd.to_numeric(df[col], downcast='integer')
        elif col_type == 'object':
            num_unique = df[col].nunique()
            num_total = len(df[col])
            if num_unique / num_total < 0.5:
                df[col] = df[col].astype('category')
    return df


# ========================================
# AUTHENTICATION MIT COOKIES
# ========================================

def get_cookie_hash():
    if 'browser_id' not in st.session_state:
        import platform
        browser_fingerprint = f"{platform.system()}_{platform.node()}_{time.time()}"
        st.session_state.browser_id = hashlib.md5(browser_fingerprint.encode()).hexdigest()
    return st.session_state.browser_id

def save_auth_cookie():
    cookie_hash = get_cookie_hash()
    try:
        auth_data = loadsheet("auth_cookies", ['cookie_hash', 'timestamp', 'expires'])
        now = datetime.now()
        if not auth_data.empty:
            auth_data['expires'] = pd.to_datetime(auth_data['expires'], errors='coerce')
            auth_data = auth_data[auth_data['expires'] > now]
        
        expires = now + timedelta(days=30)
        new_cookie = pd.DataFrame([{'cookie_hash': cookie_hash, 'timestamp': now.isoformat(), 'expires': expires.isoformat()}])
        
        auth_data = pd.concat([auth_data, new_cookie], ignore_index=True)
        auth_data = auth_data.drop_duplicates(subset=['cookie_hash'], keep='last')
        savesheet(auth_data, "auth_cookies")
        
        st.session_state['auth_token'] = cookie_hash
        st.session_state['auth_timestamp'] = time.time()
        return True
    except:
        st.session_state['auth_token'] = cookie_hash
        st.session_state['auth_timestamp'] = time.time()
        return False

def check_auth_cookie():
    cookie_hash = get_cookie_hash()
    
    if 'auth_token' in st.session_state and st.session_state['auth_token'] == cookie_hash:
        if time.time() - st.session_state.get('auth_timestamp', 0) < 30 * 24 * 60 * 60:
            return True
    
    try:
        auth_data = loadsheet("auth_cookies", ['cookie_hash', 'expires'])
        if not auth_data.empty:
            auth_data['expires'] = pd.to_datetime(auth_data['expires'], errors='coerce')
            match = auth_data[auth_data['cookie_hash'] == cookie_hash]
            if not match.empty:
                expires = match.iloc[0]['expires']
                if pd.notna(expires) and expires > datetime.now():
                    st.session_state['auth_token'] = cookie_hash
                    st.session_state['auth_timestamp'] = time.time()
                    return True
    except:
        pass
    return False

def check_password():
    if check_auth_cookie():
        return True
    
    def entered():
        password = st.session_state.get("password", "")
        correct_password = st.secrets.get("passwords", {}).get("admin_password", "")
        
        if password and password == correct_password:
            save_auth_cookie()
            st.session_state["password_correct"] = True
            if "password" in st.session_state:
                del st.session_state["password"]
        elif password:
            st.session_state["password_correct"] = False
    
    if st.session_state.get("password_correct", False):
        return True
    
    st.markdown("<h1 style='text-align: center;'>🏔️🎾 halle11</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #666;'>🔒 Login</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input("🔑 Passwort:", type="password", on_change=entered, key="password")
        
        if st.session_state.get("password_correct") == False:
            st.error("😕 Falsches Passwort!")
        
        st.success("🍪 30 Tage eingeloggt bleiben")
        st.caption("⚡ Famiglia Schneiderhan powered")
    
    return False


# ========================================
# WHATSAPP INTEGRATION
# ========================================

def send_whatsapp_message(to_number, message_text):
    try:
        from twilio.rest import Client
        
        account_sid = st.secrets.get("twilio", {}).get("account_sid")
        auth_token = st.secrets.get("twilio", {}).get("auth_token")
        from_number = st.secrets.get("twilio", {}).get("whatsapp_from")
        
        if not all([account_sid, auth_token, from_number]):
            st.error("❌ Twilio nicht konfiguriert")
            return False
        
        client = Client(account_sid, auth_token)
        message = client.messages.create(from_=from_number, body=message_text, to=to_number)
        st.success(f"✅ WhatsApp gesendet! SID: {message.sid}")
        return True
    except Exception as e:
        st.error(f"❌ WhatsApp-Fehler: {e}")
        return False

def get_whatsapp_log_key(fehler_row):
    return f"{fehler_row['Name_norm']}_{fehler_row['Datum']}_{fehler_row['Betrag']}"

def log_whatsapp_sent(fehler_row, to_number):
    log = loadsheet("whatsapp_log", cols=['key', 'name', 'datum', 'betrag', 'to_number', 'timestamp'])
    key = get_whatsapp_log_key(fehler_row)
    
    if not log.empty and 'key' in log.columns:
        existing = log[log['key'] == key]
        if not existing.empty:
            log.loc[log['key'] == key, 'timestamp'] = datetime.now().isoformat()
            savesheet(log, "whatsapp_log")
            return
    
    new_row = pd.DataFrame([{
        'key': key, 'name': fehler_row['Name'], 'datum': fehler_row['Datum'],
        'betrag': fehler_row['Betrag'], 'to_number': to_number, 'timestamp': datetime.now().isoformat()
    }])
    log = pd.concat([log, new_row], ignore_index=True)
    savesheet(log, "whatsapp_log")

def get_whatsapp_sent_time(fehler_row):
    log = loadsheet("whatsapp_log", cols=['key', 'timestamp'])
    if log.empty or 'key' not in log.columns:
        return None
    
    key = get_whatsapp_log_key(fehler_row)
    match = log[log['key'] == key]
    
    if not match.empty:
        try:
            return datetime.fromisoformat(match.iloc[0]['timestamp'])
        except:
            return None
    return None

def send_fehler_notification_with_link(fehler_row, to_player=False):
    if to_player:
        customers = loadsheet("customers")
        if not customers.empty and 'name' in customers.columns:
            player_name_norm = normalize_name(fehler_row['Name'])
            match = customers[customers['name'].apply(normalize_name) == player_name_norm]
            
            if not match.empty and 'phone_number' in match.columns and pd.notna(match.iloc[0]['phone_number']):
                phone = str(match.iloc[0]['phone_number'])
                if not phone.startswith('+'):
                    phone = '+49' + phone.lstrip('0').replace(' ', '')
                to_number = f"whatsapp:{phone}"
            else:
                st.warning(f"❌ Keine Telefonnummer für {fehler_row['Name']}")
                return False
        else:
            st.warning("❌ Customer-Daten nicht geladen")
            return False
    else:
        to_number = st.secrets.get("twilio", {}).get("whatsapp_to")
    
    full_name = fehler_row['Name']
    first_name = full_name.split()[0] if ' ' in full_name else full_name
    service_zeit = fehler_row.get('Service_Zeit', '')
    spielinfo = f"Du hast um {service_zeit} Uhr gespielt." if service_zeit else ""

    message = f"""
🎾 Hey {first_name}!

Schön, dass du bei halle11 warst! 🏔️

{spielinfo}

Kleine Bitte:
Wir haben deinen Wellpass-Check-In noch nicht im System. Wär klasse, wenn du ihn schnell nachholen könntest!

👉 QR-Code: {WELLPASS_QR_LINK}

Danke & bis bald!
Dein halle11 Team
""".strip()

    success = send_whatsapp_message(to_number, message)
    if success:
        log_whatsapp_sent(fehler_row, to_number)
    return success


# ========================================
# CUSTOMER-DATEN
# ========================================

def get_customer_data(player_name):
    customers = loadsheet("customers")
    if customers.empty or 'name' not in customers.columns:
        return None
    
    player_name_norm = normalize_name(player_name)
    match = customers[customers['name'].apply(normalize_name) == player_name_norm]
    
    if not match.empty:
        customer = match.iloc[0]
        return {
            'phone_number': customer.get('phone_number', 'N/A'),
            'email': customer.get('email', 'N/A'),
            'category': customer.get('category_name', 'N/A')
        }
    return None


# ========================================
# GOOGLE SHEETS
# ========================================

@st.cache_resource
def get_gsheet_client():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client.open_by_key(st.secrets["google_sheets"]["sheet_id"])
    except Exception as e:
        st.error(f"❌ Google Sheets Fehler: {e}")
        return None

@st.cache_data(ttl=600, show_spinner=False)  # 10 min cache to reduce API calls
def loadsheet(name, cols=None):
    try:
        sheet = get_gsheet_client()
        if not sheet:
            return pd.DataFrame(columns=cols) if cols else pd.DataFrame()
        
        try:
            data = sheet.worksheet(name).get_all_records()
            df = pd.DataFrame(data) if data else pd.DataFrame(columns=cols) if cols else pd.DataFrame()
        except gspread.exceptions.WorksheetNotFound:
            sheet.add_worksheet(title=name, rows=1000, cols=20)
            return pd.DataFrame(columns=cols) if cols else pd.DataFrame()
        
        if not df.empty:
            df = optimize_dataframe(df)
        return df
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ Rate Limit - warte 10s...")
            time.sleep(10)
            loadsheet.clear()
            return loadsheet(name, cols)
        return pd.DataFrame(columns=cols) if cols else pd.DataFrame()

def save_sheet_with_retry(df, name, max_retries=3):
    for attempt in range(max_retries):
        try:
            sheet = get_gsheet_client()
            if not sheet:
                return False
            
            try:
                ws = sheet.worksheet(name)
            except gspread.exceptions.WorksheetNotFound:
                ws = sheet.add_worksheet(title=name, rows=1000, cols=20)
            
            ws.clear()
            time.sleep(0.5)
            
            if not df.empty:
                df_copy = df.copy()
                for col in df_copy.columns:
                    if df_copy[col].dtype == 'object' or str(df_copy[col].dtype) == 'category':
                        df_copy[col] = df_copy[col].astype(str).str.replace(',', '.', regex=False)
                    elif df_copy[col].dtype in ['float64', 'float32', 'int64', 'int32']:
                        df_copy[col] = df_copy[col].apply(lambda x: str(x).replace(',', '.') if pd.notna(x) else '')
                
                df_clean = df_copy.fillna('').replace([np.inf, -np.inf], '')
                batch_data = [df_clean.columns.tolist()] + df_clean.values.tolist()
                ws.update(batch_data, value_input_option='RAW')
            
            loadsheet.clear()
            return True
            
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                st.warning(f"⚠️ Rate Limit - {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                st.error(f"❌ Fehler: {e}")
                return False
    return False

def savesheet(df, name):
    return save_sheet_with_retry(df, name)

def save_playtomic_raw(df):
    try:
        existing = loadsheet("playtomic_raw")
        
        if not existing.empty and 'Payment id' in existing.columns and 'Payment id' in df.columns:
            def make_key(d):
                payment_id = d.get('Payment id', '')
                club_id = d.get('Club payment id', '')
                return f"{payment_id}|{club_id}" if payment_id else f"CLUB-{club_id}"
            
            existing['_key'] = existing.apply(make_key, axis=1)
            df['_key'] = df.apply(make_key, axis=1)
            
            existing_keys = set(existing['_key'].dropna())
            df_new = df[~df['_key'].isin(existing_keys)].copy()
            df_new = df_new.drop('_key', axis=1)
            
            if not df_new.empty:
                existing = existing.drop('_key', axis=1)
                df_combined = pd.concat([existing, df_new], ignore_index=True)
                savesheet(df_combined, "playtomic_raw")
                st.success(f"✅ {len(df_new)} neue Einträge!")
                return True
            else:
                st.info("ℹ️ Keine neuen Daten")
                return False
        else:
            savesheet(df, "playtomic_raw")
            st.success(f"✅ {len(df)} Einträge!")
            return True
            
    except Exception as e:
        st.error(f"❌ Fehler: {e}")
        return False


def get_corrections_cached():
    """
    Lädt Corrections mit Session-Cache um Rate Limits zu reduzieren.
    Cache wird alle 60 Sekunden aktualisiert oder bei Änderungen invalidiert.
    """
    current_time = time.time()
    cache_age = current_time - st.session_state.get('corrections_cache_time', 0)
    
    # Cache ist 60 Sekunden gültig
    if st.session_state.get('corrections_cache') is not None and cache_age < 60:
        return st.session_state.corrections_cache
    
    # Neu laden
    corr = loadsheet("corrections", ['key', 'date', 'behoben', 'timestamp'])
    st.session_state.corrections_cache = corr
    st.session_state.corrections_cache_time = current_time
    return corr


def invalidate_corrections_cache():
    """Invalidiert den Corrections-Cache nach Änderungen."""
    st.session_state.corrections_cache = None
    st.session_state.corrections_cache_time = 0


# ========================================
# REVENUE-FUNKTION MIT TENNIS/PADEL SPLIT
# ========================================

def get_revenue_from_raw(date_str=None, start_date=None, end_date=None):
    """Berechnet Umsätze aus Raw-Daten mit Tennis/Padel Unterscheidung."""
    raw_data = loadsheet("playtomic_raw")
    
    if raw_data.empty:
        return {'gesamt': 0, 'padel': 0, 'tennis': 0, 'reservierung': 0, 'baelle': 0, 'schlaeger': 0, 'sonstige': 0}
    
    raw_data['Service_date_clean'] = raw_data['Service date'].apply(parse_date_safe)
    raw_data = raw_data.dropna(subset=['Service_date_clean'])
    
    if date_str:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        filtered = raw_data[raw_data['Service_date_clean'] == date_obj]
    elif start_date and end_date:
        filtered = raw_data[(raw_data['Service_date_clean'] >= start_date) & (raw_data['Service_date_clean'] <= end_date)]
    else:
        filtered = raw_data
    
    def parse_total(total):
        if pd.isna(total):
            return 0
        total_str = str(total).replace(',', '.').replace('€', '').replace(' ', '').strip()
        try:
            return float(total_str)
        except:
            return 0
    
    filtered['Total_clean'] = filtered['Total'].apply(parse_total)
    gesamt = filtered['Total_clean'].sum()
    
    revenue = {'gesamt': gesamt, 'padel': 0, 'tennis': 0, 'reservierung': 0, 'baelle': 0, 'schlaeger': 0, 'sonstige': 0}
    
    if 'Sport' in filtered.columns:
        padel_data = filtered[filtered['Sport'].str.upper() == 'PADEL']
        tennis_data = filtered[filtered['Sport'].str.upper() == 'TENNIS']
        revenue['padel'] = padel_data['Total_clean'].sum()
        revenue['tennis'] = tennis_data['Total_clean'].sum()
    
    if 'Product SKU' in filtered.columns:
        for product in filtered['Product SKU'].unique():
            if pd.isna(product):
                continue
            product_revenue = filtered[filtered['Product SKU'] == product]['Total_clean'].sum()
            if 'User booking' in str(product) or 'Open match' in str(product):
                revenue['reservierung'] += product_revenue
            elif 'BALLS' in str(product):
                revenue['baelle'] += product_revenue
            elif 'RACKET' in str(product):
                revenue['schlaeger'] += product_revenue
            else:
                revenue['sonstige'] += product_revenue
    
    return revenue

def get_unique_wellpass_checkins(date_str):
    checkins = loadsheet("checkins")
    if checkins.empty or 'analysis_date' not in checkins.columns:
        return 0
    day_checkins = checkins[checkins['analysis_date'] == date_str]
    return day_checkins['Name_norm'].nunique() if not day_checkins.empty else 0

def get_dates():
    buchungen = loadsheet("buchungen", ['analysis_date'])
    if buchungen.empty or 'analysis_date' not in buchungen.columns:
        return []
    dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in buchungen['analysis_date'].unique()]
    return sorted(dates, reverse=True)

def load_snapshot(date_str):
    buchungen = loadsheet("buchungen", ['analysis_date'])
    if buchungen.empty or 'analysis_date' not in buchungen.columns:
        return None
    data = buchungen[buchungen['analysis_date'] == date_str]
    return data if not data.empty else None

def load_checkins_snapshot(date_str):
    checkins = loadsheet("checkins", ['analysis_date'])
    if checkins.empty or 'analysis_date' not in checkins.columns:
        return None
    data = checkins[checkins['analysis_date'] == date_str]
    return data if not data.empty else None


# ========================================
# NAME-MATCHING FUNKTIONEN
# ========================================

def load_name_mapping():
    try:
        df = loadsheet("name_mapping")
        if not df.empty and 'buchung_name' in df.columns and 'checkin_name' in df.columns:
            mapping = {}
            for _, row in df.iterrows():
                mapping[row['buchung_name']] = {
                    'checkin_name': row['checkin_name'],
                    'confidence': row.get('confidence', 100),
                    'timestamp': row.get('timestamp', ''),
                    'confirmed_by': row.get('confirmed_by', 'auto')
                }
            return mapping
        return {}
    except:
        return {}

def save_name_mapping(mapping):
    data = []
    for buchung_name, details in mapping.items():
        if isinstance(details, dict):
            data.append({
                'buchung_name': buchung_name,
                'checkin_name': details['checkin_name'],
                'confidence': details.get('confidence', 100),
                'timestamp': details.get('timestamp', datetime.now().isoformat()),
                'confirmed_by': details.get('confirmed_by', 'auto')
            })
        else:
            data.append({
                'buchung_name': buchung_name, 'checkin_name': details, 'confidence': 100,
                'timestamp': datetime.now().isoformat(), 'confirmed_by': 'legacy'
            })
    savesheet(pd.DataFrame(data), "name_mapping")

def load_rejected_matches():
    try:
        df = loadsheet("rejected_matches")
        if not df.empty:
            return set(tuple(row) for row in df[['buchung_name', 'checkin_name']].values)
        return set()
    except:
        return set()

def save_rejected_match(buchung_name, checkin_name):
    df = loadsheet("rejected_matches", cols=['buchung_name', 'checkin_name', 'timestamp'])
    new_row = pd.DataFrame([{'buchung_name': buchung_name, 'checkin_name': checkin_name, 'timestamp': datetime.now().isoformat()}])
    df = pd.concat([df, new_row], ignore_index=True)
    savesheet(df, "rejected_matches")

def remove_rejected_match(buchung_name, checkin_name):
    df = loadsheet("rejected_matches", cols=['buchung_name', 'checkin_name', 'timestamp'])
    if not df.empty:
        df = df[~((df['buchung_name'] == buchung_name) & (df['checkin_name'] == checkin_name))]
        savesheet(df, "rejected_matches")

def check_initials_match(name1, name2):
    def get_initials(name):
        parts = name.split()
        return ''.join([p[0].lower() for p in parts if p])
    init1 = get_initials(name1)
    init2 = get_initials(name2)
    return init1 in init2 or init2 in init1 or init1 == init2

def phonetic_similarity(name1, name2):
    def simplify_phonetic(name):
        if not name:
            return ""
        simplified = name[0].lower()
        for char in name[1:].lower():
            if char not in 'aeiouäöü':
                simplified += char
        for old, new in {'z': 's', 'c': 'k', 'v': 'f', 'w': 'v', 'ph': 'f', 'dt': 't', 'th': 't'}.items():
            simplified = simplified.replace(old, new)
        return simplified
    return fuzz.ratio(simplify_phonetic(name1), simplify_phonetic(name2))

def advanced_fuzzy_match(query_name, candidate_names, mapping, rejected_matches, already_matched_checkins=None):
    if not candidate_names:
        return []
    
    if already_matched_checkins is None:
        already_matched_checkins = set()
    
    available_candidates = [c for c in candidate_names if c not in already_matched_checkins]
    if not available_candidates:
        return []
    
    if query_name in mapping:
        learned = mapping[query_name]
        learned_name = learned['checkin_name'] if isinstance(learned, dict) else learned
        if learned_name in available_candidates:
            return [(learned_name, 100, 'learned')]
    
    results = []
    for candidate in available_candidates:
        if (query_name, candidate) in rejected_matches:
            continue
        
        token_score = fuzz.token_set_ratio(query_name, candidate)
        partial_score = fuzz.partial_ratio(query_name, candidate)
        initials_bonus = 20 if check_initials_match(query_name, candidate) else 0
        phonetic_score = phonetic_similarity(query_name, candidate)
        
        final_score = token_score * 0.5 + partial_score * 0.2 + phonetic_score * 0.2 + initials_bonus
        
        if final_score > 50:
            results.append((candidate, round(final_score, 1), 'fuzzy'))
    
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:5]

def render_name_matching_interface(fehler_row, ci_df, mapping, rejected_matches, all_fehler):
    name = fehler_row['Name_norm']
    key_base = f"{fehler_row['Name_norm']}_{fehler_row['Datum']}_{fehler_row['Betrag']}"
    
    checkin_names = list(ci_df['Name_norm']) if ci_df is not None and not ci_df.empty else []
    
    already_matched = set()
    for _, other_fehler in all_fehler.iterrows():
        if other_fehler['Name_norm'] == name:
            continue
        other_name = other_fehler['Name_norm']
        if other_name in mapping:
            mapped = mapping[other_name]
            mapped_name = mapped['checkin_name'] if isinstance(mapped, dict) else mapped
            already_matched.add(mapped_name)
    
    matches = advanced_fuzzy_match(name, checkin_names, mapping, rejected_matches, already_matched)
    
    # Show suggestions if any
    if matches:
        st.markdown("##### 🔍 Vorschläge")
        for i, (match_name, score, match_type) in enumerate(matches):
            original_match = ci_df[ci_df['Name_norm'] == match_name].iloc[0]['Name']
            confidence = "✅" if match_type == 'learned' else ("🟢" if score >= 90 else ("🟡" if score >= 75 else "🔴"))
            
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.caption(f"{confidence} {original_match} ({score}%)")
            with col2:
                if st.button("✅", key=f"confirm_{key_base}_{i}", use_container_width=True):
                    mapping[name] = {'checkin_name': match_name, 'confidence': score, 'timestamp': datetime.now().isoformat(), 'confirmed_by': 'user'}
                    save_name_mapping(mapping)
                    if (name, match_name) in rejected_matches:
                        remove_rejected_match(name, match_name)
                    corr = loadsheet("corrections", ['key','date','behoben','timestamp'])
                    key = f"{fehler_row['Name_norm']}_{fehler_row['Datum']}_{fehler_row['Betrag']}"
                    if not corr.empty and 'key' in corr.columns:
                        corr = corr[corr['key'] != key]
                    corr = pd.concat([corr, pd.DataFrame([{'key': key, 'date': fehler_row['Datum'], 'behoben': True, 'timestamp': datetime.now().isoformat()}])], ignore_index=True)
                    savesheet(corr, "corrections")
                    st.rerun()
            with col3:
                if st.button("❌", key=f"reject_{key_base}_{i}", use_container_width=True):
                    save_rejected_match(name, match_name)
                    st.rerun()
    else:
        st.info("💡 Keine automatischen Vorschläge gefunden")
    
    # ✅ MANUELLES MATCHING - IMMER ANZEIGEN
    st.markdown("##### ✏️ Manuell zuordnen")
    if checkin_names:
        # Build dropdown options with original names
        dropdown_options = [''] + [ci_df[ci_df['Name_norm'] == n].iloc[0]['Name'] for n in checkin_names if n not in already_matched]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            manual_match = st.selectbox(
                "Check-in Name auswählen:", 
                options=dropdown_options, 
                key=f"manual_{key_base}", 
                label_visibility="collapsed",
                help="Wähle den passenden Namen aus der Check-in Liste"
            )
        with col2:
            if st.button("💾 Speichern", key=f"save_manual_{key_base}", disabled=not manual_match, use_container_width=True):
                if manual_match:
                    manual_norm = ci_df[ci_df['Name'] == manual_match].iloc[0]['Name_norm']
                    mapping[name] = {'checkin_name': manual_norm, 'confidence': 100, 'timestamp': datetime.now().isoformat(), 'confirmed_by': 'manual'}
                    save_name_mapping(mapping)
                    corr = loadsheet("corrections", ['key','date','behoben','timestamp'])
                    key = f"{fehler_row['Name_norm']}_{fehler_row['Datum']}_{fehler_row['Betrag']}"
                    if not corr.empty and 'key' in corr.columns:
                        corr = corr[corr['key'] != key]
                    corr = pd.concat([corr, pd.DataFrame([{'key': key, 'date': fehler_row['Datum'], 'behoben': True, 'timestamp': datetime.now().isoformat()}])], ignore_index=True)
                    savesheet(corr, "corrections")
                    st.success("✅ Manuell gematcht!")
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.caption("Keine Check-ins vorhanden")

def render_learned_matches_manager():
    mapping = load_name_mapping()
    rejected = load_rejected_matches()
    
    with st.expander(f"🧠 Gelernte Matches ({len(mapping)} ✅, {len(rejected)} ❌)", expanded=False):
        if not mapping and not rejected:
            st.info("Noch keine")
            return
        
        tab_learned, tab_rejected = st.tabs(["✅ Bestätigt", "❌ Abgelehnt"])
        
        with tab_learned:
            if mapping:
                for buchung_name, details in mapping.items():
                    checkin_name = details['checkin_name'] if isinstance(details, dict) else details
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.caption(f"{buchung_name} → {checkin_name}")
                    with col2:
                        if st.button("🗑️", key=f"del_{buchung_name}"):
                            del mapping[buchung_name]
                            save_name_mapping(mapping)
                            st.rerun()
        
        with tab_rejected:
            if rejected:
                for buchung_name, checkin_name in list(rejected):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.caption(f"{buchung_name} ≠ {checkin_name}")
                    with col2:
                        if st.button("↩️", key=f"restore_{buchung_name}_{checkin_name}"):
                            remove_rejected_match(buchung_name, checkin_name)
                            st.rerun()


# ========================================
# MAIN APP
# ========================================

st.set_page_config(page_title="halle11", layout="wide", page_icon="🎾")

st.markdown("""
<style>
    .stExpander { margin-bottom: 0.5rem !important; }
    .stExpander > div { padding: 0.5rem !important; }
</style>
""", unsafe_allow_html=True)

# ✅ KEEP-ALIVE: Verhindert dass die App einschläft (alle 5 Minuten ein Ping)
st.markdown("""
<script>
    // Keep-alive ping every 5 minutes to prevent Streamlit Cloud from sleeping
    setInterval(function() {
        // Trigger a tiny interaction to keep the connection alive
        const event = new Event('mousemove');
        document.dispatchEvent(event);
        console.log('🎾 halle11 keep-alive ping');
    }, 300000); // 5 minutes = 300000ms
</script>
""", unsafe_allow_html=True)

validate_secrets()

if not check_password():
    st.stop()

if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'current_date' not in st.session_state:
    st.session_state.current_date = date.today().strftime("%Y-%m-%d")
if 'df_all' not in st.session_state:
    st.session_state.df_all = pd.DataFrame()
if 'checkins_all' not in st.session_state:
    st.session_state.checkins_all = pd.DataFrame()
if 'day_idx' not in st.session_state:
    st.session_state.day_idx = 0
# ✅ Session-Cache für weniger API Calls
if 'corrections_cache' not in st.session_state:
    st.session_state.corrections_cache = None
if 'corrections_cache_time' not in st.session_state:
    st.session_state.corrections_cache_time = 0

if not st.session_state.data_loaded:
    dates = get_dates()
    if dates:
        latest_date = dates[0]
        snap = load_snapshot(latest_date.strftime("%Y-%m-%d"))
        ci_snap = load_checkins_snapshot(latest_date.strftime("%Y-%m-%d"))
        if snap is not None:
            st.session_state.df_all = snap
            st.session_state.checkins_all = ci_snap if ci_snap is not None else pd.DataFrame()
            st.session_state.current_date = latest_date.strftime("%Y-%m-%d")
            st.session_state.data_loaded = True

st.markdown("<h1 style='text-align: center;'>🏔️🎾 halle11</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888; font-size: 14px;'>⚡ Famiglia Schneiderhan powered</p>", unsafe_allow_html=True)

# ========================================
# SIDEBAR
# ========================================

st.sidebar.title("🚀 Analyse")

p_file = st.sidebar.file_uploader("📁 Playtomic CSV", type=['csv'], key="playtomic")
c_file = st.sidebar.file_uploader("📁 Checkins CSV", type=['csv'], key="checkins")

if st.sidebar.button("🚀 Analysieren", use_container_width=True) and p_file and c_file:
    with st.spinner(get_random_padel_message('verarbeite')):
        pdf = parse_playtomic_csv(p_file)
        
        if pdf.empty:
            st.error("❌ Playtomic CSV konnte nicht gelesen werden")
            st.stop()
        
        save_playtomic_raw(pdf)
        
        playtomic_filtered = pdf[pdf['Product SKU'].isin(['User booking registration', 'Open match registration'])].copy() if 'Product SKU' in pdf.columns else pdf.copy()
        
        if 'Refund id' in playtomic_filtered.columns:
            playtomic_filtered = playtomic_filtered[playtomic_filtered['Refund id'] == '-']
        if 'Payment status' in playtomic_filtered.columns:
            playtomic_filtered = playtomic_filtered[playtomic_filtered['Payment status'] != 'Refund']
        
        rename_map = {
            'User name': 'Name', 'Total': 'Betrag_raw', 'Service date': 'Servicedatum_raw',
            'Product SKU': 'Product_SKU', 'Payment id': 'Payment id', 'Club payment id': 'Club payment id', 'Sport': 'Sport'
        }
        if 'Service time' in playtomic_filtered.columns:
            rename_map['Service time'] = 'Service_Zeit'
        
        playtomic_filtered.rename(columns=rename_map, inplace=True)
        playtomic_filtered['Service_Zeit'] = playtomic_filtered['Servicedatum_raw'].astype(str).str.extract(r'(\d{2}:\d{2})')
        playtomic_filtered['Name_norm'] = playtomic_filtered['Name'].apply(normalize_name)
        playtomic_filtered['Betrag_raw'] = playtomic_filtered['Betrag_raw'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('€', '', regex=False).str.strip()
        playtomic_filtered['Betrag'] = pd.to_numeric(playtomic_filtered['Betrag_raw'], errors='coerce').fillna(0)
        playtomic_filtered['Betrag'] = playtomic_filtered['Betrag'].apply(lambda x: f"{x:.2f}".replace(',', '.'))
        playtomic_filtered['Servicedatum'] = playtomic_filtered['Servicedatum_raw'].apply(parse_date_safe)
        
        if 'Service_Zeit' not in playtomic_filtered.columns:
            playtomic_filtered['Service_Zeit'] = ''
        else:
            playtomic_filtered['Service_Zeit'] = playtomic_filtered['Service_Zeit'].fillna('')
        
        playtomic_filtered['Betrag_num'] = pd.to_numeric(playtomic_filtered['Betrag'], errors='coerce').fillna(0)
        playtomic_filtered = playtomic_filtered[playtomic_filtered['Betrag_num'] >= 0]
        
        if 'Payment id' in playtomic_filtered.columns:
            playtomic_filtered = playtomic_filtered.drop_duplicates(subset=['Payment id'])

        # ✅ FIX: Relevanz für BEIDE Sportarten (Padel UND Tennis), unter 6€
        playtomic_filtered['Relevant'] = (
            ((playtomic_filtered['Betrag_num'] < 6) & (playtomic_filtered['Betrag_num'] > 0)) | 
            (playtomic_filtered['Betrag_num'] == 0)
        )
        
        cdf = parse_checkins_csv(c_file)
        
        if cdf.empty:
            st.error("❌ Checkins CSV konnte nicht gelesen werden")
            st.stop()
        
        rename_map_ci = {'Vor- & Nachname': 'Name', 'Datum': 'Checkin_Datum_raw'}
        if 'Zeit' in cdf.columns:
            rename_map_ci['Zeit'] = 'Checkin_Zeit'
        cdf.rename(columns=rename_map_ci, inplace=True)
        cdf['Name_norm'] = cdf['Name'].apply(normalize_name)
        cdf['Checkin_Datum'] = pd.to_datetime(cdf['Checkin_Datum_raw'], errors='coerce').dt.date
        
        if 'Checkin_Zeit' not in cdf.columns:
            cdf['Checkin_Zeit'] = ''
        else:
            cdf['Checkin_Zeit'] = cdf['Checkin_Zeit'].fillna('')
        
        all_dates = sorted(set(playtomic_filtered['Servicedatum'].dropna()) | set(cdf['Checkin_Datum'].dropna()))
        st.info(f"📦 {len(all_dates)} Tage werden verarbeitet...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_results = []
        all_checkin_results = []
        mapping = load_name_mapping()
        
        for i, td in enumerate(all_dates):
            progress_bar.progress((i + 1) / len(all_dates))
            status_text.text(f"{td.strftime('%d.%m.%Y')} ({i+1}/{len(all_dates)})")
            
            pd_day = playtomic_filtered[playtomic_filtered['Servicedatum'] == td]
            cd_day = cdf[cdf['Checkin_Datum'] == td]
            
            for _, row in pd_day.iterrows():
                is_ma = normalize_name(row['Name']) in [normalize_name(m) for m in MITARBEITER]
                
                checkin_match = cd_day[cd_day['Name_norm'] == row['Name_norm']]
                has_ci = not checkin_match.empty
                
                if not has_ci and row['Name_norm'] in mapping:
                    mapped = mapping[row['Name_norm']]
                    mapped_name = mapped['checkin_name'] if isinstance(mapped, dict) else mapped
                    mapped_checkin = cd_day[cd_day['Name_norm'] == mapped_name]
                    if not mapped_checkin.empty:
                        has_ci = True
                        checkin_match = mapped_checkin
                
                ci_zeit = checkin_match.iloc[0]['Checkin_Zeit'] if has_ci else ''
                fehler = row['Relevant'] and not has_ci and not is_ma
                
                all_results.append({
                    'Datum': str(td), 'Name': row['Name'], 'Name_norm': row['Name_norm'],
                    'Betrag': row['Betrag'], 'Service_Zeit': str(row['Service_Zeit']), 'Checkin_Zeit': str(ci_zeit),
                    'Product_SKU': row.get('Product_SKU', ''), 'Sport': row.get('Sport', ''),
                    'Relevant': 'Ja' if row['Relevant'] else 'Nein',
                    'Check-in': 'Ja' if has_ci else 'Nein',
                    'Mitarbeiter': 'Ja' if is_ma else 'Nein',
                    'Fehler': 'Ja' if fehler else 'Nein',
                    'analysis_date': td.strftime("%Y-%m-%d"),
                    'Payment id': row.get('Payment id', ''), 'Club payment id': row.get('Club payment id', '')
                })
            
            seen_names = set()
            for _, row in cd_day.iterrows():
                if row['Name_norm'] not in seen_names:
                    seen_names.add(row['Name_norm'])
                    buchung = pd_day[pd_day['Name_norm'] == row['Name_norm']]
                    gespielt = not buchung.empty
                    all_checkin_results.append({
                        'Datum': str(td), 'Name': row['Name'], 'Name_norm': row['Name_norm'],
                        'Checkin_Zeit': str(row['Checkin_Zeit']), 'Gespielt': 'Ja' if gespielt else 'Nein',
                        'analysis_date': td.strftime("%Y-%m-%d")
                    })
        
        progress_bar.progress(1.0)
        status_text.success(f"✅ {len(all_dates)} Tage verarbeitet!")
        
        # Speichern
        if all_results:
            buchungen = loadsheet("buchungen", ['analysis_date'])
            if not buchungen.empty:
                buchungen['_dup_key'] = buchungen['analysis_date'].astype(str) + '|' + buchungen['Name_norm'].astype(str) + '|' + buchungen['Service_Zeit'].astype(str)
                existing_keys = set(buchungen['_dup_key'])
                new_results_df = pd.DataFrame(all_results)
                new_results_df['_dup_key'] = new_results_df['analysis_date'].astype(str) + '|' + new_results_df['Name_norm'].astype(str) + '|' + new_results_df['Service_Zeit'].astype(str)
                new_results_filtered = new_results_df[~new_results_df['_dup_key'].isin(existing_keys)].drop('_dup_key', axis=1)
                if not new_results_filtered.empty:
                    buchungen = buchungen.drop('_dup_key', axis=1)
                    savesheet(pd.concat([buchungen, new_results_filtered], ignore_index=True), "buchungen")
                    st.success(f"✅ {len(new_results_filtered)} neue Buchungen!")
            else:
                savesheet(pd.DataFrame(all_results), "buchungen")
                st.success(f"✅ {len(all_results)} Buchungen!")
        
        if all_checkin_results:
            checkins = loadsheet("checkins", ['analysis_date'])
            if not checkins.empty:
                checkins['_dup_key'] = checkins['analysis_date'].astype(str) + '|' + checkins['Name_norm'].astype(str) + '|' + checkins['Checkin_Zeit'].astype(str)
                existing_keys = set(checkins['_dup_key'])
                new_checkins_df = pd.DataFrame(all_checkin_results)
                new_checkins_df['_dup_key'] = new_checkins_df['analysis_date'].astype(str) + '|' + new_checkins_df['Name_norm'].astype(str) + '|' + new_checkins_df['Checkin_Zeit'].astype(str)
                new_checkins_filtered = new_checkins_df[~new_checkins_df['_dup_key'].isin(existing_keys)].drop('_dup_key', axis=1)
                if not new_checkins_filtered.empty:
                    checkins = checkins.drop('_dup_key', axis=1)
                    savesheet(pd.concat([checkins, new_checkins_filtered], ignore_index=True), "checkins")
                    st.success(f"✅ {len(new_checkins_filtered)} neue Check-ins!")
            else:
                savesheet(pd.DataFrame(all_checkin_results), "checkins")
                st.success(f"✅ {len(all_checkin_results)} Check-ins!")
        
        st.success("🎉 Por cuatro! 🚀")
        st.balloons()
        time.sleep(2)
        st.rerun()

# Customer Upload
st.sidebar.markdown("---")
cust_file = st.sidebar.file_uploader("👥 Customers", type=['csv'], key="customers")

if st.sidebar.button("📤 Upload", use_container_width=True) and cust_file:
    try:
        customers_df = parse_csv(cust_file)
        if not customers_df.empty and 'name' in customers_df.columns:
            customers_df['name_norm'] = customers_df['name'].apply(normalize_name)
            if savesheet(customers_df, "customers"):
                st.sidebar.success(f"✅ {len(customers_df)} Kunden!")
                loadsheet.clear()
                st.rerun()
    except Exception as e:
        st.sidebar.error(f"❌ {str(e)[:50]}")


# ========================================
# TABS
# ========================================

tab1, tab2 = st.tabs(["📅 Tag", "📊 Monat"])

with tab1:
    dates = get_dates()
    
    if not dates:
        st.info("📄 Lade CSVs hoch! 🎾")
        st.stop()
    
    # Navigation
    col_prev, col_date, col_next = st.columns([1, 3, 1])
    
    with col_prev:
        if st.button("◀", use_container_width=True, key="prev_btn"):
            st.session_state.day_idx = min(st.session_state.day_idx + 1, len(dates) - 1)
            st.session_state.current_date = dates[st.session_state.day_idx].strftime("%Y-%m-%d")
            st.rerun()
    
    with col_date:
        curr_date = dates[st.session_state.day_idx]
        st.info(f"📅 {curr_date.strftime('%d.%m.%Y')}")
    
    with col_next:
        if st.button("▶", use_container_width=True, key="next_btn"):
            st.session_state.day_idx = max(st.session_state.day_idx - 1, 0)
            st.session_state.current_date = dates[st.session_state.day_idx].strftime("%Y-%m-%d")
            st.rerun()
    
    with st.expander("📆 Springe zu...", expanded=False):
        selected_date = st.selectbox("Datum:", options=dates, index=st.session_state.day_idx, format_func=lambda x: x.strftime("%d.%m.%Y"), key="date_jump")
        if st.button("✅ Go", use_container_width=True):
            st.session_state.day_idx = dates.index(selected_date)
            st.session_state.current_date = selected_date.strftime("%Y-%m-%d")
            st.rerun()
    
    curr_date = dates[st.session_state.day_idx]
    st.session_state.current_date = curr_date.strftime("%Y-%m-%d")
    
    df = load_snapshot(st.session_state.current_date)
    ci_df = load_checkins_snapshot(st.session_state.current_date)
    
    if df is None or df.empty:
        st.info("🎾 Keine Daten für diesen Tag")
        st.stop()

    revenue = get_revenue_from_raw(date_str=st.session_state.current_date)
    wellpass_unique_checkins = get_unique_wellpass_checkins(st.session_state.current_date)
    wellpass_wert_tag = get_wellpass_wert(datetime.strptime(st.session_state.current_date, "%Y-%m-%d").date())
    wellpass_revenue = wellpass_unique_checkins * wellpass_wert_tag
    gesamt_mit_wellpass = revenue['gesamt'] + wellpass_revenue
    
    
    # ✅ VORWOCHEN-VERGLEICH
    last_week_date = curr_date - timedelta(days=7)
    last_week_str = last_week_date.strftime("%Y-%m-%d")
    
    revenue_last_week = get_revenue_from_raw(date_str=last_week_str)
    wellpass_last_week = get_unique_wellpass_checkins(last_week_str)
    wellpass_rev_last_week = wellpass_last_week * wellpass_wert_tag
    gesamt_last_week = revenue_last_week['gesamt'] + wellpass_rev_last_week
    
    # Calculate deltas
    delta_gesamt = gesamt_mit_wellpass - gesamt_last_week
    delta_pct = ((gesamt_mit_wellpass / gesamt_last_week) - 1) * 100 if gesamt_last_week > 0 else 0
    
    
    # ✅ KOMPAKTE UMSATZ-ZEILE
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        delta_str = f"{delta_pct:+.0f}% vs. Vorwoche" if gesamt_last_week > 0 else None
        st.metric("💰 Gesamt", f"€{gesamt_mit_wellpass:.2f}", delta_str)
    with col2:
        st.metric("🎾 Padel", f"€{revenue['padel']:.2f}")
    with col3:
        st.metric("🎾 Tennis", f"€{revenue['tennis']:.2f}")
    with col4:
        st.metric("🏓 Extras", f"€{revenue['baelle'] + revenue['schlaeger']:.2f}")
    with col5:
        st.metric("💳 Wellpass", f"€{wellpass_revenue:.2f}", f"{wellpass_unique_checkins} CI")
    
    st.markdown("---")
    
    # ✅ STATISTIK-BADGES
    relevant_count = len(df[df['Relevant'] == 'Ja'])
    fehler_count = len(df[df['Fehler'] == 'Ja'])
    checkin_count = len(ci_df) if ci_df is not None else 0
    
    st.markdown(f"**📊 Übersicht:** {len(df)} Buchungen · {relevant_count} Relevant · {'🔴' if fehler_count > 0 else '🟢'} {fehler_count} Fehler · {checkin_count} Check-ins")
    
    st.markdown("---")
    
    # ✅ ZWEI LISTEN MIT STATUS-BADGE VOR DEM NAMEN
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("##### 📋 Buchungen (Relevant)")
        rv = df[df['Relevant'] == 'Ja'].sort_values('Name').copy()
        
        if not rv.empty:
            # ✅ Toggle: Nur Probleme anzeigen (alles OK ausblenden)
            show_only_problems = st.checkbox("🔍 Nur Probleme (Für Marci ❤️)", value=True, key="hide_green_bookings", help="Blendet alle OK-Einträge aus")
            
            # Status-Badge vor Namen - ⚪ wird jetzt auch 🟢
            def add_status_badge(row):
                if row['Fehler'] == 'Ja':
                    return f"🔴 {row['Name']}"
                else:
                    # Sowohl Check-in OK als auch nicht-relevant = grün
                    return f"🟢 {row['Name']}"
            
            rv['Spieler'] = rv.apply(add_status_badge, axis=1)
            rv['_is_problem'] = rv['Fehler'] == 'Ja'
            
            # Filtere wenn Toggle aktiv - zeige nur Probleme (rot)
            if show_only_problems:
                rv_display = rv[rv['_is_problem'] == True].copy()
                hidden_count = len(rv) - len(rv_display)
            else:
                rv_display = rv.copy()
                hidden_count = 0
            
            # Sport-Icon
            if 'Sport' in rv_display.columns:
                rv_display['🏆'] = rv_display['Sport'].apply(lambda x: '🎾P' if str(x).upper() == 'PADEL' else ('🎾T' if str(x).upper() == 'TENNIS' else ''))
            
            display_cols = ['Spieler', 'Betrag']
            if 'Service_Zeit' in rv_display.columns:
                display_cols.append('Service_Zeit')
            if '🏆' in rv_display.columns:
                display_cols.append('🏆')
            
            if not rv_display.empty:
                # Dynamische Höhe - alle Zeilen sichtbar
                row_height = 35
                header_height = 40
                table_height = min(len(rv_display) * row_height + header_height, 1200)
                
                st.dataframe(rv_display[display_cols], use_container_width=True, hide_index=True, height=table_height)
            else:
                st.success("✅ Alle OK!")
            
            # Caption mit Info über ausgeblendete
            if hidden_count > 0:
                st.caption(f"🟢 {hidden_count} OK ausgeblendet · 🔴 {len(rv_display)} offen")
            else:
                st.caption(f"🟢 Check-in OK · 🔴 Fehlt")
        else:
            st.info("Keine relevanten Buchungen")
    
    with col_right:
        st.markdown("##### ✅ Wellpass Check-ins")
        
        if ci_df is not None and not ci_df.empty:
            ci_view = ci_df.sort_values('Name').copy()
            
            # ✅ Toggle: Nur Probleme anzeigen
            show_only_ci_problems = st.checkbox("🔍 Nur Probleme (Für Marci ❤️)", value=True, key="hide_green_checkins", help="Blendet alle OK-Check-ins aus")
            
            # Load name mapping for inverse lookup
            mapping = load_name_mapping()
            
            # Build inverse mapping: checkin_name_norm -> buchung_name_norm
            inverse_mapping = {}
            for buchung_name_norm, details in mapping.items():
                if isinstance(details, dict):
                    ci_norm = details.get("checkin_name", "")
                else:
                    ci_norm = details
                if ci_norm:
                    inverse_mapping[ci_norm] = buchung_name_norm
            
            # Get all booking names for today (normalized)
            booking_names_today = set(df['Name_norm'].tolist()) if 'Name_norm' in df.columns else set()
            
            # Status-Badge mit Mapping-Berücksichtigung + _is_green Flag
            def add_gespielt_badge_with_mapping(row):
                ci_name_norm = row.get('Name_norm', '')
                ci_name_lower = row.get('Name', '').lower().strip()
                
                # 0) Always green list - Familie/Bekannte
                if ci_name_lower in ALWAYS_GREEN_CHECKINS:
                    return f"🟢 {row['Name']}", True
                
                # 1) Direct match: Check-in name exists in bookings
                if ci_name_norm in booking_names_today:
                    return f"🟢 {row['Name']}", True
                
                # 2) Mapped match: Check-in name was mapped to a booking name
                if ci_name_norm in inverse_mapping:
                    mapped_buchung_name = inverse_mapping[ci_name_norm]
                    if mapped_buchung_name in booking_names_today:
                        return f"🟢 {row['Name']}", True
                
                # 3) No match found
                return f"🔴 {row['Name']}", False
            
            # Apply and split result
            ci_view['_result'] = ci_view.apply(add_gespielt_badge_with_mapping, axis=1)
            ci_view['Spieler'] = ci_view['_result'].apply(lambda x: x[0])
            ci_view['_is_green'] = ci_view['_result'].apply(lambda x: x[1])
            
            # Filter wenn Toggle aktiv
            if show_only_ci_problems:
                ci_display = ci_view[ci_view['_is_green'] == False].copy()
                hidden_ci_count = len(ci_view) - len(ci_display)
            else:
                ci_display = ci_view.copy()
                hidden_ci_count = 0
            
            display_cols_ci = ['Spieler', 'Checkin_Zeit']
            
            if not ci_display.empty:
                # Dynamische Höhe
                row_height = 35
                header_height = 40
                table_height = min(len(ci_display) * row_height + header_height, 1200)
                
                st.dataframe(ci_display[display_cols_ci], use_container_width=True, hide_index=True, height=table_height)
            else:
                st.success("✅ Alle OK!")
            
            # Caption
            if hidden_ci_count > 0:
                st.caption(f"🟢 {hidden_ci_count} OK ausgeblendet · 🔴 {len(ci_display)} ohne Buchung")
            else:
                st.caption(f"🟢 Buchung vorhanden · 🔴 Keine Buchung gefunden")
        else:
            st.info("Keine Check-ins")
    
    st.markdown("---")
    
    # ✅ FEHLER-BEREICH
    fehler = df[df['Fehler'] == 'Ja'].copy()
    if not fehler.empty:
        mapping = load_name_mapping()
        rejected_matches = load_rejected_matches()
        corr = loadsheet("corrections", ['key','date','behoben','timestamp'])
        
        # Count open vs fixed
        open_count = 0
        fixed_count = 0
        for idx, row in fehler.iterrows():
            key = f"{row['Name_norm']}_{row['Datum']}_{row['Betrag']}"
            is_behoben = False
            if not corr.empty and 'key' in corr.columns:
                match_corr = corr[corr['key'] == key]
                if not match_corr.empty:
                    is_behoben = bool(match_corr.iloc[0].get('behoben', False))
            if is_behoben:
                fixed_count += 1
            else:
                open_count += 1
        
        st.subheader(f"📋 Fehler-Status ({open_count} offen · {fixed_count} behoben)")
        
        for idx, row in fehler.iterrows():
            key = f"{row['Name_norm']}_{row['Datum']}_{row['Betrag']}"
            is_behoben = False
            if not corr.empty and 'key' in corr.columns:
                match_corr = corr[corr['key'] == key]
                if not match_corr.empty:
                    is_behoben = bool(match_corr.iloc[0].get('behoben', False))
            
            whatsapp_sent = get_whatsapp_sent_time(row)
            sport_icon = '🎾P' if str(row.get('Sport', '')).upper() == 'PADEL' else '🎾T'
            
            # Status-Icon based on behoben
            status_icon = "🟢" if is_behoben else "🔴"
            status_text = "Behoben" if is_behoben else "Offen"
            
            with st.expander(f"{status_icon} {row['Name']} | €{row['Betrag']} | {row.get('Service_Zeit', '')} {sport_icon} [{status_text}]", expanded=not is_behoben):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    customer = get_customer_data(row['Name'])
                    if customer:
                        st.caption(f"📱 {customer['phone_number']} · 📧 {customer['email'][:30]}")
                    else:
                        st.caption("⚠️ Nicht im Customer-Sheet")
                    
                    if whatsapp_sent:
                        st.caption(f"✅ WhatsApp: {whatsapp_sent.strftime('%d.%m. %H:%M')}")
                
                with col2:
                    if is_behoben:
                        # Button to reopen
                        if st.button("🔄 Wieder öffnen", key=f"reopen_{key}", use_container_width=True):
                            if not corr.empty and 'key' in corr.columns:
                                corr = corr[corr['key'] != key]
                                savesheet(corr, "corrections")
                            st.rerun()
                    else:
                        if st.button("✅ Behoben", key=f"fix_{key}", use_container_width=True):
                            if not corr.empty and 'key' in corr.columns:
                                corr = corr[corr['key'] != key]
                            corr = pd.concat([corr, pd.DataFrame([{'key': key, 'date': st.session_state.current_date, 'behoben': True, 'timestamp': datetime.now().isoformat()}])], ignore_index=True)
                            savesheet(corr, "corrections")
                            st.rerun()
                
                # Only show matching interface if NOT behoben
                if not is_behoben:
                    render_name_matching_interface(row, ci_df, mapping, rejected_matches, fehler)
                    
                    st.markdown("---")
                    col_wa1, col_wa2 = st.columns(2)
                    with col_wa1:
                        if st.button("📱 WhatsApp", key=f"wa_{key}", use_container_width=True):
                            send_wellpass_whatsapp_to_player(row)
                    with col_wa2:
                        if st.button("🧪 Test", key=f"test_{key}", use_container_width=True):
                            send_wellpass_whatsapp_test(row)
    else:
        st.success("✅ Keine offenen Fehler! Por cuatro! 🎉")
    
    # ✅ OFFENE FEHLER DER LETZTEN 5 TAGE
    st.markdown("---")
    with st.expander("📋 Offene Fehler der letzten 5 Tage", expanded=False):
        # Lade Buchungen und Corrections
        all_buchungen = loadsheet("buchungen")
        all_corrections = loadsheet("corrections", ['key', 'behoben'])
        
        if not all_buchungen.empty and 'analysis_date' in all_buchungen.columns:
            # Letzte 5 Tage berechnen (ohne heute)
            today = datetime.strptime(st.session_state.current_date, "%Y-%m-%d").date()
            past_dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 6)]
            
            # Filtere auf Fehler der letzten 5 Tage
            past_fehler = all_buchungen[
                (all_buchungen['analysis_date'].isin(past_dates)) & 
                (all_buchungen['Fehler'] == 'Ja')
            ].copy()
            
            if not past_fehler.empty:
                # Prüfe welche behoben sind
                open_fehler = []
                for idx, row in past_fehler.iterrows():
                    key = f"{row['Name_norm']}_{row['Datum']}_{row['Betrag']}"
                    is_behoben = False
                    if not all_corrections.empty and 'key' in all_corrections.columns:
                        match_corr = all_corrections[all_corrections['key'] == key]
                        if not match_corr.empty:
                            is_behoben = bool(match_corr.iloc[0].get('behoben', False))
                    
                    if not is_behoben:
                        open_fehler.append({
                            'Datum': row['Datum'],
                            'Name': row['Name'],
                            'Betrag': f"€{row['Betrag']}",
                            'Zeit': row.get('Service_Zeit', ''),
                            'Sport': '🎾P' if str(row.get('Sport', '')).upper() == 'PADEL' else '🎾T',
                            '_key': key,
                            '_row': row
                        })
                
                if open_fehler:
                    st.warning(f"⚠️ {len(open_fehler)} offene Fehler aus den letzten 5 Tagen")
                    
                    # Gruppiere nach Datum
                    from collections import defaultdict
                    by_date = defaultdict(list)
                    for f in open_fehler:
                        by_date[f['Datum']].append(f)
                    
                    for datum in sorted(by_date.keys(), reverse=True):
                        fehler_list = by_date[datum]
                        datum_display = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
                        
                        st.markdown(f"**📅 {datum_display}** ({len(fehler_list)} offen)")
                        
                        for f in fehler_list:
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.caption(f"🔴 {f['Name']} | {f['Betrag']} | {f['Zeit']} {f['Sport']}")
                            with col2:
                                if st.button("✅", key=f"fix_past_{f['_key']}", use_container_width=True):
                                    corr = loadsheet("corrections", ['key','date','behoben','timestamp'])
                                    if not corr.empty and 'key' in corr.columns:
                                        corr = corr[corr['key'] != f['_key']]
                                    corr = pd.concat([corr, pd.DataFrame([{
                                        'key': f['_key'], 
                                        'date': f['Datum'], 
                                        'behoben': True, 
                                        'timestamp': datetime.now().isoformat()
                                    }])], ignore_index=True)
                                    savesheet(corr, "corrections")
                                    st.rerun()
                        
                        st.markdown("---")
                else:
                    st.success("✅ Keine offenen Fehler aus den letzten 5 Tagen!")
            else:
                st.info("Keine Fehler in den letzten 5 Tagen gefunden")
        else:
            st.info("Keine Buchungsdaten vorhanden")
    
    # ✅ CHARTS NACH UNTEN
    if gesamt_mit_wellpass > 0:
        with st.expander("📊 Charts", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                fig = go.Figure(data=[go.Pie(
                    labels=['Padel', 'Tennis', 'Extras', 'Wellpass'],
                    values=[revenue['padel'], revenue['tennis'], revenue['baelle'] + revenue['schlaeger'], wellpass_revenue],
                    hole=.4, marker_colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
                )])
                fig.update_layout(title="Umsatz", height=300)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                if revenue['padel'] > 0 or revenue['tennis'] > 0:
                    fig2 = go.Figure(data=[
                        go.Bar(name='Padel', x=['Sport'], y=[revenue['padel']], marker_color='#FF6B6B'),
                        go.Bar(name='Tennis', x=['Sport'], y=[revenue['tennis']], marker_color='#4ECDC4')
                    ])
                    fig2.update_layout(title="Padel vs Tennis", height=300, barmode='group')
                    st.plotly_chart(fig2, use_container_width=True)
    
    render_learned_matches_manager()


# ========================================
# MONATS-TAB
# ========================================

with tab2:
    st.subheader("📊 Monat")
    
    today = date.today()
    month_names = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}
    
    col1, col2 = st.columns(2)
    with col1:
        selected_year = st.selectbox("Jahr:", list(range(2024, today.year + 1)), index=today.year - 2024)
    with col2:
        selected_month = st.selectbox("Monat:", list(range(1, 13)), format_func=lambda x: month_names[x], index=today.month - 1)
    
    first_day = date(selected_year, selected_month, 1)
    last_day = date(selected_year, selected_month, monthrange(selected_year, selected_month)[1])
    
    buchungen = loadsheet("buchungen")
    
    if buchungen.empty or 'analysis_date' not in buchungen.columns:
        st.info("📦 Keine Daten")
        st.stop()
    
    buchungen['date_obj'] = pd.to_datetime(buchungen['analysis_date'], errors='coerce').dt.date
    month_data = buchungen[(buchungen['date_obj'] >= first_day) & (buchungen['date_obj'] <= last_day)]
    
    if month_data.empty:
        st.warning(f"⚠️ Keine Daten für {month_names[selected_month]} {selected_year}")
        st.stop()
    
    total_buchungen = len(month_data)
    relevant_buchungen = len(month_data[month_data['Relevant'] == 'Ja'])
    fehler_gesamt = len(month_data[month_data['Fehler'] == 'Ja'])
    
    checkins = loadsheet("checkins")
    wellpass_checkins_monat = 0
    if not checkins.empty and 'analysis_date' in checkins.columns:
        checkins['date_obj'] = pd.to_datetime(checkins['analysis_date'], errors='coerce').dt.date
        month_checkins = checkins[(checkins['date_obj'] >= first_day) & (checkins['date_obj'] <= last_day)]
        if not month_checkins.empty:
            wellpass_checkins_monat = len(month_checkins.drop_duplicates(subset=['analysis_date', 'Name_norm']))
    
    revenue_month = get_revenue_from_raw(start_date=first_day, end_date=last_day)
    wellpass_revenue_monat = wellpass_checkins_monat * WELLPASS_WERT
    gesamt_umsatz = revenue_month['gesamt'] + wellpass_revenue_monat
    
    st.markdown("---")
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("💰 Gesamt", f"€{gesamt_umsatz:.2f}")
    with col2:
        st.metric("🎾 Padel", f"€{revenue_month['padel']:.2f}")
    with col3:
        st.metric("🎾 Tennis", f"€{revenue_month['tennis']:.2f}")
    with col4:
        st.metric("💳 Wellpass", f"€{wellpass_revenue_monat:.2f}")
    with col5:
        st.metric("📊 Buchungen", f"{total_buchungen}")
    with col6:
        fehler_rate = (fehler_gesamt / relevant_buchungen * 100) if relevant_buchungen > 0 else 0
        st.metric("❌ Fehler", f"{fehler_gesamt}", f"{fehler_rate:.1f}%")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(data=[go.Pie(
            labels=['Padel', 'Tennis', 'Extras', 'Wellpass'],
            values=[revenue_month['padel'], revenue_month['tennis'], revenue_month['baelle'] + revenue_month['schlaeger'], wellpass_revenue_monat],
            hole=.4, marker_colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
        )])
        fig.update_layout(title="Umsatz-Verteilung", height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        korrekt = relevant_buchungen - fehler_gesamt
        fig = go.Figure(data=[go.Pie(
            labels=['✅ OK', '❌ Fehler'], values=[korrekt, fehler_gesamt],
            hole=.4, marker_colors=['#96CEB4', '#FF6B6B']
        )])
        fig.update_layout(title="Fehlerquote", height=300)
        st.plotly_chart(fig, use_container_width=True)


# ========================================
# FOOTER
# ========================================

st.markdown("---")
st.markdown("<p style='text-align: center; color: #888; font-size: 12px;'>🏔️🎾 halle11 v9.2 · ⚡ Famiglia Schneiderhan powered</p>", unsafe_allow_html=True)
