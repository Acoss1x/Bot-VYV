import os
import datetime
import random
import requests
import yfinance as yf
import pandas as pd
import mplfinance as mpf

# ================= Config =================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1403165163829592125/JwA3vaW5E7hRbqlge4gWSAZz4ABvPvgFYxi-e57jWROSMc5RMUT4sG9lfXWMI1V9Oucs"

PORTAFOLIO = {"PYPL": 72.0, "TSLA": 310.0, "MSTR": 245.0}
METAS      = {"TSLA": 480.0, "PYPL": 100.0, "MSTR": 480.0}

CARPETA_GRAFICOS = "graficos"
os.makedirs(CARPETA_GRAFICOS, exist_ok=True)

FRASES_MOTIVACIONALES = [
    "El éxito no es cuestión de suerte, sino de preparación diaria.",
    "Cada día es una nueva oportunidad para ganar.",
    "Invierte en tu futuro, no en tus excusas.",
    "Las grandes ganancias nacen de la constancia.",
    "La paciencia es el interés compuesto de la disciplina.",
    "No se trata de predecir, se trata de prepararse.",
    "Tener control emocional es más valioso que tener razón.",
    "La constancia que tienes hoy será la libertad que tendrás mañana."
]

# ================= Helpers =================
def obtener_datos_accion(ticker: str) -> pd.DataFrame:
    # Usar period para intradía es más estable
    df = yf.download(
        ticker, period="5d", interval="60m",
        progress=False, auto_adjust=False, group_by="ticker"
    )
    return df

def normalizar_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Devuelve columnas simples: Open, High, Low, Close, Volume (sin MultiIndex ni duplicados).
    """
    if isinstance(df.columns, pd.MultiIndex):
        # Nivel con ticker al final
        if ticker in df.columns.get_level_values(-1):
            try:
                df = df.xs(ticker, axis=1, level=-1, drop_level=True)
            except KeyError:
                pass
        # Nivel con ticker al inicio
        if isinstance(df.columns, pd.MultiIndex) and ticker in df.columns.get_level_values(0):
            try:
                df = df.xs(ticker, axis=1, level=0, drop_level=True)
            except KeyError:
                pass
        # Si el primer nivel es OHLC, chataremos a ese nivel
        if isinstance(df.columns, pd.MultiIndex) and "Close" in df.columns.get_level_values(0):
            df.columns = df.columns.get_level_values(0)

    # Renombrar variantes
    rename_map = {
        "Adj Close": "Close", "adjclose": "Close",
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
    }
    df = df.rename(columns=rename_map)

    # Nos quedamos con las que existan
    cols = ["Open", "High", "Low", "Close", "Volume"]
    keep = [c for c in cols if c in df.columns]
    df = df[keep].copy()

    # 🔒 Eliminar columnas duplicadas (yfinance a veces duplica nombres)
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # Convertir todo a numérico
    df = df.apply(pd.to_numeric, errors="coerce")
    df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)

    # Índice tiempo
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    df.sort_index(inplace=True)

    # Asegurar orden y que existan todas para mplfinance (si falta Volume, la creamos)
    for c in ["Open", "High", "Low", "Close"]:
        if c not in df.columns:
            raise ValueError(f"Falta columna requerida: {c}")
    if "Volume" not in df.columns:
        df["Volume"] = 0.0

    return df[["Open", "High", "Low", "Close", "Volume"]]

def generar_grafico_mplfinance(ticker: str, data: pd.DataFrame) -> str:
    ruta = os.path.join(CARPETA_GRAFICOS, f"{ticker}.png")
    print(f"🔍 Procesando gráfico para {ticker}")
    print("📊 Columnas originales:", list(data.columns))

    data = normalizar_ohlcv(data, ticker)
    print("✅ Columnas normalizadas:", list(data.columns))

    if data.empty:
        raise ValueError("❌ DataFrame vacío tras limpieza/normalización.")

    mpf.plot(
        data,
        type="candle",
        style="charles",
        title=f"{ticker} – Gráfico 4H",
        ylabel="Precio USD",
        volume=True,
        mav=(20, 50),
        savefig=dict(fname=ruta, dpi=100)
    )
    print(f"✅ Gráfico de {ticker} guardado en {ruta}")
    return ruta

def enviar_a_discord(mensaje: str, archivos: list) -> int:
    payload = {"content": mensaje}
    files = [("file", open(archivo, "rb")) for archivo in archivos]
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=payload, files=files, timeout=30)
    finally:
        for _, f in files:
            f.close()
    return response.status_code

# ================= Run =================
bitacora = []
graficos = []
hoy_str = datetime.datetime.now().strftime("%d/%m/%Y")
frase = random.choice(FRASES_MOTIVACIONALES)

for ticker, precio_promedio in PORTAFOLIO.items():
    try:
        print(f"\n🚀 Procesando {ticker}...")
        raw = obtener_datos_accion(ticker)
        if raw is None or raw.empty:
            raise ValueError("❌ No hay datos descargados")

        data = normalizar_ohlcv(raw, ticker)
        if data.empty:
            raise ValueError("❌ Sin OHLC válidos tras normalizar")

        # 👇 Forma robusta de extraer un escalar
        close_series = pd.to_numeric(data["Close"], errors="coerce").dropna()
        if close_series.empty:
            raise ValueError("❌ 'Close' vacío tras convertir a numérico")
        precio_actual = float(close_series.tail(1).to_numpy().ravel()[0])

        ganancia = ((precio_actual - precio_promedio) / precio_promedio) * 100

        # Metas
        meta = METAS.get(ticker)
        if meta:
            avance_meta = (precio_actual / meta) * 100
            if precio_actual >= meta:
                estado_meta = f"Meta superada +{((precio_actual - meta)/meta)*100:.1f}%"
            else:
                estado_meta = f"Faltante: {((meta - precio_actual)/meta)*100:.1f}%"
            meta_str = f"| Meta: ${meta:.2f} | Avance: {avance_meta:.1f}% | {estado_meta} |"
        else:
            meta_str = "| Meta: N/D |"

        bitacora.append(
            f"| {ticker} | Actual: ${precio_actual:.2f} | Promedio: ${precio_promedio:.2f} "
            f"| Ganancia: {ganancia:+.2f}% {meta_str}"
        )

        graficos.append(generar_grafico_mplfinance(ticker, raw))

    except Exception as e:
        print(f"❌ Error procesando {ticker}: {e}")

mensaje = f"📈 **Bitácora diaria – {hoy_str}**\n\n"
mensaje += f"🌟 *\"{frase}\"*\n\n"
mensaje += "\n".join(bitacora) if bitacora else "No se pudo generar la bitácora hoy."

# Enviar a Discord (204 = No Content, es normal en webhooks)
status = enviar_a_discord(mensaje, [graficos[0]]) if graficos else enviar_a_discord(mensaje, [])
for graf in graficos[1:]:
    enviar_a_discord("", [graf])

print(f"\n✅ Bitácora enviada a Discord. Status: {status}")
print(f"📊 Gráficos generados: {graficos}")









