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
import base64


# ========================================
# 🎨 DESIGN & BRANDING
# ========================================

# Farbschema halle11
COLORS = {
    'primary': '#1B5E20',      # Dunkelgrün (Berg/Wald)
    'primary_light': '#4CAF50', # Hellgrün
    'secondary': '#FFB300',     # Tennis-Gelb/Gold
    'accent': '#FF5722',        # Padel-Orange
    'success': '#43A047',       # Erfolg-Grün
    'error': '#E53935',         # Fehler-Rot
    'warning': '#FB8C00',       # Warnung-Orange
    'background': '#F8FBF8',    # Soft-Grün-Weiß
    'card_bg': '#FFFFFF',       # Karten-Hintergrund
    'text': '#1A1A1A',          # Haupttext
    'text_light': '#666666',    # Sekundärtext
    'border': '#E0E0E0',        # Rahmen
}

# SVG Icon als Base64 (Berg + Tennisball)
FAVICON_SVG = '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <defs>
    <linearGradient id="bergGrad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" style="stop-color:#1B5E20"/>
      <stop offset="100%" style="stop-color:#4CAF50"/>
    </linearGradient>
    <linearGradient id="ballGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#C8E600"/>
      <stop offset="100%" style="stop-color:#9ACD32"/>
    </linearGradient>
  </defs>
  <!-- Berg -->
  <polygon points="10,85 50,20 90,85" fill="url(#bergGrad)"/>
  <polygon points="30,85 50,45 70,85" fill="#2E7D32" opacity="0.5"/>
  <!-- Schnee -->
  <polygon points="42,35 50,20 58,35 53,38 50,32 47,38" fill="white"/>
  <!-- Tennisball -->
  <circle cx="75" cy="30" r="18" fill="url(#ballGrad)" stroke="#7CB342" stroke-width="2"/>
  <path d="M 63 22 Q 75 35 63 42" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M 87 22 Q 75 35 87 42" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
</svg>
'''

# Sound-Effekt als Base64 (kurzer "Pling" Sound)
# Generiert als Web Audio - wird als JS eingebunden
WHATSAPP_SOUND_JS = '''
function playWhatsAppSound() {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.setValueAtTime(880, audioContext.currentTime);
    oscillator.frequency.setValueAtTime(1100, audioContext.currentTime + 0.1);
    oscillator.frequency.setValueAtTime(1320, audioContext.currentTime + 0.2);
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.4);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.4);
}
'''

# Konfetti Animation CSS
CONFETTI_CSS = '''
@keyframes confetti-fall {
    0% { transform: translateY(-100vh) rotate(0deg); opacity: 1; }
    100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
}
.confetti {
    position: fixed;
    width: 10px;
    height: 10px;
    top: -10px;
    z-index: 9999;
    animation: confetti-fall 3s ease-out forwards;
}
'''


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
    'Filip Nadrchal',
    'Spieler 1', 'Spieler 2', 'Spieler 3', 'Spieler 4', 'Playtomic',
    # Familie/Bekannte - keine Wellpass-Pflicht
    'Janik Otto', 'Tim Otto', 'Wencke Kern', 'Thorsten Kern'
}

# ✅ Diese Check-ins sind IMMER grün (Familie/Bekannte ohne Wellpass-Pflicht)
ALWAYS_GREEN_CHECKINS = {
    'marcel sidorov', 'mattia niklas mauta', 'thomas otto', 'andrea otto',
    'andreas schneiderhan', 'ludmila sidorov', 'tanja schneiderhan',
    'janik otto', 'tim otto', 'wencke kern', 'thorsten kern'
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


# ========================================
# 🎨 DESIGN HELPER FUNKTIONEN
# ========================================

def render_header():
    """Rendert den stylischen Header mit Logo."""
    st.markdown("""
        <div class="main-header animate-in">
            <h1>🏔️ halle11</h1>
            <div class="subtitle">Padel & Tennis am Berg</div>
        </div>
    """, unsafe_allow_html=True)


def render_metric_card(icon: str, value: str, label: str, card_type: str = "", delta: str = None, delta_positive: bool = True):
    """Rendert eine stylische Metriken-Karte."""
    delta_html = ""
    if delta:
        delta_class = "positive" if delta_positive else "negative"
        delta_html = f'<div class="delta {delta_class}">{delta}</div>'
    
    return f"""
        <div class="metric-card {card_type} animate-in">
            <div class="icon">{icon}</div>
            <div class="value">{value}</div>
            <div class="label">{label}</div>
            {delta_html}
        </div>
    """


def render_metric_row(metrics: list):
    """Rendert eine Reihe von Metriken-Karten."""
    cols = st.columns(len(metrics))
    for i, metric in enumerate(metrics):
        with cols[i]:
            st.markdown(render_metric_card(**metric), unsafe_allow_html=True)


def render_status_badge(text: str, status: str = "success"):
    """Rendert ein Status-Badge."""
    return f'<span class="status-badge {status}">{text}</span>'


def trigger_confetti():
    """Triggert Konfetti-Animation via JavaScript."""
    st.markdown("<script>triggerConfetti();</script>", unsafe_allow_html=True)


def play_sound():
    """Spielt WhatsApp Sound via JavaScript (nur wenn aktiviert)."""
    if st.session_state.get('sound_enabled', True):
        st.markdown("<script>playWhatsAppSound();</script>", unsafe_allow_html=True)


def render_success_box(message: str):
    """Rendert eine Erfolgs-Box - nutzt native st.success."""
    st.success(f"✅ {message}")


def render_error_box(message: str):
    """Rendert eine Fehler-Box - nutzt native st.error."""
    st.error(f"❌ {message}")


def render_info_box(message: str):
    """Rendert eine Info-Box - nutzt native st.info."""
    st.info(f"💡 {message}")


# ========================================
# 💾 PERSISTENTE EINSTELLUNGEN
# ========================================

def load_settings():
    """Lade Einstellungen aus Google Sheets."""
    try:
        settings = loadsheet("settings", ['key', 'value'])
        if settings.empty:
            return {}
        return dict(zip(settings['key'], settings['value']))
    except:
        return {}

def save_setting(key, value):
    """Speichere eine Einstellung in Google Sheets."""
    try:
        settings = loadsheet("settings", ['key', 'value'])
        
        if settings.empty:
            settings = pd.DataFrame(columns=['key', 'value'])
        
        if key in settings['key'].values:
            settings.loc[settings['key'] == key, 'value'] = str(value)
        else:
            new_row = pd.DataFrame([{'key': key, 'value': str(value)}])
            settings = pd.concat([settings, new_row], ignore_index=True)
        
        savesheet(settings, "settings")
        return True
    except Exception as e:
        return False

def get_monthly_goal():
    """Hole das Monatsziel aus den Einstellungen."""
    settings = load_settings()
    try:
        return float(settings.get('monthly_goal', 8000))
    except:
        return 8000

def set_monthly_goal(value):
    """Setze das Monatsziel."""
    save_setting('monthly_goal', value)


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
        play_sound()  # 🔊 Sound-Effekt
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

def is_behoben_value(val):
    """Robuster Check ob ein Wert 'behoben' bedeutet (Boolean oder String)."""
    if val is None or pd.isna(val):
        return False
    return val in [True, 'True', 'true', 1, '1', 'TRUE']

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
# ✅ VERBESSERTES AUTHENTICATION MIT URL-TOKEN
# ========================================

def generate_auth_token():
    """Generiere einen sicheren Auth-Token"""
    import secrets
    return secrets.token_urlsafe(32)

def save_auth_token(token):
    """Speichere Auth-Token im Google Sheet"""
    try:
        auth_data = loadsheet("auth_tokens", ['token', 'created', 'expires'])
        
        now = datetime.now()
        expires = now + timedelta(days=30)
        
        new_token = pd.DataFrame([{
            'token': token,
            'created': now.isoformat(),
            'expires': expires.isoformat()
        }])
        
        if not auth_data.empty:
            auth_data['expires'] = pd.to_datetime(auth_data['expires'], errors='coerce')
            auth_data = auth_data[auth_data['expires'] > now]
        
        auth_data = pd.concat([auth_data, new_token], ignore_index=True)
        savesheet(auth_data, "auth_tokens")
        return True
    except Exception as e:
        return False

def check_auth_token(token):
    """Prüfe ob Token gültig ist"""
    if not token:
        return False
    
    try:
        auth_data = loadsheet("auth_tokens", ['token', 'expires'])
        
        if auth_data.empty:
            return False
        
        auth_data['expires'] = pd.to_datetime(auth_data['expires'], errors='coerce')
        match = auth_data[auth_data['token'] == token]
        
        if not match.empty:
            expires = match.iloc[0]['expires']
            if pd.notna(expires) and expires > datetime.now():
                return True
    except:
        pass
    
    return False

def check_password():
    """Haupt-Login-Funktion mit URL-Token-Support"""
    
    # 1. Prüfe URL-Parameter
    query_params = st.query_params
    url_token = query_params.get("auth", None)
    
    if url_token and check_auth_token(url_token):
        st.session_state["password_correct"] = True
        return True
    
    # 2. Prüfe Session State
    if st.session_state.get("password_correct", False):
        return True
    
    def entered():
        password = st.session_state.get("password", "")
        correct_password = st.secrets.get("passwords", {}).get("admin_password", "")
        
        if password and password == correct_password:
            new_token = generate_auth_token()
            if save_auth_token(new_token):
                st.query_params["auth"] = new_token
            
            st.session_state["password_correct"] = True
            if "password" in st.session_state:
                del st.session_state["password"]
        elif password:
            st.session_state["password_correct"] = False
    
    # ✅ Stylischer Login-Screen
    st.markdown("""
        <div class="main-header" style="margin-top: 3rem;">
            <h1>🏔️ halle11</h1>
            <div class="subtitle">Padel & Tennis am Berg</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
            <div style="background: white; padding: 2rem; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); margin-top: 2rem;">
                <h3 style="text-align: center; color: #1B5E20; margin-bottom: 1.5rem;">🔒 Anmelden</h3>
            </div>
        """, unsafe_allow_html=True)
        
        st.text_input("🔑 Passwort:", type="password", on_change=entered, key="password")
        
        if st.session_state.get("password_correct") == False:
            render_error_box("😕 Falsches Passwort!")
        
        render_info_box("Nach dem Login wird ein Token in der URL gespeichert. Speichere die URL als Lesezeichen für automatischen Login! (30 Tage gültig)")
        
        st.markdown("""
            <p style="text-align: center; color: #888; margin-top: 1rem; font-size: 12px;">
                ⚡ Famiglia Schneiderhan powered
            </p>
        """, unsafe_allow_html=True)
    
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
        play_sound()  # 🔊 Sound-Effekt
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

@st.cache_data(ttl=900, show_spinner=False)  # 15 min cache to reduce API calls
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

@st.cache_data(ttl=900, show_spinner=False)  # 15 min cache
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

@st.cache_data(ttl=300, show_spinner=False)  # 5 min cache
def get_unique_wellpass_checkins(date_str):
    """Cached unique check-in count for a date."""
    checkins = loadsheet("checkins")
    if checkins.empty or 'analysis_date' not in checkins.columns:
        return 0
    day_checkins = checkins[checkins['analysis_date'] == date_str]
    return day_checkins['Name_norm'].nunique() if not day_checkins.empty else 0

@st.cache_data(ttl=300, show_spinner=False)  # 5 min cache
def get_dates():
    """Cached list of available dates."""
    buchungen = loadsheet("buchungen", ['analysis_date'])
    if buchungen.empty or 'analysis_date' not in buchungen.columns:
        return []
    dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in buchungen['analysis_date'].unique()]
    return sorted(dates, reverse=True)

@st.cache_data(ttl=300, show_spinner=False)  # 5 min cache
def load_snapshot(date_str):
    """Cached snapshot for a specific date."""
    buchungen = loadsheet("buchungen", ['analysis_date'])
    if buchungen.empty or 'analysis_date' not in buchungen.columns:
        return None
    data = buchungen[buchungen['analysis_date'] == date_str]
    return data if not data.empty else None

@st.cache_data(ttl=300, show_spinner=False)  # 5 min cache
def load_checkins_snapshot(date_str):
    """Cached check-ins for a specific date."""
    checkins = loadsheet("checkins", ['analysis_date'])
    if checkins.empty or 'analysis_date' not in checkins.columns:
        return None
    data = checkins[checkins['analysis_date'] == date_str]
    return data if not data.empty else None


# ========================================
# NAME-MATCHING FUNKTIONEN
# ========================================

@st.cache_data(ttl=120, show_spinner=False)  # 2 min cache (shorter because data changes)
def load_name_mapping():
    """Cached name mapping loading."""
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
    load_name_mapping.clear()  # Clear cache after save

@st.cache_data(ttl=120, show_spinner=False)  # 2 min cache
def load_rejected_matches():
    """Cached rejected matches loading."""
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
    load_rejected_matches.clear()  # Clear cache after save

def remove_rejected_match(buchung_name, checkin_name):
    df = loadsheet("rejected_matches", cols=['buchung_name', 'checkin_name', 'timestamp'])
    if not df.empty:
        df = df[~((df['buchung_name'] == buchung_name) & (df['checkin_name'] == checkin_name))]
        savesheet(df, "rejected_matches")
        load_rejected_matches.clear()  # Clear cache after save

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

st.set_page_config(
    page_title="halle11 | Padel & Tennis", 
    layout="wide", 
    page_icon="🎾",  # ✅ Universell unterstütztes Emoji
    initial_sidebar_state="expanded"
)

# ========================================
# 🎨 HALLE11 DESIGN (THEME-AWARE)
# ========================================

# Dark Mode Check (vor dem CSS!)
_dark_mode = st.session_state.get('dark_mode', False)

# CSS Variablen basierend auf Mode
if _dark_mode:
    _card_bg = "#262730"
    _card_border = "#3D3D4D"
    _text_primary = "#FAFAFA"
    _text_secondary = "#B0B0B0"
    _bg_subtle = "#0E1117"
    _shadow_color = "rgba(0,0,0,0.3)"
    _shadow_hover = "rgba(0,0,0,0.4)"
    _app_bg = "#0E1117"
else:
    _card_bg = "#FFFFFF"
    _card_border = "#E0E0E0"
    _text_primary = "#1A1A1A"
    _text_secondary = "#666666"
    _bg_subtle = "#F8FBF8"
    _shadow_color = "rgba(0,0,0,0.08)"
    _shadow_hover = "rgba(0,0,0,0.12)"
    _app_bg = "#F8FBF8"

st.markdown(f"""
<style>
    /* ===== CSS VARIABLEN ===== */
    :root {{
        --halle11-primary: {COLORS['primary']};
        --halle11-primary-light: {COLORS['primary_light']};
        --halle11-secondary: {COLORS['secondary']};
        --halle11-accent: {COLORS['accent']};
        --halle11-success: {COLORS['success']};
        --halle11-error: {COLORS['error']};
        --halle11-warning: {COLORS['warning']};
        --card-bg: {_card_bg};
        --card-border: {_card_border};
        --text-primary: {_text_primary};
        --text-secondary: {_text_secondary};
        --bg-subtle: {_bg_subtle};
        --shadow-color: {_shadow_color};
        --shadow-hover: {_shadow_hover};
    }}
    
    /* ===== FORCE THEME COLORS ===== */
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    .main {{
        background: {_app_bg} !important;
    }}
    
    [data-testid="block-container"] {{
        color: {_text_primary} !important;
    }}
    
    /* ===== TEXT COLORS ===== */
    .stMarkdown, .stMarkdown p, .stMarkdown span,
    .stCaption, h1, h2, h3, h4, h5, h6,
    label, .stTextInput label, .stSelectbox label,
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
    .stDataFrame th, .stDataFrame td {{
        color: {_text_primary} !important;
    }}
    
    .stCaption, [data-testid="stMetricDelta"] {{
        color: {_text_secondary} !important;
    }}
    
    /* ===== STREAMLIT WIDGETS ===== */
    .stTextInput input, .stSelectbox > div > div,
    .stNumberInput input, .stDateInput input {{
        background: {_card_bg} !important;
        color: {_text_primary} !important;
        border-color: {_card_border} !important;
    }}
    
    .stExpander {{
        background: {_card_bg} !important;
        border-color: {_card_border} !important;
    }}
    
    .stExpander [data-testid="stExpanderToggleIcon"] {{
        color: {_text_primary} !important;
    }}
    
    /* Checkbox/Toggle */
    .stCheckbox label span {{
        color: {_text_primary} !important;
    }}
    
    /* ===== GLOBALE STYLES ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp {{
        font-family: 'Inter', sans-serif;
        background: {_app_bg} !important;
    }}
    
    /* ===== HEADER BRANDING (immer grün) ===== */
    .main-header {{
        background: linear-gradient(135deg, var(--halle11-primary) 0%, var(--halle11-primary-light) 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(27, 94, 32, 0.15);
        text-align: center;
        color: white !important;
    }}
    
    .main-header h1 {{
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        color: white !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }}
    
    .main-header .subtitle {{
        font-size: 1rem;
        opacity: 0.9;
        margin-top: 0.3rem;
        color: white !important;
    }}
    
    /* ===== METRIC CARDS (Theme-aware) ===== */
    .metric-card {{
        background: var(--card-bg);
        border-radius: 16px;
        padding: 1.2rem;
        box-shadow: 0 2px 12px var(--shadow-color);
        border: 1px solid var(--card-border);
        transition: all 0.3s ease;
        text-align: center;
    }}
    
    .metric-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 8px 25px var(--shadow-hover);
    }}
    
    .metric-card .icon {{
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }}
    
    .metric-card .value {{
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.2;
    }}
    
    .metric-card .label {{
        font-size: 0.85rem;
        color: var(--text-secondary);
        margin-top: 0.3rem;
    }}
    
    .metric-card .delta {{
        font-size: 0.8rem;
        padding: 0.2rem 0.5rem;
        border-radius: 20px;
        display: inline-block;
        margin-top: 0.5rem;
    }}
    
    .metric-card .delta.positive {{
        background: rgba(67, 160, 71, 0.15);
        color: var(--halle11-success);
    }}
    
    .metric-card .delta.negative {{
        background: rgba(229, 57, 53, 0.15);
        color: var(--halle11-error);
    }}
    
    /* Spezielle Karten-Farben */
    .metric-card.total {{ border-top: 4px solid var(--halle11-secondary); }}
    .metric-card.padel {{ border-top: 4px solid var(--halle11-accent); }}
    .metric-card.tennis {{ border-top: 4px solid var(--halle11-primary-light); }}
    .metric-card.wellpass {{ border-top: 4px solid var(--halle11-primary); }}
    .metric-card.extras {{ border-top: 4px solid #9C27B0; }}
    
    /* ===== STATUS BADGES ===== */
    .status-badge {{
        display: inline-flex;
        align-items: center;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        color: var(--text-primary);
    }}
    
    .status-badge.success {{
        background: rgba(67, 160, 71, 0.15);
        color: var(--halle11-success);
        border-color: var(--halle11-success);
    }}
    
    .status-badge.error {{
        background: rgba(229, 57, 53, 0.15);
        color: var(--halle11-error);
        border-color: var(--halle11-error);
    }}
    
    .status-badge.warning {{
        background: rgba(251, 140, 0, 0.15);
        color: var(--halle11-warning);
        border-color: var(--halle11-warning);
    }}
    
    /* ===== NAVIGATION ===== */
    .date-display {{
        background: var(--card-bg);
        padding: 0.8rem 2rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px var(--shadow-color);
        font-weight: 600;
        font-size: 1.1rem;
        color: var(--text-primary);
        border: 1px solid var(--card-border);
    }}
    
    /* ===== BUTTONS ===== */
    .stButton > button {{
        border-radius: 12px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px var(--shadow-hover) !important;
    }}
    
    /* ===== EXPANDER ===== */
    .stExpander {{
        background: var(--card-bg);
        border-radius: 12px !important;
        border: 1px solid var(--card-border) !important;
        margin-bottom: 0.8rem !important;
        overflow: hidden;
    }}
    
    .stExpander > div {{
        padding: 0.8rem !important;
    }}
    
    /* ===== SIDEBAR (immer dunkelgrün) ===== */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, var(--halle11-primary) 0%, #0D3311 100%) !important;
    }}
    
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}
    
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        color: white !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stFileUploader"] section {{
        background: rgba(255,255,255,0.1) !important;
        border: 2px dashed rgba(255,255,255,0.4) !important;
        border-radius: 12px !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stFileUploader"] section:hover {{
        border-color: rgba(255,255,255,0.8) !important;
        background: rgba(255,255,255,0.15) !important;
    }}
    
    [data-testid="stSidebar"] .stButton button {{
        background: var(--halle11-secondary) !important;
        color: #1A1A1A !important;
        font-weight: 600 !important;
        border: none !important;
    }}
    
    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background: var(--card-bg);
        padding: 0.5rem;
        border-radius: 12px;
        border: 1px solid var(--card-border);
    }}
    
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        color: var(--text-primary);
    }}
    
    .stTabs [aria-selected="true"] {{
        background: var(--halle11-primary) !important;
        color: white !important;
    }}
    
    /* ===== SUCCESS/ERROR BOXES ===== */
    .success-box {{
        background: rgba(67, 160, 71, 0.15);
        border-left: 4px solid var(--halle11-success);
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
        color: var(--text-primary);
    }}
    
    .error-box {{
        background: rgba(229, 57, 53, 0.15);
        border-left: 4px solid var(--halle11-error);
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
        color: var(--text-primary);
    }}
    
    .info-box {{
        background: rgba(27, 94, 32, 0.15);
        border-left: 4px solid var(--halle11-primary);
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
        color: var(--text-primary);
    }}
    
    /* ===== DATAFRAME ===== */
    .stDataFrame {{
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px var(--shadow-color);
    }}
    
    /* ===== STREAMLIT NATIVE ELEMENTS (Theme-aware) ===== */
    
    /* Text und Labels */
    .stMarkdown, .stText, p, span, label {{
        color: {_text_primary} !important;
    }}
    
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {_text_secondary} !important;
    }}
    
    /* Metrics */
    [data-testid="stMetricValue"] {{
        color: {_text_primary} !important;
    }}
    
    [data-testid="stMetricLabel"] {{
        color: {_text_secondary} !important;
    }}
    
    [data-testid="stMetricDelta"] {{
        color: {_text_secondary} !important;
    }}
    
    /* Expander */
    .stExpander {{
        background: {_card_bg} !important;
        border: 1px solid {_card_border} !important;
        border-radius: 12px !important;
    }}
    
    .stExpander [data-testid="stExpanderToggleIcon"] {{
        color: {_text_primary} !important;
    }}
    
    .stExpander summary {{
        color: {_text_primary} !important;
    }}
    
    /* Info/Success/Error Boxes */
    [data-testid="stAlert"] {{
        background: {_card_bg} !important;
        border: 1px solid {_card_border} !important;
        color: {_text_primary} !important;
    }}
    
    /* Selectbox & Input */
    .stSelectbox label, .stTextInput label, .stNumberInput label {{
        color: {_text_primary} !important;
    }}
    
    .stSelectbox [data-baseweb="select"] {{
        background: {_card_bg} !important;
        border-color: {_card_border} !important;
    }}
    
    .stSelectbox [data-baseweb="select"] * {{
        color: {_text_primary} !important;
    }}
    
    /* Checkbox */
    .stCheckbox label {{
        color: {_text_primary} !important;
    }}
    
    /* Toggle */
    [data-testid="stToggle"] label {{
        color: {_text_primary} !important;
    }}
    
    /* Plotly Charts */
    .js-plotly-plot {{
        background: {_card_bg} !important;
    }}
    
    /* Main Container */
    [data-testid="stAppViewContainer"] {{
        background: {_app_bg} !important;
    }}
    
    [data-testid="stHeader"] {{
        background: {_app_bg} !important;
    }}
    
    /* DataFrame Headers und Zellen */
    .stDataFrame th {{
        background: {_card_bg} !important;
        color: {_text_primary} !important;
    }}
    
    .stDataFrame td {{
        background: {_card_bg} !important;
        color: {_text_primary} !important;
    }}
    
    /* ===== MOBILE RESPONSIVE ===== */
    @media (max-width: 768px) {{
        .main-header h1 {{
            font-size: 1.8rem;
        }}
        
        .metric-card {{
            padding: 0.8rem;
        }}
        
        .metric-card .value {{
            font-size: 1.4rem;
        }}
        
        .metric-card .icon {{
            font-size: 1.5rem;
        }}
        
        .date-display {{
            padding: 0.5rem 1rem;
            font-size: 0.9rem;
        }}
    }}
    
    /* ===== ANIMATIONS ===== */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    .animate-in {{
        animation: fadeIn 0.4s ease-out;
    }}
    
    @keyframes pulse {{
        0%, 100% {{ transform: scale(1); }}
        50% {{ transform: scale(1.05); }}
    }}
    
    .pulse {{
        animation: pulse 2s infinite;
    }}
    
    /* ===== KONFETTI ===== */
    {CONFETTI_CSS}
    
    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    
    ::-webkit-scrollbar-track {{
        background: var(--bg-subtle);
        border-radius: 4px;
    }}
    
    ::-webkit-scrollbar-thumb {{
        background: var(--halle11-primary-light);
        border-radius: 4px;
    }}
    
    ::-webkit-scrollbar-thumb:hover {{
        background: var(--halle11-primary);
    }}
</style>

<!-- Sound & Konfetti JavaScript -->
<script>
    {WHATSAPP_SOUND_JS}
    
    function triggerConfetti() {{
        const colors = ['#1B5E20', '#FFB300', '#FF5722', '#43A047', '#9C27B0'];
        for (let i = 0; i < 50; i++) {{
            setTimeout(() => {{
                const confetti = document.createElement('div');
                confetti.className = 'confetti';
                confetti.style.left = Math.random() * 100 + 'vw';
                confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
                confetti.style.borderRadius = Math.random() > 0.5 ? '50%' : '0';
                confetti.style.animationDuration = (2 + Math.random() * 2) + 's';
                document.body.appendChild(confetti);
                setTimeout(() => confetti.remove(), 4000);
            }}, i * 30);
        }}
    }}
    
    // Keep-alive ping every 5 minutes
    setInterval(function() {{
        const event = new Event('mousemove');
        document.dispatchEvent(event);
        console.log('🏔️ halle11 keep-alive ping');
    }}, 300000);
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
# ✅ NEU: Sound-Einstellung
if 'sound_enabled' not in st.session_state:
    st.session_state.sound_enabled = True
# ✅ Dark Mode - IMMER AN (stabiler)
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = True
st.session_state.dark_mode = True  # Force Dark Mode
# ✅ Monatsziel - aus Google Sheets laden (persistent!)
if 'monthly_goal' not in st.session_state:
    st.session_state.monthly_goal = get_monthly_goal()  # Lädt gespeicherten Wert

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

# ✅ NEUER STYLISCHER HEADER
render_header()

# ========================================
# SIDEBAR
# ========================================

st.sidebar.markdown("""
    <div style="text-align: center; padding: 1rem 0;">
        <span style="font-size: 2rem;">🏔️🎾</span>
        <h2 style="margin: 0.5rem 0 0 0;">halle11</h2>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

# ========================================
# 🔍 GLOBALE SUCHE
# ========================================

search_query = st.sidebar.text_input("🔍 Spieler suchen", placeholder="Name eingeben...", key="global_search")

if search_query and len(search_query) >= 2:
    all_buchungen = loadsheet("buchungen")
    if not all_buchungen.empty and 'Name' in all_buchungen.columns:
        # Suche in Namen (case-insensitive)
        search_lower = search_query.lower()
        matches = all_buchungen[all_buchungen['Name'].str.lower().str.contains(search_lower, na=False)]
        
        if not matches.empty:
            # ✅ FIX: Einfachere Aggregation ohne Categorical-Problem
            # Konvertiere analysis_date zu string falls nötig
            matches = matches.copy()
            matches['analysis_date_str'] = matches['analysis_date'].astype(str)
            matches['Betrag_num'] = pd.to_numeric(matches['Betrag'], errors='coerce').fillna(0)
            
            # Gruppiere manuell
            player_stats = []
            for name in matches['Name'].unique():
                player_data = matches[matches['Name'] == name]
                player_stats.append({
                    'Name': name,
                    'Buchungen': len(player_data),
                    'Letzte': player_data['analysis_date_str'].max(),
                    'Umsatz': player_data['Betrag_num'].sum()
                })
            
            unique_players = pd.DataFrame(player_stats)
            unique_players = unique_players.sort_values('Buchungen', ascending=False).head(5)
            
            st.sidebar.markdown("##### 🔎 Ergebnisse")
            for _, player in unique_players.iterrows():
                st.sidebar.markdown(f"""
                    <div style="background: rgba(255,255,255,0.1); padding: 0.5rem; border-radius: 8px; margin-bottom: 0.5rem;">
                        <strong>{player['Name']}</strong><br>
                        <span style="font-size: 0.8rem;">📋 {int(player['Buchungen'])}x · 📅 {player['Letzte']}</span>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.sidebar.info("Keine Treffer")

st.sidebar.markdown("---")

# ========================================
# EINSTELLUNGEN
# ========================================

with st.sidebar.expander("Einstellungen", expanded=False):
    # Sound Toggle
    st.session_state.sound_enabled = st.checkbox(
        "Sound bei WhatsApp", 
        value=st.session_state.sound_enabled
    )
    
    # Monatsziel aus Google Sheets laden
    current_goal = get_monthly_goal()
    new_goal = st.number_input(
        "Monatsziel (€)",
        min_value=1000,
        max_value=50000,
        value=int(current_goal),
        step=500
    )
    
    # Speichern wenn geändert
    if new_goal != current_goal:
        set_monthly_goal(new_goal)
        st.success("Gespeichert")
    
    st.session_state.monthly_goal = new_goal

st.sidebar.markdown("---")

# Dark Mode ist immer aktiv (stabiler)
st.sidebar.caption("🌙 Dark Mode aktiv")

st.sidebar.markdown("---")

p_file = st.sidebar.file_uploader("📄 Playtomic CSV", type=['csv'], key="playtomic")
c_file = st.sidebar.file_uploader("📄 Checkins CSV", type=['csv'], key="checkins")

if st.sidebar.button("🚀 Analysieren", use_container_width=True, type="primary") and p_file and c_file:
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
            'Product SKU': 'Product_SKU', 'Payment id': 'Payment id', 'Club payment id': 'Club payment id', 'Sport': 'Sport',
            'Payment method': 'Payment_method'  # ✅ NEU: Für Wallet-Erkennung
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

        # ✅ FIX: Club Wallet Zahlungen erkennen
        # Wenn Payment method = "Club wallet" → Spieler hat über Wallet bezahlt, NICHT Wellpass-relevant!
        is_wallet_payment = False
        if 'Payment_method' in playtomic_filtered.columns:
            is_wallet_payment = playtomic_filtered['Payment_method'].str.lower().str.contains('wallet', na=False)
        
        # ✅ Relevanz für BEIDE Sportarten (Padel UND Tennis), unter 6€
        # ABER: Wallet-Zahlungen sind NICHT relevant (die haben ja bezahlt!)
        playtomic_filtered['Relevant'] = (
            (
                ((playtomic_filtered['Betrag_num'] < 6) & (playtomic_filtered['Betrag_num'] > 0)) | 
                (playtomic_filtered['Betrag_num'] == 0)
            ) & 
            (~is_wallet_payment)  # ✅ Wallet-Zahlungen ausschließen
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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Tag", "📊 Monat", "👥 Spieler", "🔮 Prognose", "💬 Vielspieler"])

with tab1:
    dates = get_dates()
    
    if not dates:
        st.info("📄 Lade CSVs hoch! 🎾")
        st.stop()
    
    # ✅ STYLISCHE NAVIGATION
    curr_date = dates[st.session_state.day_idx]
    weekday_de = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    month_de = ['', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
    
    date_formatted = f"{weekday_de[curr_date.weekday()]}, {curr_date.day}. {month_de[curr_date.month]} {curr_date.year}"
    
    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: center; gap: 1rem; margin: 1rem 0;">
            <div class="date-display" style="flex: 0 0 auto;">
                📅 <strong>{date_formatted}</strong>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if st.button("◀ Zurück", use_container_width=True, key="prev_btn"):
            st.session_state.day_idx = min(st.session_state.day_idx + 1, len(dates) - 1)
            st.session_state.current_date = dates[st.session_state.day_idx].strftime("%Y-%m-%d")
            st.rerun()
    
    with col_info:
        st.markdown(f"""
            <div style="text-align: center; color: {COLORS['text_light']}; font-size: 0.9rem;">
                Tag {st.session_state.day_idx + 1} von {len(dates)}
            </div>
        """, unsafe_allow_html=True)
    
    with col_next:
        if st.button("Weiter ▶", use_container_width=True, key="next_btn"):
            st.session_state.day_idx = max(st.session_state.day_idx - 1, 0)
            st.session_state.current_date = dates[st.session_state.day_idx].strftime("%Y-%m-%d")
            st.rerun()
    
    with st.expander("📆 Springe zu Datum...", expanded=False):
        selected_date = st.selectbox("Datum:", options=dates, index=st.session_state.day_idx, format_func=lambda x: x.strftime("%d.%m.%Y"), key="date_jump")
        if st.button("✅ Springen", use_container_width=True):
            st.session_state.day_idx = dates.index(selected_date)
            st.session_state.current_date = selected_date.strftime("%Y-%m-%d")
            st.rerun()
    
    curr_date = dates[st.session_state.day_idx]
    st.session_state.current_date = curr_date.strftime("%Y-%m-%d")
    
    df = load_snapshot(st.session_state.current_date)
    ci_df = load_checkins_snapshot(st.session_state.current_date)
    
    # ✅ EINMAL LADEN für gesamten Tab (Rate Limit Fix!)
    corrections_df = loadsheet("corrections", ['key','date','behoben','timestamp'])
    
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
    
    
    # ✅ NEUE STYLISCHE METRIKEN-KARTEN
    st.markdown("---")
    
    # Berechne Prozent-Anteile
    padel_pct = (revenue['padel'] / gesamt_mit_wellpass * 100) if gesamt_mit_wellpass > 0 else 0
    tennis_pct = (revenue['tennis'] / gesamt_mit_wellpass * 100) if gesamt_mit_wellpass > 0 else 0
    extras_total = revenue['baelle'] + revenue['schlaeger']
    wellpass_pct = (wellpass_revenue / gesamt_mit_wellpass * 100) if gesamt_mit_wellpass > 0 else 0
    
    metrics_html = f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin: 1rem 0;">
        <div class="metric-card total animate-in">
            <div class="icon">💰</div>
            <div class="value">€{gesamt_mit_wellpass:.2f}</div>
            <div class="label">Gesamt</div>
            <div class="delta {'positive' if delta_pct >= 0 else 'negative'}">{delta_pct:+.0f}% vs. Vorwoche</div>
        </div>
        <div class="metric-card padel animate-in" style="animation-delay: 0.1s;">
            <div class="icon">🟠</div>
            <div class="value">€{revenue['padel']:.2f}</div>
            <div class="label">Padel</div>
            <div class="delta positive">{padel_pct:.0f}% Anteil</div>
        </div>
        <div class="metric-card tennis animate-in" style="animation-delay: 0.2s;">
            <div class="icon">🟢</div>
            <div class="value">€{revenue['tennis']:.2f}</div>
            <div class="label">Tennis</div>
            <div class="delta positive">{tennis_pct:.0f}% Anteil</div>
        </div>
        <div class="metric-card extras animate-in" style="animation-delay: 0.3s;">
            <div class="icon">🏓</div>
            <div class="value">€{extras_total:.2f}</div>
            <div class="label">Extras</div>
        </div>
        <div class="metric-card wellpass animate-in" style="animation-delay: 0.4s;">
            <div class="icon">💳</div>
            <div class="value">€{wellpass_revenue:.2f}</div>
            <div class="label">Wellpass</div>
            <div class="delta positive">{wellpass_unique_checkins} Check-ins</div>
        </div>
    </div>
    """
    st.markdown(metrics_html, unsafe_allow_html=True)
    
    # ✅ STATISTIK-BADGES
    relevant_count = len(df[df['Relevant'] == 'Ja'])
    fehler_count = len(df[df['Fehler'] == 'Ja'])
    checkin_count = len(ci_df) if ci_df is not None else 0
    
    stats_html = f"""
    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: center; margin: 1rem 0;">
        <span class="status-badge">{len(df)} Buchungen</span>
        <span class="status-badge">{relevant_count} Relevant</span>
        <span class="status-badge {'error' if fehler_count > 0 else 'success'}">{fehler_count} Fehler</span>
        <span class="status-badge">{checkin_count} Check-ins</span>
    </div>
    """
    st.markdown(stats_html, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ✅ ZWEI LISTEN MIT STATUS-BADGE VOR DEM NAMEN
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("**Buchungen (Relevant)**")
        rv = df[df['Relevant'] == 'Ja'].sort_values('Name').copy()
        
        if not rv.empty:
            # Toggle: Nur Probleme anzeigen
            show_only_problems = st.checkbox("Nur Probleme", value=True, key="hide_green_bookings")
            
            # ✅ Verwende bereits geladene corrections (Rate Limit Fix!)
            behoben_keys = set()
            if not corrections_df.empty and 'key' in corrections_df.columns:
                # Robuster Check für Boolean/String
                for _, c_row in corrections_df.iterrows():
                    behoben_val = c_row.get('behoben', False)
                    # Check für True, 'True', 'true', 1, '1'
                    is_behoben = behoben_val in [True, 'True', 'true', 1, '1', 'TRUE']
                    if is_behoben and pd.notna(c_row.get('key')):
                        behoben_keys.add(str(c_row['key']))
            
            # Status-Badge vor Namen - mit Behoben-Check
            def add_status_badge(row):
                if row['Fehler'] == 'Ja':
                    # Prüfe ob bereits behoben
                    key = f"{row['Name_norm']}_{row['Datum']}_{row['Betrag']}"
                    if key in behoben_keys:
                        return f"🟢 {row['Name']}"  # Behoben = grün
                    else:
                        return f"🔴 {row['Name']}"  # Offen = rot
                else:
                    return f"🟢 {row['Name']}"
            
            # Prüfe ob Problem noch offen (für Filter)
            def is_open_problem(row):
                if row['Fehler'] != 'Ja':
                    return False
                key = f"{row['Name_norm']}_{row['Datum']}_{row['Betrag']}"
                return key not in behoben_keys
            
            rv['Spieler'] = rv.apply(add_status_badge, axis=1)
            rv['_is_problem'] = rv.apply(is_open_problem, axis=1)
            
            # Filtere wenn Toggle aktiv - zeige nur OFFENE Probleme (nicht behobene)
            if show_only_problems:
                rv_display = rv[rv['_is_problem'] == True].copy()
                hidden_count = len(rv) - len(rv_display)
            else:
                rv_display = rv.copy()
                hidden_count = 0
            
            # Sport-Icon
            if 'Sport' in rv_display.columns:
                rv_display['S'] = rv_display['Sport'].apply(lambda x: 'P' if str(x).upper() == 'PADEL' else ('T' if str(x).upper() == 'TENNIS' else ''))
            
            display_cols = ['Spieler', 'Betrag']
            if 'Service_Zeit' in rv_display.columns:
                display_cols.append('Service_Zeit')
            if 'S' in rv_display.columns:
                display_cols.append('S')
            
            if not rv_display.empty:
                # Dynamische Höhe - alle Zeilen sichtbar
                row_height = 35
                header_height = 40
                table_height = min(len(rv_display) * row_height + header_height, 1200)
                
                st.dataframe(rv_display[display_cols], use_container_width=True, hide_index=True, height=table_height)
            else:
                st.success("Alle OK!")
            
            # Caption mit Info über ausgeblendete
            if hidden_count > 0:
                st.caption(f"{hidden_count} OK/behoben ausgeblendet · {len(rv_display)} offen")
            else:
                st.caption("grün = OK/behoben · rot = offen")
        else:
            st.info("Keine relevanten Buchungen")
    
    with col_right:
        st.markdown("**Wellpass Check-ins**")
        
        if ci_df is not None and not ci_df.empty:
            ci_view = ci_df.sort_values('Name').copy()
            
            # Toggle: Nur Probleme anzeigen
            show_only_ci_problems = st.checkbox("Nur Probleme", value=True, key="hide_green_checkins")
            
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
                st.caption(f"Buchung vorhanden = grün · Keine Buchung = rot")
        else:
            st.info("Keine Check-ins")
    
    st.markdown("---")
    
    # FEHLER-BEREICH (wie Padel Port - funktioniert!)
    fehler = df[df['Fehler'] == 'Ja'].copy()
    if not fehler.empty:
        mapping = load_name_mapping()
        rejected_matches = load_rejected_matches()
        corr = corrections_df
        
        # Fehler-Daten sammeln
        fehler_data = []
        for idx, row in fehler.iterrows():
            key = f"{row['Name_norm']}_{row['Datum']}_{row['Betrag']}"
            
            is_behoben = False
            if not corr.empty and 'key' in corr.columns:
                match_corr = corr[corr['key'] == key]
                if not match_corr.empty:
                    is_behoben = is_behoben_value(match_corr.iloc[0].get('behoben'))
            
            whatsapp_sent_time = get_whatsapp_sent_time(row)
            customer_data = get_customer_data(row['Name'])
            
            telefon = 'N/A'
            if customer_data and customer_data.get('phone_number') and customer_data['phone_number'] != 'Nicht verfügbar':
                tel = str(customer_data['phone_number'])
                telefon = tel[:15] + '...' if len(tel) > 15 else tel
            
            fehler_data.append({
                'Status': '✅' if is_behoben else '🔴',
                'Name': row['Name'],
                'Betrag': f"€{row['Betrag']}",
                'Zeit': row.get('Service_Zeit', 'N/A'),
                'Telefon': telefon,
                'WhatsApp': '✅ ' + whatsapp_sent_time.strftime("%d.%m. %H:%M") if whatsapp_sent_time else '❌',
                '_key': key,
                '_row': row,
                '_is_behoben': is_behoben
            })
        
        # Zähle offen/behoben
        open_count = len([f for f in fehler_data if f['Status'] == '🔴'])
        fixed_count = len([f for f in fehler_data if f['Status'] == '✅'])
        
        st.subheader(f"📋 Fehler ({open_count} offen · {fixed_count} behoben)")
        
        # DataFrame-Übersicht
        fehler_df = pd.DataFrame(fehler_data)
        st.dataframe(
            fehler_df[['Status', 'Name', 'Betrag', 'Zeit', 'Telefon', 'WhatsApp']],
            use_container_width=True,
            hide_index=True,
            height=min(len(fehler_df) * 35 + 38, 400)
        )
        
        st.markdown("---")
        st.markdown("### 🔧 Fehler bearbeiten")
        
        # Selectbox zur Auswahl
        fehler_options = [f"{f['Status']} {f['Name']} | {f['Betrag']} | {f['Zeit']}" for f in fehler_data]
        
        selected_fehler_name = st.selectbox(
            "Fehler auswählen:",
            options=fehler_options,
            key="fehler_selector"
        )
        
        selected_idx = fehler_options.index(selected_fehler_name)
        selected_fehler = fehler_data[selected_idx]
        
        row = selected_fehler['_row']
        key = selected_fehler['_key']
        is_behoben = selected_fehler['_is_behoben']
        whatsapp_sent_time = get_whatsapp_sent_time(row)
        
        st.markdown("---")
        
        # Info-Bereich
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.markdown(f"**🧑 {row['Name']}**")
            st.caption(f"⏰ {row.get('Service_Zeit', 'N/A')} | 💰 €{row['Betrag']} | 📅 {row['Datum']}")
            if whatsapp_sent_time:
                st.caption(f"✅ WhatsApp: {whatsapp_sent_time.strftime('%d.%m. %H:%M')}")
        
        with col2:
            customer_data = get_customer_data(row['Name'])
            if customer_data:
                st.caption(f"📱 {customer_data.get('phone_number', 'N/A')}")
                email = customer_data.get('email', 'N/A')
                st.caption(f"📧 {email[:30]}..." if len(str(email)) > 30 else f"📧 {email}")
            else:
                st.caption("⚠️ Nicht im Customer-Sheet")
        
        with col3:
            if not is_behoben:
                if st.button("✅ Behoben", key=f"fix_{key}", type="primary", use_container_width=True):
                    if not corr.empty and 'key' in corr.columns:
                        corr = corr[corr['key'] != key]
                    corr = pd.concat([corr, pd.DataFrame([{
                        'key': key,
                        'date': st.session_state.current_date,
                        'behoben': True,
                        'timestamp': datetime.now().isoformat()
                    }])], ignore_index=True)
                    savesheet(corr, "corrections")
                    loadsheet.clear()
                    st.rerun()
            else:
                if st.button("🔄 Öffnen", key=f"reopen_{key}", use_container_width=True):
                    if not corr.empty and 'key' in corr.columns:
                        corr = corr[corr['key'] != key]
                        savesheet(corr, "corrections")
                    loadsheet.clear()
                    st.rerun()
        
        # WhatsApp Buttons
        col_wa1, col_wa2 = st.columns(2)
        with col_wa1:
            if st.button("📱 WhatsApp senden", key=f"wa_{key}", use_container_width=True, disabled=whatsapp_sent_time is not None):
                send_wellpass_whatsapp_to_player(row)
        with col_wa2:
            if st.button("🧪 Test WA", key=f"test_{key}", use_container_width=True):
                send_wellpass_whatsapp_test(row)
        
        # Name-Matching (nur wenn nicht behoben)
        if not is_behoben:
            with st.expander("🔗 Name-Zuordnung", expanded=False):
                render_name_matching_interface(row, ci_df, mapping, rejected_matches, fehler)
    else:
        st.success("✅ Keine offenen Fehler! 🎉")
        trigger_confetti()
    
    # ✅ OFFENE FEHLER DER LETZTEN 5 TAGE
    st.markdown("---")
    with st.expander("📋 Offene Fehler der letzten 5 Tage", expanded=False):
        # Lade Buchungen (corrections schon geladen)
        all_buchungen = loadsheet("buchungen")
        all_corrections = corrections_df  # ✅ Verwende bereits geladene corrections
        
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
                            is_behoben = is_behoben_value(match_corr.iloc[0].get('behoben'))
                    
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
                                    corr = corrections_df.copy()  # ✅ Verwende bereits geladene corrections
                                    if not corr.empty and 'key' in corr.columns:
                                        corr = corr[corr['key'] != f['_key']]
                                    corr = pd.concat([corr, pd.DataFrame([{
                                        'key': f['_key'], 
                                        'date': f['Datum'], 
                                        'behoben': True, 
                                        'timestamp': datetime.now().isoformat()
                                    }])], ignore_index=True)
                                    savesheet(corr, "corrections")
                                    loadsheet.clear()  # ✅ Cache leeren!
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
    st.markdown("### 📊 Monat")
    
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
    
    # ========================================
    # 🎯 UMSATZ-ZIEL FORTSCHRITT (Ladebalken)
    # ========================================
    
    monthly_goal = st.session_state.get('monthly_goal', 8000)
    progress_pct = min((gesamt_umsatz / monthly_goal) * 100, 100) if monthly_goal > 0 else 0
    remaining = max(monthly_goal - gesamt_umsatz, 0)
    
    # Berechne Tage im Monat und vergangene Tage
    days_in_month = last_day.day
    if selected_year == today.year and selected_month == today.month:
        days_passed = today.day
    elif date(selected_year, selected_month, 1) < today:
        days_passed = days_in_month  # Monat ist vorbei
    else:
        days_passed = 0  # Zukunft
    
    expected_pct = (days_passed / days_in_month * 100) if days_in_month > 0 else 0
    on_track = progress_pct >= expected_pct
    
    # Prognose für Monatsende
    if days_passed > 0:
        daily_avg = gesamt_umsatz / days_passed
        projected_total = daily_avg * days_in_month
    else:
        projected_total = 0
    
    # Progress Bar Farbe & Status
    if progress_pct >= 100:
        bar_color = COLORS['success']
        status_emoji = "🎉"
        status_text = "ZIEL ERREICHT!"
    elif on_track:
        bar_color = COLORS['primary_light']
        status_emoji = "✅"
        status_text = "Im Plan"
    else:
        bar_color = COLORS['warning']
        status_emoji = "⚠️"
        status_text = f"Noch €{remaining:.0f}"
    
    # ========================================
    # 📊 FORTSCHRITTSBALKEN (native Streamlit)
    # ========================================
    
    st.subheader(f"🎯 Monatsziel: €{monthly_goal:,.0f}")
    
    # Info-Zeile
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.write(f"**€{gesamt_umsatz:,.2f}** von €{monthly_goal:,.0f}")
    with col_info2:
        st.write(f"**{status_emoji} {progress_pct:.1f}%** - {status_text}")
    
    # Native Streamlit Progress Bar
    st.progress(min(progress_pct / 100, 1.0))
    
    # Info unter dem Balken
    st.caption(f"Tag {days_passed} von {days_in_month} | Soll: {expected_pct:.0f}% | Ist: {progress_pct:.0f}%")
    
    # Kompakte Stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Aktuell", f"€{gesamt_umsatz:,.0f}", f"{progress_pct:.0f}%")
    with col2:
        st.metric("🎯 Noch offen", f"€{remaining:,.0f}", f"-{100-progress_pct:.0f}%")
    with col3:
        st.metric("📈 Prognose", f"€{projected_total:,.0f}", "Monatsende")
    with col4:
        tempo = "🟢 Im Plan" if on_track else "🟡 Aufholen"
        st.metric("📊 Status", tempo, f"Tag {days_passed}/{days_in_month}")
    
    st.markdown("---")
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("💰 Gesamt", f"€{gesamt_umsatz:.2f}")
    with col2:
        st.metric("🏓 Padel", f"€{revenue_month['padel']:.2f}")
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
# TAB 3: SPIELER-ANALYTICS
# ========================================

with tab3:
    st.markdown("### 👥 Spieler-Analytics")
    
    # Zeitraum-Auswahl
    col_period, col_info = st.columns([2, 3])
    with col_period:
        analysis_days = st.selectbox(
            "Zeitraum",
            options=[7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"Letzte {x} Tage",
            key="analytics_period"
        )
    
    # Lade alle Buchungsdaten
    all_buchungen = loadsheet("buchungen")
    
    if all_buchungen.empty or 'analysis_date' not in all_buchungen.columns:
        st.warning("⚠️ Keine Buchungsdaten vorhanden. Bitte erst CSVs hochladen!")
    else:
        # Filtere auf Zeitraum
        today = date.today()
        start_date = today - timedelta(days=analysis_days)
        
        all_buchungen['date_obj'] = pd.to_datetime(all_buchungen['analysis_date'], errors='coerce').dt.date
        period_data = all_buchungen[all_buchungen['date_obj'] >= start_date].copy()
        
        if period_data.empty:
            st.info(f"📭 Keine Daten in den letzten {analysis_days} Tagen")
        else:
            # Filtere Mitarbeiter raus
            if 'Mitarbeiter' in period_data.columns:
                period_data = period_data[period_data['Mitarbeiter'] != 'Ja']
            
            with col_info:
                unique_players = period_data['Name'].nunique()
                total_bookings = len(period_data)
                st.info(f"📊 {total_bookings} Buchungen von {unique_players} Spielern")
            
            st.markdown("---")
            
            # ========================================
            # SPIELER-STATISTIKEN BERECHNEN
            # ========================================
            
            # Gruppiere nach Spieler - sichere Methode ohne iloc[0] Problem
            if period_data.empty or 'Name' not in period_data.columns:
                # Leere DataFrame wenn keine Daten
                player_stats = pd.DataFrame(columns=['Name', 'Buchungen', 'Umsatz', 'Relevante', 'Mit_Checkin', 'Fehler', 'Ist_Wellpass', 'Checkin_Quote', 'Pro_Woche'])
            else:
                # Sichere Aggregation ohne lambda mit iloc
                stats_list = []
                for name, group in period_data.groupby('Name'):
                    if len(group) == 0:
                        continue
                    stats_list.append({
                        'Name': name,
                        'Buchungen': len(group),
                        'Umsatz': pd.to_numeric(group['Betrag'], errors='coerce').sum(),
                        'Relevante': (group['Relevant'] == 'Ja').sum(),
                        'Mit_Checkin': (group['Check-in'] == 'Ja').sum(),
                        'Fehler': (group['Fehler'] == 'Ja').sum(),
                        'Ist_Wellpass': (group['Relevant'] == 'Ja').any()
                    })
                
                if stats_list:
                    player_stats = pd.DataFrame(stats_list)
                else:
                    player_stats = pd.DataFrame(columns=['Name', 'Buchungen', 'Umsatz', 'Relevante', 'Mit_Checkin', 'Fehler', 'Ist_Wellpass'])
            
            # Check-in Quote berechnen (nur wenn Daten vorhanden)
            if not player_stats.empty and 'Relevante' in player_stats.columns:
                player_stats['Checkin_Quote'] = (
                    player_stats['Mit_Checkin'] / player_stats['Relevante'].replace(0, 1) * 100
                ).round(1)
                
                # Spiele pro Woche
                weeks = max(analysis_days / 7, 1)
                player_stats['Pro_Woche'] = (player_stats['Buchungen'] / weeks).round(1)
            else:
                player_stats['Checkin_Quote'] = 0
                player_stats['Pro_Woche'] = 0
            
            # ========================================
            # ÜBERSICHTS-METRIKEN
            # ========================================
            
            # Wellpass vs Normal Vergleich
            wellpass_players = player_stats[player_stats['Ist_Wellpass'] == True]
            normal_players = player_stats[player_stats['Ist_Wellpass'] == False]
            
            avg_bookings_wellpass = wellpass_players['Buchungen'].mean() if len(wellpass_players) > 0 else 0
            avg_bookings_normal = normal_players['Buchungen'].mean() if len(normal_players) > 0 else 0
            
            # Stammkunden (≥4 Buchungen im Zeitraum)
            stammkunden = player_stats[player_stats['Buchungen'] >= 4]
            
            # Problem-Spieler (<50% Check-in Quote bei mind. 2 relevanten Buchungen)
            problem_players = player_stats[
                (player_stats['Checkin_Quote'] < 50) & 
                (player_stats['Relevante'] >= 2)
            ]
            
            # Metriken als native Streamlit-Komponenten
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("👥 Spieler gesamt", len(player_stats))
            with col2:
                st.metric("🏠 Stammkunden", len(stammkunden), "≥4 Buchungen")
            with col3:
                st.metric("💳 Wellpass", len(wellpass_players), f"Ø {avg_bookings_wellpass:.1f} Spiele")
            with col4:
                st.metric("💰 Vollzahler", len(normal_players), f"Ø {avg_bookings_normal:.1f} Spiele")
            with col5:
                st.metric("⚠️ Problem-Spieler", len(problem_players), "<50% Check-in")
            
            st.markdown("---")
            
            # ========================================
            # TOP SPIELER RANKINGS
            # ========================================
            
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.markdown("##### 🏆 Top 10 - Meiste Buchungen")
                top_bookings = player_stats.nlargest(10, 'Buchungen')[['Name', 'Buchungen', 'Pro_Woche', 'Umsatz']]
                top_bookings['Umsatz'] = top_bookings['Umsatz'].apply(lambda x: f"€{x:.2f}")
                top_bookings.columns = ['Spieler', 'Buchungen', 'Pro Woche', 'Umsatz']
                st.dataframe(top_bookings, use_container_width=True, hide_index=True)
                
            with col_right:
                st.markdown("##### 💰 Top 10 - Höchster Umsatz")
                top_revenue = player_stats.nlargest(10, 'Umsatz')[['Name', 'Umsatz', 'Buchungen']]
                top_revenue['Umsatz'] = top_revenue['Umsatz'].apply(lambda x: f"€{x:.2f}")
                top_revenue.columns = ['Spieler', 'Umsatz', 'Buchungen']
                st.dataframe(top_revenue, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # ========================================
            # WELLPASS VS VOLLZAHLER VERGLEICH
            # ========================================
            
            st.markdown("##### 🆚 Wellpass vs. Vollzahler")
            
            comparison_data = {
                'Kategorie': ['Wellpass-Spieler', 'Vollzahler'],
                'Anzahl Spieler': [len(wellpass_players), len(normal_players)],
                'Ø Buchungen': [f"{avg_bookings_wellpass:.1f}", f"{avg_bookings_normal:.1f}"],
                'Ø Pro Woche': [
                    f"{wellpass_players['Pro_Woche'].mean():.1f}" if len(wellpass_players) > 0 else "0",
                    f"{normal_players['Pro_Woche'].mean():.1f}" if len(normal_players) > 0 else "0"
                ],
                'Total Buchungen': [
                    wellpass_players['Buchungen'].sum() if len(wellpass_players) > 0 else 0,
                    normal_players['Buchungen'].sum() if len(normal_players) > 0 else 0
                ]
            }
            comparison_df = pd.DataFrame(comparison_data)
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)
            
            # Visualisierung
            if len(wellpass_players) > 0 or len(normal_players) > 0:
                fig = go.Figure(data=[
                    go.Bar(
                        name='Wellpass', 
                        x=['Ø Buchungen', 'Ø Pro Woche'], 
                        y=[avg_bookings_wellpass, wellpass_players['Pro_Woche'].mean() if len(wellpass_players) > 0 else 0],
                        marker_color=COLORS['primary']
                    ),
                    go.Bar(
                        name='Vollzahler', 
                        x=['Ø Buchungen', 'Ø Pro Woche'], 
                        y=[avg_bookings_normal, normal_players['Pro_Woche'].mean() if len(normal_players) > 0 else 0],
                        marker_color=COLORS['secondary']
                    )
                ])
                fig.update_layout(
                    barmode='group', 
                    height=300,
                    title="Buchungsverhalten im Vergleich",
                    yaxis_title="Anzahl"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            # ========================================
            # PROBLEM-SPIELER LISTE
            # ========================================
            
            if len(problem_players) > 0:
                st.markdown("##### ⚠️ Problem-Spieler (Check-in Quote < 50%)")
                st.caption("Diese Spieler vergessen häufig den Wellpass Check-in")
                
                problem_display = problem_players[['Name', 'Relevante', 'Mit_Checkin', 'Checkin_Quote', 'Fehler']].copy()
                problem_display.columns = ['Spieler', 'Relevante Buchungen', 'Mit Check-in', 'Quote %', 'Offene Fehler']
                problem_display = problem_display.sort_values('Quote %')
                
                # Färbung basierend auf Quote
                st.dataframe(
                    problem_display, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Quote %": st.column_config.ProgressColumn(
                            "Quote %",
                            help="Check-in Quote",
                            min_value=0,
                            max_value=100,
                        ),
                    }
                )
            else:
                render_success_box("Keine Problem-Spieler! Alle haben gute Check-in Quoten 🎉")
            
            st.markdown("---")
            
            # ========================================
            # STAMMKUNDEN ÜBERSICHT
            # ========================================
            
            st.markdown("##### 🏠 Stammkunden (≥4 Buchungen)")
            
            if len(stammkunden) > 0:
                stammkunden_display = stammkunden[['Name', 'Buchungen', 'Pro_Woche', 'Umsatz', 'Checkin_Quote']].copy()
                stammkunden_display['Umsatz'] = stammkunden_display['Umsatz'].apply(lambda x: f"€{x:.2f}")
                stammkunden_display.columns = ['Spieler', 'Buchungen', 'Pro Woche', 'Umsatz', 'Check-in %']
                stammkunden_display = stammkunden_display.sort_values('Buchungen', ascending=False)
                
                st.dataframe(stammkunden_display, use_container_width=True, hide_index=True)
                
                # Stammkunden-Anteil am Umsatz
                stammkunden_umsatz = player_stats[player_stats['Buchungen'] >= 4]['Umsatz'].sum()
                gesamt_umsatz = player_stats['Umsatz'].sum()
                stammkunden_anteil = (stammkunden_umsatz / gesamt_umsatz * 100) if gesamt_umsatz > 0 else 0
                
                st.success(f"💡 **{len(stammkunden)} Stammkunden** ({len(stammkunden)/len(player_stats)*100:.0f}% aller Spieler) generieren **€{stammkunden_umsatz:.2f}** ({stammkunden_anteil:.0f}% des Umsatzes)")
            else:
                st.info("Noch keine Stammkunden im gewählten Zeitraum")
            
            st.markdown("---")
            
            # ========================================
            # ALLE SPIELER (ausklappbar)
            # ========================================
            
            with st.expander(f"📋 Alle {len(player_stats)} Spieler anzeigen", expanded=False):
                all_players_display = player_stats[['Name', 'Buchungen', 'Pro_Woche', 'Umsatz', 'Checkin_Quote', 'Ist_Wellpass']].copy()
                all_players_display['Umsatz'] = all_players_display['Umsatz'].apply(lambda x: f"€{x:.2f}")
                all_players_display['Typ'] = all_players_display['Ist_Wellpass'].apply(lambda x: '💳 Wellpass' if x else '💰 Vollzahler')
                all_players_display = all_players_display[['Name', 'Buchungen', 'Pro_Woche', 'Umsatz', 'Checkin_Quote', 'Typ']]
                all_players_display.columns = ['Spieler', 'Buchungen', 'Pro Woche', 'Umsatz', 'Check-in %', 'Typ']
                all_players_display = all_players_display.sort_values('Buchungen', ascending=False)
                
                st.dataframe(all_players_display, use_container_width=True, hide_index=True, height=600)


# ========================================
# TAB 4: PROGNOSEN & KALENDER
# ========================================

with tab4:
    st.markdown("### 🔮 Prognosen & Kalender")
    
    # Lade Daten
    all_buchungen = loadsheet("buchungen")
    all_checkins = loadsheet("checkins")
    
    if all_buchungen.empty or 'analysis_date' not in all_buchungen.columns:
        st.warning("⚠️ Keine Buchungsdaten vorhanden!")
    else:
        all_buchungen['date_obj'] = pd.to_datetime(all_buchungen['analysis_date'], errors='coerce').dt.date
        all_buchungen = all_buchungen.dropna(subset=['date_obj'])
        
        # Berechne Betrag numerisch
        all_buchungen['Betrag_num'] = pd.to_numeric(all_buchungen['Betrag'], errors='coerce').fillna(0)
        
        # Wochentag hinzufügen (0=Montag, 6=Sonntag)
        all_buchungen['Wochentag'] = pd.to_datetime(all_buchungen['analysis_date']).dt.dayofweek
        
        # Deutsche Wochentag-Namen
        wochentag_namen = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
        all_buchungen['Wochentag_Name'] = all_buchungen['Wochentag'].apply(lambda x: wochentag_namen[x])
        
        # Uhrzeit extrahieren (falls vorhanden)
        if 'Service_Zeit' in all_buchungen.columns:
            all_buchungen['Stunde'] = all_buchungen['Service_Zeit'].apply(
                lambda x: int(str(x).split(':')[0]) if pd.notna(x) and ':' in str(x) else None
            )
        
        st.markdown("---")
        
        # ========================================
        # 📅 KALENDER-VIEW
        # ========================================
        
        st.markdown("#### 📅 Kalender-Übersicht")
        
        # Monat auswählen
        today = date.today()
        col_year, col_month = st.columns(2)
        with col_year:
            cal_year = st.selectbox("Jahr", options=list(range(2024, today.year + 1)), index=list(range(2024, today.year + 1)).index(today.year), key="cal_year")
        with col_month:
            month_names_cal = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
            cal_month = st.selectbox("Monat", options=list(range(1, 13)), index=today.month - 1, format_func=lambda x: month_names_cal[x-1], key="cal_month")
        
        # Kalender-Daten berechnen
        first_day = date(cal_year, cal_month, 1)
        last_day = date(cal_year, cal_month, monthrange(cal_year, cal_month)[1])
        
        # Tages-Statistiken für den Monat
        month_data = all_buchungen[(all_buchungen['date_obj'] >= first_day) & (all_buchungen['date_obj'] <= last_day)]
        
        daily_stats = month_data.groupby('date_obj').agg({
            'Betrag_num': 'sum',
            'Name': 'count',
            'Fehler': lambda x: (x == 'Ja').sum()
        }).reset_index()
        daily_stats.columns = ['Datum', 'Umsatz', 'Buchungen', 'Fehler']
        
        # Wellpass Check-ins pro Tag
        if not all_checkins.empty and 'analysis_date' in all_checkins.columns:
            all_checkins['date_obj'] = pd.to_datetime(all_checkins['analysis_date'], errors='coerce').dt.date
            month_checkins = all_checkins[(all_checkins['date_obj'] >= first_day) & (all_checkins['date_obj'] <= last_day)]
            checkin_counts = month_checkins.groupby('date_obj')['Name_norm'].nunique().reset_index()
            checkin_counts.columns = ['Datum', 'Checkins']
            daily_stats = daily_stats.merge(checkin_counts, on='Datum', how='left')
            daily_stats['Checkins'] = daily_stats['Checkins'].fillna(0).astype(int)
        else:
            daily_stats['Checkins'] = 0
        
        # Wellpass-Wert hinzufügen
        daily_stats['Wellpass_Umsatz'] = daily_stats['Checkins'] * WELLPASS_WERT
        daily_stats['Gesamt'] = daily_stats['Umsatz'] + daily_stats['Wellpass_Umsatz']
        
        # Kalender als Grid darstellen
        # Erster Tag des Monats - welcher Wochentag?
        first_weekday = first_day.weekday()  # 0=Montag
        
        # Kalender-Grid erstellen
        st.markdown(f"**{month_names_cal[cal_month-1]} {cal_year}**")
        
        # Wochentag-Header
        header_cols = st.columns(7)
        for i, day_name in enumerate(['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']):
            header_cols[i].markdown(f"<div style='text-align: center; font-weight: bold; color: var(--text-secondary);'>{day_name}</div>", unsafe_allow_html=True)
        
        # Kalender-Tage
        current_day = 1
        max_day = last_day.day
        
        # Berechne Anzahl Wochen
        total_cells = first_weekday + max_day
        num_weeks = (total_cells + 6) // 7
        
        for week in range(num_weeks):
            cols = st.columns(7)
            for weekday in range(7):
                cell_num = week * 7 + weekday
                day_num = cell_num - first_weekday + 1
                
                if day_num < 1 or day_num > max_day:
                    cols[weekday].markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)
                else:
                    current_date = date(cal_year, cal_month, day_num)
                    day_data = daily_stats[daily_stats['Datum'] == current_date]
                    
                    if not day_data.empty:
                        umsatz = day_data.iloc[0]['Gesamt']
                        buchungen = day_data.iloc[0]['Buchungen']
                        fehler = day_data.iloc[0]['Fehler']
                        
                        # Farbe basierend auf Umsatz
                        if umsatz >= 500:
                            bg_color = "rgba(67, 160, 71, 0.3)"  # Grün
                            border_color = COLORS['success']
                        elif umsatz >= 200:
                            bg_color = "rgba(255, 179, 0, 0.3)"  # Gelb
                            border_color = COLORS['secondary']
                        elif umsatz > 0:
                            bg_color = "rgba(255, 87, 34, 0.2)"  # Orange
                            border_color = COLORS['accent']
                        else:
                            bg_color = "var(--card-bg)"
                            border_color = "var(--card-border)"
                        
                        fehler_dot = "🔴" if fehler > 0 else ""
                        
                        cols[weekday].markdown(f"""
                            <div style="
                                background: {bg_color}; 
                                border: 2px solid {border_color}; 
                                border-radius: 8px; 
                                padding: 0.3rem; 
                                text-align: center;
                                height: 80px;
                            ">
                                <div style="font-weight: bold; font-size: 1.1rem;">{day_num}</div>
                                <div style="font-size: 0.75rem; color: var(--text-primary);">€{umsatz:.0f}</div>
                                <div style="font-size: 0.65rem; color: var(--text-secondary);">{buchungen} 📋 {fehler_dot}</div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        # Tag ohne Daten (Zukunft oder keine Buchungen)
                        is_future = current_date > today
                        cols[weekday].markdown(f"""
                            <div style="
                                background: var(--card-bg); 
                                border: 1px dashed var(--card-border); 
                                border-radius: 8px; 
                                padding: 0.3rem; 
                                text-align: center;
                                height: 80px;
                                opacity: {'0.5' if is_future else '1'};
                            ">
                                <div style="font-weight: bold; font-size: 1.1rem; color: var(--text-secondary);">{day_num}</div>
                                <div style="font-size: 0.75rem; color: var(--text-secondary);">{'—' if is_future else '€0'}</div>
                            </div>
                        """, unsafe_allow_html=True)
        
        # Legende
        st.markdown("""
            <div style="display: flex; gap: 1rem; justify-content: center; margin-top: 1rem; flex-wrap: wrap;">
                <span style="font-size: 0.8rem;">🟢 ≥€500</span>
                <span style="font-size: 0.8rem;">🟡 €200-499</span>
                <span style="font-size: 0.8rem;">🟠 €1-199</span>
                <span style="font-size: 0.8rem;">⬜ €0 / keine Daten</span>
                <span style="font-size: 0.8rem;">🔴 = offene Fehler</span>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ========================================
        # 📈 WOCHENTAG-PROGNOSE
        # ========================================
        
        st.markdown("#### 📈 Wochentag-Prognose")
        st.caption("Basierend auf historischen Durchschnittswerten")
        
        # Durchschnitt pro Wochentag berechnen (letzte 8 Wochen)
        eight_weeks_ago = today - timedelta(weeks=8)
        recent_data = all_buchungen[all_buchungen['date_obj'] >= eight_weeks_ago]
        
        # Tages-Umsätze berechnen
        daily_revenue = recent_data.groupby(['date_obj', 'Wochentag', 'Wochentag_Name']).agg({
            'Betrag_num': 'sum',
            'Name': 'count'
        }).reset_index()
        daily_revenue.columns = ['Datum', 'Wochentag', 'Wochentag_Name', 'Umsatz', 'Buchungen']
        
        # Wellpass dazu
        if not all_checkins.empty:
            recent_checkins = all_checkins[all_checkins['date_obj'] >= eight_weeks_ago]
            checkin_daily = recent_checkins.groupby('date_obj')['Name_norm'].nunique().reset_index()
            checkin_daily.columns = ['Datum', 'Checkins']
            daily_revenue = daily_revenue.merge(checkin_daily, on='Datum', how='left')
            daily_revenue['Checkins'] = daily_revenue['Checkins'].fillna(0)
            daily_revenue['Wellpass'] = daily_revenue['Checkins'] * WELLPASS_WERT
            daily_revenue['Gesamt'] = daily_revenue['Umsatz'] + daily_revenue['Wellpass']
        else:
            daily_revenue['Gesamt'] = daily_revenue['Umsatz']
        
        # Durchschnitt pro Wochentag
        weekday_avg = daily_revenue.groupby(['Wochentag', 'Wochentag_Name']).agg({
            'Gesamt': 'mean',
            'Buchungen': 'mean',
            'Datum': 'count'  # Anzahl Datenpunkte
        }).reset_index()
        weekday_avg.columns = ['Wochentag', 'Wochentag_Name', 'Ø_Umsatz', 'Ø_Buchungen', 'Datenpunkte']
        weekday_avg = weekday_avg.sort_values('Wochentag')
        
        # Balkendiagramm
        fig_weekday = go.Figure()
        
        fig_weekday.add_trace(go.Bar(
            x=weekday_avg['Wochentag_Name'],
            y=weekday_avg['Ø_Umsatz'],
            marker_color=[COLORS['primary'] if i < 5 else COLORS['secondary'] for i in range(7)],
            text=[f"€{x:.0f}" for x in weekday_avg['Ø_Umsatz']],
            textposition='outside'
        ))
        
        fig_weekday.update_layout(
            title="Durchschnittlicher Umsatz pro Wochentag",
            xaxis_title="",
            yaxis_title="Ø Umsatz (€)",
            height=350,
            showlegend=False
        )
        
        st.plotly_chart(fig_weekday, use_container_width=True)
        
        # Prognose für aktuelle/nächste Woche
        st.markdown("##### 🎯 Prognose für diese Woche")
        
        # Berechne Start der aktuellen Woche (Montag)
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        
        prognose_data = []
        for i in range(7):
            day = monday + timedelta(days=i)
            day_name = wochentag_namen[i]
            avg_row = weekday_avg[weekday_avg['Wochentag'] == i]
            
            if not avg_row.empty:
                expected = avg_row.iloc[0]['Ø_Umsatz']
                expected_bookings = avg_row.iloc[0]['Ø_Buchungen']
            else:
                expected = 0
                expected_bookings = 0
            
            # Actual wenn Tag in der Vergangenheit
            actual = None
            if day <= today:
                day_actual = daily_revenue[daily_revenue['Datum'] == day]
                if not day_actual.empty:
                    actual = day_actual.iloc[0]['Gesamt']
            
            prognose_data.append({
                'Tag': day_name,
                'Datum': day.strftime('%d.%m.'),
                'Erwartet': f"€{expected:.0f}",
                'Tatsächlich': f"€{actual:.0f}" if actual is not None else "—",
                'Differenz': f"{((actual/expected)-1)*100:+.0f}%" if actual is not None and expected > 0 else "—",
                'Status': '✅' if day <= today else '🔮'
            })
        
        prognose_df = pd.DataFrame(prognose_data)
        st.dataframe(prognose_df, use_container_width=True, hide_index=True)
        
        # Wochen-Summe Prognose
        weekly_expected = weekday_avg['Ø_Umsatz'].sum()
        st.metric("📊 Erwarteter Wochen-Umsatz", f"€{weekly_expected:.0f}")
        
        st.markdown("---")
        
        # ========================================
        # ⏰ PEAK-ZEITEN HEATMAP
        # ========================================
        
        st.markdown("#### ⏰ Peak-Zeiten (Wann wird gespielt?)")
        
        if 'Stunde' in all_buchungen.columns:
            # Filtere auf gültige Stunden
            heatmap_data = all_buchungen[all_buchungen['Stunde'].notna()].copy()
            heatmap_data['Stunde'] = heatmap_data['Stunde'].astype(int)
            
            if not heatmap_data.empty:
                # Pivot-Tabelle: Wochentag × Stunde
                heatmap_pivot = heatmap_data.groupby(['Wochentag', 'Stunde']).size().reset_index(name='Buchungen')
                heatmap_matrix = heatmap_pivot.pivot(index='Stunde', columns='Wochentag', values='Buchungen').fillna(0)
                
                # Sicherstellen dass alle Wochentage vorhanden sind
                for i in range(7):
                    if i not in heatmap_matrix.columns:
                        heatmap_matrix[i] = 0
                heatmap_matrix = heatmap_matrix.reindex(columns=range(7))
                heatmap_matrix.columns = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
                
                # Heatmap erstellen
                fig_heatmap = go.Figure(data=go.Heatmap(
                    z=heatmap_matrix.values,
                    x=heatmap_matrix.columns,
                    y=[f"{h}:00" for h in heatmap_matrix.index],
                    colorscale=[
                        [0, '#F5F5F5'],
                        [0.25, '#C8E6C9'],
                        [0.5, '#81C784'],
                        [0.75, '#4CAF50'],
                        [1, '#1B5E20']
                    ],
                    hovertemplate='%{x} %{y}: %{z} Buchungen<extra></extra>'
                ))
                
                fig_heatmap.update_layout(
                    title="Buchungen nach Uhrzeit und Wochentag",
                    xaxis_title="",
                    yaxis_title="Uhrzeit",
                    height=400,
                    yaxis=dict(autorange='reversed')
                )
                
                st.plotly_chart(fig_heatmap, use_container_width=True)
                
                # Top 3 Peak-Zeiten
                top_peaks = heatmap_pivot.nlargest(3, 'Buchungen')
                peak_text = []
                for _, row in top_peaks.iterrows():
                    day_name = wochentag_namen[int(row['Wochentag'])]
                    peak_text.append(f"**{day_name} {int(row['Stunde'])}:00** ({int(row['Buchungen'])} Buchungen)")
                
                st.markdown(f"🔥 **Top Peak-Zeiten:** {' · '.join(peak_text)}")
            else:
                st.info("Keine Uhrzeit-Daten verfügbar")
        else:
            st.info("Keine Uhrzeit-Daten in den Buchungen")
        
        st.markdown("---")
        
        # ========================================
        # 🔄 WIEDERKEHRRATE
        # ========================================
        
        st.markdown("#### 🔄 Wiederkehr-Analyse")
        
        # Spieler die letzte Woche gespielt haben
        last_week_start = today - timedelta(days=14)
        last_week_end = today - timedelta(days=7)
        this_week_start = today - timedelta(days=7)
        
        last_week_players = set(all_buchungen[
            (all_buchungen['date_obj'] >= last_week_start) & 
            (all_buchungen['date_obj'] < last_week_end)
        ]['Name_norm'].unique())
        
        this_week_players = set(all_buchungen[
            (all_buchungen['date_obj'] >= this_week_start)
        ]['Name_norm'].unique())
        
        if len(last_week_players) > 0:
            returning = last_week_players.intersection(this_week_players)
            return_rate = len(returning) / len(last_week_players) * 100
            
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("📅 Spieler letzte Woche", len(last_week_players))
            with col_r2:
                st.metric("🔄 Davon wiedergekommen", len(returning))
            with col_r3:
                st.metric("📈 Wiederkehrrate", f"{return_rate:.0f}%")
            
            if return_rate >= 40:
                render_success_box(f"Sehr gute Wiederkehrrate! {return_rate:.0f}% kommen wieder")
            elif return_rate >= 25:
                st.info(f"Solide Wiederkehrrate von {return_rate:.0f}%")
            else:
                st.warning(f"Niedrige Wiederkehrrate ({return_rate:.0f}%)")
        else:
            st.info("Noch nicht genug Daten für Wiederkehr-Analyse (mind. 2 Wochen)")


# ========================================
# TAB 5: VIELSPIELER & WHATSAPP
# ========================================

with tab5:
    st.markdown("### 💬 Vielspieler-Kommunikation")
    st.caption("WhatsApp-Nachrichten an eure treuesten Spieler senden")
    
    # ========================================
    # NACHRICHTENVORLAGEN DEFINIEREN
    # ========================================
    
    WHATSAPP_TEMPLATES = {
        "danke": {
            "icon": "🎁",
            "title": "Danke für deine Treue",
            "template": """Servus {name}! 🏔️

Du bist einer unserer treuesten Spieler - {buchungen}x warst du diesen Monat bei uns am Berg!

Als kleines Dankeschön bekommst du beim nächsten Besuch einen Kaffee aufs Haus ☕

Bis bald in der halle11!
Dein halle11 Team""",
            "placeholders": ["{name}", "{buchungen}"]
        },
        "bewertung": {
            "icon": "⭐",
            "title": "Bitte um Bewertung",
            "template": """Hey {name}! 🎾

Wir hoffen, du hattest wieder eine super Session bei uns am Berg!

Würdest du uns mit einer Google-Bewertung unterstützen? Das würde uns mega helfen! ⭐⭐⭐⭐⭐

👉 [Google Review Link]

Vielen Dank!
Dein halle11 Team""",
            "placeholders": ["{name}"]
        },
        "event": {
            "icon": "🏔️",
            "title": "Event-Einladung",
            "template": """Servus {name}! 🎾

Am [DATUM] steigt unser nächstes Turnier am Berg!

Als Vielspieler bist du natürlich herzlich eingeladen.
Melde dich bis [DATUM] an und sichere dir deinen Platz!

Wir freuen uns auf dich! ⛰️
Dein halle11 Team""",
            "placeholders": ["{name}", "[DATUM]"]
        },
        "comeback": {
            "icon": "💰",
            "title": "Comeback-Rabatt",
            "template": """Hey {name}! 🏔️

Wir haben dich lang nicht mehr am Berg gesehen!

Hier ist ein 15% Comeback-Rabatt für dich: COMEBACK15
Gültig 14 Tage.

Wir freuen uns auf dein Comeback!
Dein halle11 Team""",
            "placeholders": ["{name}"]
        },
        "wellpass_reminder": {
            "icon": "📱",
            "title": "Wellpass Check-in Erinnerung",
            "template": """Servus {name}! 🏔️

Du hast heute um {zeit} bei uns gespielt - top! 🎾

Kleine Bitte: Wir haben deinen Wellpass-Check-In noch nicht im System. 
Wär klasse, wenn du ihn schnell nachholen könntest!

👉 QR-Code: [WELLPASS_QR_LINK]

Danke dir und bis bald am Berg! ⛰️
Dein halle11 Team""",
            "placeholders": ["{name}", "{zeit}"]
        },
        "geburtstag": {
            "icon": "🎂",
            "title": "Geburtstag",
            "template": """Happy Birthday, {name}! 🎉🏔️

Zu deinem Ehrentag schenken wir dir 20% auf deine nächste Buchung!
Code: BIRTHDAY2024

Feier schön und bis bald am Berg! 🎾
Dein halle11 Team""",
            "placeholders": ["{name}"]
        },
    }
    
    # ========================================
    # SPIELER-LISTE LADEN
    # ========================================
    
    buchungen = loadsheet("buchungen")
    vielspieler_list = []
    all_players_list = []
    
    if not buchungen.empty:
        buchungen['date_obj'] = pd.to_datetime(buchungen['analysis_date'], errors='coerce').dt.date
        cutoff = date.today() - timedelta(days=30)
        
        # Vielspieler (≥4 Wellpass-Buchungen in 30 Tagen)
        recent = buchungen[
            (buchungen['date_obj'] >= cutoff) & 
            (buchungen['Mitarbeiter'] != 'Ja') &
            (buchungen['Relevant'] == 'Ja')
        ]
        
        if not recent.empty:
            counts = recent.groupby('Name').agg({
                'Name': 'first',
                'analysis_date': 'count'
            }).rename(columns={'analysis_date': 'Buchungen'}).reset_index(drop=True)
            counts = recent.groupby('Name').size().reset_index(name='Buchungen')
            vielspieler = counts[counts['Buchungen'] >= 4].sort_values('Buchungen', ascending=False)
            vielspieler_list = vielspieler['Name'].tolist()
        
        # Alle Spieler (für manuelle Auswahl)
        all_players_list = sorted(buchungen['Name'].unique().tolist())
    
    # ========================================
    # WHATSAPP SENDEN UI
    # ========================================
    
    st.markdown("### 📤 Nachricht senden")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Empfänger-Auswahl
        empfaenger_modus = st.radio(
            "Empfänger wählen:",
            ["📋 Aus Vielspieler-Liste", "👤 Alle Spieler", "✏️ Manuelle Nummer"],
            horizontal=True,
            key="empfaenger_modus"
        )
        
        selected_player = None
        manual_phone = None
        manual_name = None
        
        if empfaenger_modus == "📋 Aus Vielspieler-Liste":
            if vielspieler_list:
                selected_player = st.selectbox(
                    "Vielspieler auswählen:",
                    options=vielspieler_list,
                    format_func=lambda x: f"{x} ({counts[counts['Name']==x]['Buchungen'].values[0]}x)" if not counts[counts['Name']==x].empty else x,
                    key="vielspieler_select"
                )
            else:
                st.info("Keine Vielspieler gefunden (≥4 Wellpass-Buchungen in 30 Tagen)")
        
        elif empfaenger_modus == "👤 Alle Spieler":
            if all_players_list:
                selected_player = st.selectbox(
                    "Spieler auswählen:",
                    options=all_players_list,
                    key="alle_spieler_select"
                )
            else:
                st.info("Keine Spieler gefunden")
        
        else:  # Manuelle Nummer
            manual_phone = st.text_input(
                "📱 Telefonnummer (mit +49):",
                placeholder="+49151...",
                key="manual_phone"
            )
            manual_name = st.text_input(
                "👤 Name (für Platzhalter):",
                placeholder="Max Mustermann",
                key="manual_name"
            )
    
    with col2:
        # Template-Auswahl
        template_options = {k: f"{v['icon']} {v['title']}" for k, v in WHATSAPP_TEMPLATES.items()}
        selected_template_key = st.selectbox(
            "📝 Nachrichtenvorlage:",
            options=list(template_options.keys()),
            format_func=lambda x: template_options[x],
            key="template_select"
        )
        
        selected_template = WHATSAPP_TEMPLATES[selected_template_key]
        
        # Platzhalter anzeigen
        st.caption(f"Platzhalter: {', '.join(selected_template['placeholders'])}")
    
    # ========================================
    # NACHRICHT VORSCHAU & BEARBEITUNG
    # ========================================
    
    st.markdown("---")
    st.markdown("### 📝 Nachricht anpassen")
    
    # Platzhalter ersetzen
    template_text = selected_template['template']
    
    # Name ersetzen
    if selected_player:
        template_text = template_text.replace("{name}", selected_player.split()[0])
        template_text = template_text.replace("{buchungen}", str(counts[counts['Name']==selected_player]['Buchungen'].values[0]) if not counts[counts['Name']==selected_player].empty else "X")
    elif manual_name:
        template_text = template_text.replace("{name}", manual_name.split()[0] if manual_name else "")
        template_text = template_text.replace("{buchungen}", "X")
    
    # Bearbeitbares Textfeld
    final_message = st.text_area(
        "Nachricht (bearbeitbar):",
        value=template_text,
        height=250,
        key="final_message"
    )
    
    # ========================================
    # SENDEN BUTTONS
    # ========================================
    
    col_send, col_test = st.columns(2)
    
    with col_send:
        can_send = (selected_player is not None) or (manual_phone and manual_name)
        
        if st.button("📤 WhatsApp senden", type="primary", use_container_width=True, disabled=not can_send):
            st.session_state['confirm_vielspieler_wa'] = True
    
    with col_test:
        if st.button("🧪 Test an Admin", use_container_width=True):
            # Test an Admin-Nummer senden
            try:
                from twilio.rest import Client
                
                twilio_conf = st.secrets.get("twilio", {})
                account_sid = twilio_conf.get("account_sid")
                auth_token = twilio_conf.get("auth_token")
                from_number = twilio_conf.get("whatsapp_from")
                admin_phone = twilio_conf.get("whatsapp_to")
                
                if all([account_sid, auth_token, from_number, admin_phone]):
                    client = Client(account_sid, auth_token)
                    
                    to_number = admin_phone if admin_phone.startswith("whatsapp:") else f"whatsapp:{admin_phone}"
                    
                    msg = client.messages.create(
                        from_=from_number,
                        to=to_number,
                        body=f"[TEST] {final_message}"
                    )
                    
                    st.success(f"✅ Test gesendet! SID: {msg.sid}")
                else:
                    st.error("Twilio nicht konfiguriert")
            except Exception as e:
                st.error(f"Fehler: {e}")
    
    # Bestätigungsdialog
    if st.session_state.get('confirm_vielspieler_wa', False):
        recipient = selected_player or manual_name
        st.warning(f"⚠️ Nachricht wirklich an **{recipient}** senden?")
        
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ Ja, senden!", type="primary", use_container_width=True):
                try:
                    from twilio.rest import Client
                    
                    # Telefonnummer ermitteln
                    if manual_phone:
                        phone = manual_phone
                    else:
                        # Aus Customers-Sheet laden
                        customers = loadsheet("customers")
                        if not customers.empty and 'name' in customers.columns:
                            player_match = customers[customers['name'].apply(normalize_name) == normalize_name(selected_player)]
                            if not player_match.empty and 'phone_number' in player_match.columns:
                                phone = str(player_match.iloc[0]['phone_number'])
                            else:
                                st.error(f"Keine Telefonnummer für {selected_player} gefunden")
                                st.session_state['confirm_vielspieler_wa'] = False
                                st.stop()
                        else:
                            st.error("Customer-Sheet nicht verfügbar")
                            st.session_state['confirm_vielspieler_wa'] = False
                            st.stop()
                    
                    # Nummer normalisieren
                    phone = phone.replace(" ", "").replace("-", "")
                    if not phone.startswith("+"):
                        phone = "+49" + phone.lstrip("0")
                    to_number = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
                    
                    # Senden
                    twilio_conf = st.secrets.get("twilio", {})
                    client = Client(twilio_conf["account_sid"], twilio_conf["auth_token"])
                    
                    msg = client.messages.create(
                        from_=twilio_conf["whatsapp_from"],
                        to=to_number,
                        body=final_message
                    )
                    
                    st.success(f"✅ Gesendet an {recipient}! SID: {msg.sid}")
                    st.session_state['confirm_vielspieler_wa'] = False
                    
                except Exception as e:
                    st.error(f"Fehler: {e}")
                    st.session_state['confirm_vielspieler_wa'] = False
        
        with col_no:
            if st.button("❌ Abbrechen", use_container_width=True):
                st.session_state['confirm_vielspieler_wa'] = False
                st.rerun()
    
    st.markdown("---")
    
    # ========================================
    # VIELSPIELER-ÜBERSICHT
    # ========================================
    
    st.markdown("### 👥 Eure Wellpass-Vielspieler")
    
    if vielspieler_list:
        # Metriken
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎯 Vielspieler", len(vielspieler_list), "≥4x/30 Tage")
        with col2:
            stammkunden_count = len([v for v in vielspieler_list if counts[counts['Name']==v]['Buchungen'].values[0] >= 8])
            st.metric("⭐ Stammkunden", stammkunden_count, "≥8x/30 Tage")
        with col3:
            top_count = counts['Buchungen'].max() if not counts.empty else 0
            st.metric("🏆 Top-Spieler", f"{top_count}x", "Buchungen")
        
        # Tabelle
        display_df = counts[counts['Buchungen'] >= 4].head(15).copy()
        display_df = display_df.sort_values('Buchungen', ascending=False)
        display_df.index = range(1, len(display_df) + 1)
        
        def add_medal(idx):
            if idx == 1: return "🥇"
            if idx == 2: return "🥈"
            if idx == 3: return "🥉"
            return f"{idx}."
        
        display_df['#'] = [add_medal(i) for i in range(1, len(display_df) + 1)]
        display_df = display_df[['#', 'Name', 'Buchungen']]
        display_df.columns = ['#', 'Spieler', 'Buchungen']
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=min(len(display_df) * 35 + 40, 500)
        )
    else:
        st.info("Keine Vielspieler gefunden (≥4 Wellpass-Buchungen in 30 Tagen)")
    
    st.markdown("---")
    
    # ========================================
    # ALLE VORLAGEN ANZEIGEN
    # ========================================
    
    st.markdown("### 📋 Alle Nachrichtenvorlagen")
    st.caption("Klicke zum Kopieren oder wähle oben zum Senden")
    
    for key, tmpl in WHATSAPP_TEMPLATES.items():
        with st.expander(f"{tmpl['icon']} {tmpl['title']}", expanded=False):
            st.code(tmpl['template'], language=None)
            st.caption(f"Platzhalter: {', '.join(tmpl['placeholders'])}")


# ========================================
# FOOTER
# ========================================

st.markdown("""
<div style="
    margin-top: 3rem; 
    padding: 1.5rem; 
    text-align: center;
    color: var(--text-secondary, #86868B);
    font-size: 0.75rem;
">
    🏔️ halle11 · v16.2
</div>
""", unsafe_allow_html=True)
