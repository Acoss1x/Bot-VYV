import requests
import yfinance as yf
import datetime
import os
import time
import random
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager


DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1403165163829592125/JwA3vaW5E7hRbqlge4gWSAZz4ABvPvgFYxi-e57jWROSMc5RMUT4sG9lfXWMI1V9Oucs"  # <-- REEMPLAZA ESTO
PORTAFOLIO = {
    "PYPL": 72.0,
    "TSLA": 310.0,
    "MSTR": 245.0
}
CARPETA_GRAFICOS = "graficos"
os.makedirs(CARPETA_GRAFICOS, exist_ok=True)

FRASES_MOTIVACIONALES = [
    "El éxito no es cuestión de suerte, sino de preparación diaria.",
    "Cada día es una nueva oportunidad para ganar.",
    "Invierte en tu futuro, no en tus excusas.",
    "Las grandes ganancias nacen de la constancia.",
    "No todos los días se gana, pero todos los días se aprende.",
    "La paciencia es el interés compuesto de la disciplina.",
    "El mercado premia a los que piensan a largo plazo.",
    "Tener control emocional es más valioso que tener razón.",
    "Tu mejor inversión eres tú mismo.",
    "El éxito financiero es una serie de buenas decisiones diarias.",
    "Invierte como si tu vida dependiera de ello, porque en parte... lo hace.",
    "El mejor momento para invertir fue ayer. El segundo mejor es hoy.",
    "La disciplina le gana al talento, incluso en los mercados.",
    "No se trata de predecir, se trata de prepararse.",
    "Cada gráfico cuenta una historia. Tú decides si la lees o la ignoras.",
    "El miedo vende. La convicción construye.",
    "Las ganancias rápidas emocionan, las decisiones sabias enriquecen.",
    "Paciencia no es esperar, es saber actuar en el momento correcto.",
    "Invertir no es un juego, pero puede cambiar tu vida como ninguno.",
    "Si puedes controlar tus emociones, ya le ganas al 90% del mercado.",
    "Invertir bien no es ganar siempre, es perder poco y ganar mucho.",
    "La constancia que tienes hoy será la libertad que tendrás mañana.",
    "No trabajes por dinero, haz que el dinero trabaje por ti.",
    "Tu cartera refleja tus hábitos, no tus deseos.",
    "Invertir con miedo es como conducir con el freno puesto.",
    "Los días rojos enseñan más que los días verdes.",
    "Ser consistente te hará millonario. No el hype.",
    "El éxito no está en ganarle al mercado, sino en ganarte a ti mismo.",
    "No busques la operación perfecta. Construye un sistema perfecto.",
    "Lo importante no es lo que ganas hoy, sino lo que acumulas a lo largo de los años."
]


def obtener_datos_accion(ticker):
    hoy = datetime.datetime.now().date()
    hace_5_dias = hoy - datetime.timedelta(days=7)
    data = yf.download(ticker, start=hace_5_dias, end=hoy, auto_adjust=True)
    return data

def generar_grafico_tradingview(ticker):
    symbol = f"NASDAQ:{ticker}"
    url = f"https://www.tradingview.com/chart/?symbol={symbol}&interval=240"  

    firefox_options = Options()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--disable-gpu")
    firefox_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=firefox_options)
    driver.get(url)


    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "tv-signin-dialog__close"))
        ).click()
        print(f"[i] Popup cerrado para {ticker}")
    except:
        print(f"[i] No apareció popup de login para {ticker}")

    time.sleep(12)  
     

    try:
        driver.execute_script("""
            const popup = document.getElementById('credential_picker_container');
            if (popup) popup.remove();

            const iframes = document.querySelectorAll('iframe');
            for (let iframe of iframes) {
                if (iframe.src.includes('accounts.google.com')) {
                    iframe.remove();
                }
            }
        """)
        print(f"[i] Popup de Google eliminado por script para {ticker}")
    except Exception as e:
        print(f"[!] No se pudo eliminar el popup de Google para {ticker}: {e}")

    ruta = os.path.join(CARPETA_GRAFICOS, f"{ticker}.png")
    driver.save_screenshot(ruta)
    driver.quit()
    print(f"✅ Gráfico de {ticker} capturado: {ruta}")
    return ruta

def enviar_a_discord(mensaje, archivos):
    payload = {"content": mensaje}
    files = [("file", open(archivo, "rb")) for archivo in archivos]
    response = requests.post(DISCORD_WEBHOOK_URL, data=payload, files=files)
    for _, f in files:
        f.close()
    return response.status_code

bitacora = []
graficos = []
hoy_str = datetime.datetime.now().strftime("%d/%m/%Y")
frase = random.choice(FRASES_MOTIVACIONALES)

for ticker, precio_promedio in PORTAFOLIO.items():
    try:
        data = obtener_datos_accion(ticker)
        if data.empty or len(data) < 1:
            print(f"[!] No hay suficientes datos para {ticker}")
            continue

        precio_actual = data["Close"].iloc[-1].item()
        ganancia = ((precio_actual - precio_promedio) / precio_promedio) * 100

        bitacora.append(f"| {ticker} | Actual: ${precio_actual:.2f} | Promedio: ${precio_promedio:.2f} | Ganancia: {ganancia:+.2f}% |")
        grafico = generar_grafico_tradingview(ticker)
        graficos.append(grafico)

    except Exception as e:
        print(f"Error procesando {ticker}: {e}")

mensaje = f"📈 **Bitácora diaria – {hoy_str}**\n\n"
mensaje += f"🌟 *\"{frase}\"*\n\n"
mensaje += "\n".join(bitacora)


primer_imagen = graficos[0] if graficos else None
resto_imagenes = graficos[1:] if len(graficos) > 1 else []

if primer_imagen:
    status = enviar_a_discord(mensaje, [primer_imagen])
else:
    status = enviar_a_discord(mensaje, [])

for imagen in resto_imagenes:
    enviar_a_discord("", [imagen])

print(f"✅ Bitácora enviada a Discord. Status: {status}")


