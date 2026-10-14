# -*- coding: utf-8 -*-
"""
CleanMyWin - Utilidad de mantenimiento y limpieza para Windows
Interfaz tipo "navaja suiza": un panel central con módulos independientes.

Módulos:
  - Inicio        panel de control con acceso a todas las utilidades
  - Discos        escanea unidades enteras y clasifica archivos por tipo
  - Limpieza      elimina temporales y caches regenerables
  - Configuración ajustes globales

© 2026 Marco's Utilities
"""

APP_NOMBRE = "CleanMyWin"
APP_VERSION = "2.0"
APP_COPYRIGHT = "© 2026 Marco's Utilities"

# repo de GitHub donde se publican las releases (usado por el comprobador
# de actualizaciones); formato "usuario/repositorio"
GITHUB_REPO = "MacroSUtilityes/CleanMyWin-"

import os
import sys
import string
import shutil
import threading
import heapq
import subprocess
import time
import json
import glob
import ctypes
import tempfile
import webbrowser
import urllib.request
import urllib.error

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog

try:
    from send2trash import send2trash
    HAY_PAPELERA = True
except Exception:
    HAY_PAPELERA = False

try:
    from PIL import Image
    HAY_PIL = True
except Exception:
    HAY_PIL = False

try:
    import darkdetect
    HAY_DARKDETECT = True
except Exception:
    HAY_DARKDETECT = False


# ----------------------------------------------------------------------------
#  Configuracion / apariencia  (tema futurista: cian neon sobre azul profundo)
#  Existen dos paletas (oscura / clara). El modo activo puede ser fijo o
#  seguir el tema del sistema operativo (ver _resolver_modo / _aplicar_paleta).
# ----------------------------------------------------------------------------
ctk.set_default_color_theme("blue")

PALETA_OSCURA = {
    "COL_FONDO":       "#070b15",   # fondo general (espacio profundo)
    "COL_PANEL":       "#0d1424",   # tarjetas / paneles
    "COL_PANEL_2":     "#121b30",   # paneles elevados
    "COL_PANEL_HOVER": "#182238",
    "COL_SIDEBAR":     "#04070f",   # barra superior
    "COL_ACENTO":      "#00d9ff",   # cian neon
    "COL_ACENTO_HOV":  "#4ae4ff",
    "COL_ACENTO_TXT":  "#03111c",   # texto oscuro sobre botones cian
    "COL_VIOLETA":     "#8b5cf6",
    "COL_TEXTO":       "#e8f1ff",
    "COL_TEXTO_TENUE": "#7d8cad",
    "COL_VERDE":       "#00e896",
    "COL_VERDE_HOV":   "#2bf0ad",
    "COL_ROJO":        "#ff3d68",
    "COL_ROJO_HOV":    "#ff5c81",
    "COL_AMBAR":       "#ffb224",
    "COL_NARANJA":     "#ff7a45",
    "COL_BORDE":       "#1b2742",
}

PALETA_CLARA = {
    "COL_FONDO":       "#f2f5fb",
    "COL_PANEL":       "#ffffff",
    "COL_PANEL_2":     "#eaeff8",
    "COL_PANEL_HOVER": "#dde5f3",
    "COL_SIDEBAR":     "#ffffff",
    "COL_ACENTO":      "#0091b3",
    "COL_ACENTO_HOV":  "#00a9cf",
    "COL_ACENTO_TXT":  "#ffffff",
    "COL_VIOLETA":     "#7c3aed",
    "COL_TEXTO":       "#121a2b",
    "COL_TEXTO_TENUE": "#5b6787",
    "COL_VERDE":       "#059669",
    "COL_VERDE_HOV":   "#0d9c73",
    "COL_ROJO":        "#e11d48",
    "COL_ROJO_HOV":    "#f43f5e",
    "COL_AMBAR":       "#c2760a",
    "COL_NARANJA":     "#ea580c",
    "COL_BORDE":       "#d7deed",
}

FUENTE_MONO = "Consolas"


def _detectar_modo_sistema():
    """Devuelve 'Dark' o 'Light' segun el tema actual de Windows."""
    if HAY_DARKDETECT:
        try:
            return "Dark" if darkdetect.isDark() else "Light"
        except Exception:
            pass
    return "Dark"


def _resolver_modo(preferencia):
    """preferencia: 'sistema' | 'claro' | 'oscuro' -> 'Light' | 'Dark'"""
    if preferencia == "claro":
        return "Light"
    if preferencia == "oscuro":
        return "Dark"
    return _detectar_modo_sistema()


def _aplicar_paleta(modo):
    """Vuelca en el espacio de nombres del modulo la paleta correspondiente
    a 'Light'/'Dark', de forma que todos los COL_* usados en el resto del
    archivo reflejen el tema activo."""
    paleta = PALETA_CLARA if modo == "Light" else PALETA_OSCURA
    globals().update(paleta)
    ctk.set_appearance_mode(modo)


# Paleta por defecto disponible ya en tiempo de importacion (antes de que
# exista una ventana); CleanMyWin.__init__ la vuelve a aplicar segun la
# preferencia guardada / el tema del sistema.
_aplicar_paleta("Dark")


def _mezclar_hex(c1, c2, t):
    """Interpola dos colores hex (#rrggbb). t=0 -> c1, t=1 -> c2."""
    c1, c2 = c1.lstrip("#"), c2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# Cuantos archivos como maximo guardamos por categoria (los mas grandes)
MAX_GUARDAR = 1500
# Cuantas filas mostramos en el detalle
MAX_MOSTRAR = 250

# Categorias: nombre -> (emoji, color, extensiones)
CATEGORIAS = {
    "Videos": ("\U0001F3AC", "#a855f7",
        [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
         ".mpg", ".mpeg", ".3gp", ".ts", ".vob", ".ogv", ".m2ts", ".mts"]),
    "Fotos e imagenes": ("\U0001F4F7", "#ec4899",
        [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp",
         ".heic", ".raw", ".cr2", ".nef", ".arw", ".dng", ".svg", ".ico", ".psd"]),
    "Musica y audio": ("\U0001F3B5", "#f59e0b",
        [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus",
         ".aiff", ".alac", ".mid", ".midi"]),
    "Documentos": ("\U0001F4C4", "#3b82f6",
        [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
         ".rtf", ".odt", ".ods", ".odp", ".csv", ".epub", ".mobi", ".md"]),
    "Juegos": ("\U0001F3AE", "#22c55e", []),   # se detecta por la ruta
    "Comprimidos": ("\U0001F5DC", "#eab308",
        [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cab",
         ".tgz", ".zst"]),
    "Programas": ("⚙", "#06b6d4",
        [".exe", ".msi", ".dll", ".bat", ".cmd", ".apk", ".jar", ".sys",
         ".com", ".msix", ".appx"]),
    "Otros": ("\U0001F4E6", "#6b7280", []),
}

# Palabras en la ruta que indican que el archivo pertenece a un juego
PALABRAS_JUEGO = [
    "steamapps", "steamlibrary", "epic games", "gog galaxy", "gog games",
    "riot games", "ea games", "ea\\", "origin games", "ubisoft", "battle.net",
    "rockstar games", "xboxgames", "minecraft", "roblox", "activision",
    "\\games\\", "\\juegos\\",
]

# Mapa extension -> categoria (se construye una vez)
EXT_A_CATEGORIA = {}
for _nombre, (_emoji, _color, _exts) in CATEGORIAS.items():
    for _e in _exts:
        EXT_A_CATEGORIA[_e] = _nombre

def acortar(texto, n=88):
    texto = str(texto)
    return texto if len(texto) <= n else "..." + texto[-(n - 3):]


def formato_tamano(n):
    n = float(n)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0:
            if unidad == "B":
                return f"{int(n)} {unidad}"
            return f"{n:.1f} {unidad}"
        n /= 1024.0
    return f"{n:.1f} PB"


def clasificar(ruta_min, ext):
    """Devuelve la categoria de un archivo."""
    for palabra in PALABRAS_JUEGO:
        if palabra in ruta_min:
            return "Juegos"
    return EXT_A_CATEGORIA.get(ext, "Otros")


def listar_discos():
    """Lista las unidades disponibles con su uso."""
    discos = []
    for letra in string.ascii_uppercase:
        raiz = f"{letra}:\\"
        if os.path.exists(raiz):
            try:
                total, usado, libre = shutil.disk_usage(raiz)
            except OSError:
                continue
            discos.append({
                "letra": letra,
                "raiz": raiz,
                "total": total,
                "usado": usado,
                "libre": libre,
            })
    return discos


def clasificar_disco(media, bus):
    """Clasifica un disco a partir de su MediaType/BusType de Windows."""
    b = (bus or "").strip().lower()
    m = (media or "").strip().lower()
    if "nvme" in b:
        return "nvme"
    if "ssd" in m:
        return "ssd"
    if "hdd" in m or "hard" in m:
        return "hdd"
    return "desconocido"


def detectar_tipos_discos():
    """Devuelve {LETRA: {'tipo','media','bus'}} consultando el subsistema de
    almacenamiento de Windows via PowerShell. Pensado para lanzarse en un hilo."""
    ps = (
        "$phys=@{};"
        "Get-PhysicalDisk | ForEach-Object { $phys[[int]$_.DeviceId]="
        "\"$($_.MediaType)|$($_.BusType)\" };"
        "Get-Partition | Where-Object DriveLetter | ForEach-Object {"
        " $mb=$phys[[int]$_.DiskNumber];"
        " Write-Output \"$($_.DriveLetter)|$mb\" }"
    )
    res = {}
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for linea in out.stdout.splitlines():
            partes = linea.strip().split("|")
            if len(partes) >= 3 and partes[0].strip():
                letra = partes[0].strip().upper()
                media, bus = partes[1].strip(), partes[2].strip()
                res[letra] = {"tipo": clasificar_disco(media, bus),
                              "media": media, "bus": bus}
    except Exception:
        pass
    return res


def aviso_disco(tipo):
    """Texto de aviso (y color) segun el tipo de disco. NVMe: sin aviso."""
    if tipo == "ssd":
        return ("El escaneo de este SSD SATA puede tardar un poco.", COL_AMBAR)
    if tipo == "hdd":
        return ("Es un disco HDD: el escaneo va a tardar bastante, ten paciencia.",
                COL_NARANJA)
    return ("", None)   # nvme o desconocido -> no decir nada


ETIQUETA_DISCO = {"nvme": "NVMe", "ssd": "SSD", "hdd": "HDD"}


# ----------------------------------------------------------------------------
#  Configuracion persistente (carpeta destino para mover archivos, etc.)
# ----------------------------------------------------------------------------
_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(_APPDATA, "CleanMyWin")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
# carpeta de la version anterior (LimpiaPC): se migra su config la primera vez
CONFIG_PATH_ANTIGUO = os.path.join(_APPDATA, "LimpiaPC", "config.json")


def cargar_config():
    # preferimos la config nueva; si no existe, migramos la de la version anterior
    for ruta in (CONFIG_PATH, CONFIG_PATH_ANTIGUO):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return {}


def guardar_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ----------------------------------------------------------------------------
#  Comprobador de actualizaciones (GitHub Releases)
# ----------------------------------------------------------------------------
def _version_a_tupla(v):
    """'v2.10.1' / '2.1' -> (2, 10, 1) para poder comparar versiones."""
    v = (v or "").strip().lstrip("vV")
    partes = []
    for trozo in v.split("."):
        num = "".join(c for c in trozo if c.isdigit())
        partes.append(int(num) if num else 0)
    return tuple(partes) or (0,)


def _version_es_mas_nueva(remota, local):
    return _version_a_tupla(remota) > _version_a_tupla(local)


def consultar_ultima_release(timeout=6):
    """Devuelve {'version', 'notas', 'url', 'asset_url', 'asset_tam'} de la
    ultima release de GitHub, o None si no hay conexion / no hay releases
    publicadas todavia. 'asset_url' es la descarga directa del .exe adjunto
    a la release (None si esa release no tiene ningun .exe adjunto)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    peticion = urllib.request.Request(
        url, headers={"User-Agent": APP_NOMBRE, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as resp:
            datos = json.load(resp)
    except Exception:
        return None

    assets = datos.get("assets") or []
    asset_exe = None
    for a in assets:
        if (a.get("name") or "").lower() == "cleanmywin.exe":
            asset_exe = a
            break
    if asset_exe is None:
        for a in assets:
            if (a.get("name") or "").lower().endswith(".exe"):
                asset_exe = a
                break

    return {
        "version": datos.get("tag_name", ""),
        "notas": datos.get("body", "") or "",
        "url": datos.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest"),
        "asset_url": asset_exe.get("browser_download_url") if asset_exe else None,
        "asset_tam": asset_exe.get("size") if asset_exe else 0,
    }


# ----------------------------------------------------------------------------
#  Limpieza rapida: temporales y caches que Windows/los navegadores regeneran
# ----------------------------------------------------------------------------
def _rutas_perfiles(*partes):
    """Expande patrones con comodines (perfiles de navegador) a rutas existentes."""
    patron = os.path.join(*partes)
    return [p for p in glob.glob(patron) if os.path.isdir(p)]


def limpiezas_disponibles():
    local = os.environ.get("LOCALAPPDATA", "")
    windir = os.environ.get("WINDIR", "C:\\Windows")
    temp = os.environ.get("TEMP", "")

    return [
        {"id": "temp_usuario", "nombre": "Archivos temporales de usuario",
         "desc": "Restos que dejan los programas al ejecutarse.",
         "tipo": "carpetas", "rutas": [temp] if temp else []},
        {"id": "temp_windows", "nombre": "Archivos temporales de Windows",
         "desc": "Carpeta Temp del sistema (puede necesitar permisos de administrador).",
         "tipo": "carpetas", "rutas": [os.path.join(windir, "Temp")]},
        {"id": "papelera", "nombre": "Papelera de reciclaje",
         "desc": "Vacia la papelera de todas las unidades.",
         "tipo": "papelera", "rutas": []},
        {"id": "miniaturas", "nombre": "Cache de miniaturas",
         "desc": "Imagenes en miniatura que Windows vuelve a generar solo.",
         "tipo": "carpetas",
         "rutas": [os.path.join(local, "Microsoft", "Windows", "Explorer")] if local else [],
         "patron": "thumbcache_*.db"},
        {"id": "windows_update", "nombre": "Cache de Windows Update",
         "desc": "Instaladores ya usados de actualizaciones de Windows.",
         "tipo": "carpetas", "rutas": [os.path.join(windir, "SoftwareDistribution", "Download")]},
        {"id": "chrome", "nombre": "Cache de Google Chrome",
         "desc": "Cache de navegacion (no borra contrasenas ni favoritos).",
         "tipo": "carpetas",
         "rutas": _rutas_perfiles(local, "Google", "Chrome", "User Data", "*", "Cache") if local else []},
        {"id": "edge", "nombre": "Cache de Microsoft Edge",
         "desc": "Cache de navegacion (no borra contrasenas ni favoritos).",
         "tipo": "carpetas",
         "rutas": _rutas_perfiles(local, "Microsoft", "Edge", "User Data", "*", "Cache") if local else []},
        {"id": "firefox", "nombre": "Cache de Firefox",
         "desc": "Cache de navegacion (no borra contrasenas ni favoritos).",
         "tipo": "carpetas",
         "rutas": _rutas_perfiles(local, "Mozilla", "Firefox", "Profiles", "*", "cache2") if local else []},
    ]


def calcular_tamano_rutas(rutas, patron=None):
    """Cuenta archivos y bytes dentro de unas carpetas, sin borrar nada."""
    total_size = 0
    total_count = 0
    for base in rutas:
        if not base or not os.path.isdir(base):
            continue
        if patron:
            for p in glob.glob(os.path.join(base, patron)):
                try:
                    total_size += os.path.getsize(p)
                    total_count += 1
                except OSError:
                    continue
            continue
        for dirpath, _dirnames, filenames in os.walk(base, onerror=lambda e: None):
            for f in filenames:
                try:
                    total_size += os.path.getsize(os.path.join(dirpath, f))
                    total_count += 1
                except OSError:
                    continue
    return total_count, total_size


def limpiar_rutas(rutas, patron=None):
    """Borra el contenido de unas carpetas (no la carpeta raiz). Ignora archivos en uso."""
    borrados, fallos, liberado = 0, 0, 0
    for base in rutas:
        if not base or not os.path.isdir(base):
            continue
        if patron:
            for p in glob.glob(os.path.join(base, patron)):
                try:
                    tam = os.path.getsize(p)
                    os.remove(p)
                    borrados += 1
                    liberado += tam
                except OSError:
                    fallos += 1
            continue
        for dirpath, _dirnames, filenames in os.walk(base, topdown=False, onerror=lambda e: None):
            for f in filenames:
                p = os.path.join(dirpath, f)
                try:
                    tam = os.path.getsize(p)
                    os.remove(p)
                    borrados += 1
                    liberado += tam
                except OSError:
                    fallos += 1
            if dirpath != base:
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass
    return borrados, fallos, liberado


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("i64Size", ctypes.c_int64),
        ("i64NumItems", ctypes.c_int64),
    ]


def tamano_papelera():
    """Tamano acumulado de la papelera de reciclaje en todas las unidades."""
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
    try:
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if res == 0:
            return info.i64NumItems, info.i64Size
    except Exception:
        pass
    return 0, 0


def vaciar_papelera():
    """Vacia la papelera de reciclaje de todas las unidades, sin dialogos de confirmacion."""
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI = 0x00000002
    SHERB_NOSOUND = 0x00000004
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------------
#  Deteccion de programas y procedencia de archivos
# ----------------------------------------------------------------------------
# Carpetas raiz donde viven los programas instalados
MARCADORES_PROGRAMA = (
    "\\program files (x86)\\",
    "\\program files\\",
    "\\appdata\\local\\programs\\",
    "\\programdata\\",
)


def detectar_programa(ruta_min, ruta):
    """Si el archivo pertenece a un programa instalado, devuelve (nombre, carpeta_base)."""
    for marcador in MARCADORES_PROGRAMA:
        idx = ruta_min.find(marcador)
        if idx < 0:
            continue
        resto = ruta[idx + len(marcador):]
        if "\\" not in resto:        # archivo suelto en la raiz, no es un programa
            return None, None
        nombre = resto.split("\\", 1)[0]
        base = ruta[:idx + len(marcador)] + nombre
        return nombre, base
    return None, None


# Marcas rapidas para etiquetar de donde viene un archivo
MARCAS_PROCEDENCIA = [
    ("\\downloads\\", "Descargas"), ("\\descargas\\", "Descargas"),
    ("\\desktop\\", "Escritorio"), ("\\escritorio\\", "Escritorio"),
    ("\\onedrive", "OneDrive"), ("\\dropbox", "Dropbox"),
    ("steamapps", "Steam"), ("steamlibrary", "Steam"),
    ("epic games", "Epic Games"), ("riot games", "Riot Games"),
    ("battle.net", "Battle.net"), ("gog galaxy", "GOG"), ("gog games", "GOG"),
    ("rockstar games", "Rockstar"), ("ubisoft", "Ubisoft"),
    ("whatsapp", "WhatsApp"), ("telegram", "Telegram"), ("discord", "Discord"),
    ("\\camera roll\\", "Camara"), ("\\capturas", "Capturas"),
    ("\\$recycle.bin", "Papelera"), ("\\windows\\", "Windows"),
]


def procedencia(ruta):
    """Etiqueta corta con el origen del archivo (Descargas, Steam, nombre del programa...)."""
    r = ruta.lower()
    for marca, etiqueta in MARCAS_PROCEDENCIA:
        if marca in r:
            return etiqueta
    nombre, _ = detectar_programa(r, ruta)
    if nombre:
        return nombre
    for marcador in ("\\appdata\\local\\", "\\appdata\\roaming\\"):
        i = r.find(marcador)
        if i >= 0:
            resto = ruta[i + len(marcador):]
            if "\\" in resto:
                return resto.split("\\", 1)[0]
    # ultima opcion: primera carpeta significativa de la ruta
    partes = ruta.split("\\")
    if len(partes) > 4 and partes[1].lower() == "users":
        return partes[3]
    if len(partes) > 2:
        return partes[1]
    return ""


# ----------------------------------------------------------------------------
#  Extraccion del icono real de un .exe (API de Windows + Pillow)
# ----------------------------------------------------------------------------
if os.name == "nt":
    _u32 = ctypes.windll.user32
    _g32 = ctypes.windll.gdi32
    _sh32 = ctypes.windll.shell32
    _u32.GetDC.restype = ctypes.c_void_p
    _u32.GetDC.argtypes = [ctypes.c_void_p]
    _u32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _u32.FillRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    _u32.DrawIconEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
    _u32.DestroyIcon.argtypes = [ctypes.c_void_p]
    _g32.CreateCompatibleDC.restype = ctypes.c_void_p
    _g32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    _g32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    _g32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    _g32.SelectObject.restype = ctypes.c_void_p
    _g32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _g32.CreateSolidBrush.restype = ctypes.c_void_p
    _g32.CreateSolidBrush.argtypes = [ctypes.c_uint32]
    _g32.DeleteObject.argtypes = [ctypes.c_void_p]
    _g32.DeleteDC.argtypes = [ctypes.c_void_p]
    _g32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                               ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_uint32]
    _sh32.SHGetFileInfoW.restype = ctypes.c_void_p
    _sh32.SHGetFileInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32,
                                     ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]


class _SHFILEINFOW(ctypes.Structure):
    _fields_ = [("hIcon", ctypes.c_void_p), ("iIcon", ctypes.c_int),
                ("dwAttributes", ctypes.c_uint32),
                ("szDisplayName", ctypes.c_wchar * 260),
                ("szTypeName", ctypes.c_wchar * 80)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]

# COL_PANEL "#0d1424" en formato BGR que usa GDI
_FONDO_ICONO_BGR = 0x0024140D


def icono_de_exe(ruta_exe, lado=32):
    """Extrae el icono real de un ejecutable como imagen PIL, o None si falla."""
    if not HAY_PIL or os.name != "nt" or not ruta_exe or not os.path.exists(ruta_exe):
        return None
    SHGFI_ICON, SHGFI_LARGEICON = 0x100, 0x0
    info = _SHFILEINFOW()
    res = _sh32.SHGetFileInfoW(ruta_exe, 0, ctypes.byref(info),
                               ctypes.sizeof(info), SHGFI_ICON | SHGFI_LARGEICON)
    if not res or not info.hIcon:
        return None
    hicon = info.hIcon
    hdc_pantalla = hdc = hbmp = brocha = viejo = None
    try:
        hdc_pantalla = _u32.GetDC(None)
        hdc = _g32.CreateCompatibleDC(hdc_pantalla)
        hbmp = _g32.CreateCompatibleBitmap(hdc_pantalla, lado, lado)
        viejo = _g32.SelectObject(hdc, hbmp)
        brocha = _g32.CreateSolidBrush(_FONDO_ICONO_BGR)
        rect = (ctypes.c_long * 4)(0, 0, lado, lado)
        _u32.FillRect(hdc, ctypes.byref(rect), brocha)
        _u32.DrawIconEx(hdc, 0, 0, hicon, lado, lado, 0, None, 3)  # DI_NORMAL
        _g32.SelectObject(hdc, viejo)
        viejo = None

        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = lado
        bmi.bmiHeader.biHeight = -lado      # de arriba a abajo
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        buf = ctypes.create_string_buffer(lado * lado * 4)
        if not _g32.GetDIBits(hdc, hbmp, 0, lado, buf, ctypes.byref(bmi), 0):
            return None
        return Image.frombuffer("RGB", (lado, lado), buf.raw, "raw", "BGRX", 0, 1)
    except Exception:
        return None
    finally:
        if viejo:
            _g32.SelectObject(hdc, viejo)
        if brocha:
            _g32.DeleteObject(brocha)
        if hbmp:
            _g32.DeleteObject(hbmp)
        if hdc:
            _g32.DeleteDC(hdc)
        if hdc_pantalla:
            _u32.ReleaseDC(None, hdc_pantalla)
        _u32.DestroyIcon(hicon)


# ----------------------------------------------------------------------------
#  Idiomas
#  El espanol es el idioma base: todo el codigo usa literales en espanol
#  directamente. TRADUCCIONES_EN traduce esas mismas cadenas, tal cual
#  aparecen en pantalla, al ingles. self.t(texto) hace de "diccionario":
#  si no hay traduccion (o el idioma activo es espanol) devuelve el texto
#  original sin tocar.
# ----------------------------------------------------------------------------
IDIOMAS_DISPONIBLES = {
    "es": "🇪🇸  Español",
    "en": "🇬🇧  English",
}

TRADUCCIONES_EN = {
    # --- navegacion / topbar ---
    "←  Inicio": "←  Home",
    "\U0001F5A5 Sistema": "\U0001F5A5 System",
    "☀ Claro": "☀ Light",
    "☾ Oscuro": "☾ Dark",
    "Discos": "Disks",
    "Limpieza": "Cleanup",
    "Configuracion": "Settings",

    # --- selector de idioma ---
    "Cambiar idioma": "Change language",

    # --- tutorial de bienvenida ---
    "Bienvenida": "Welcome",
    "Saltar": "Skip",
    "Siguiente  ▸": "Next  ▸",
    "◂  Atras": "◂  Back",
    "¡Empezar!  ✓": "Start!  ✓",
    "Te damos la bienvenida a CleanMyWin": "Welcome to CleanMyWin",
    "Tu asistente para liberar espacio y mantener Windows limpio.\n"
    "Te ensenamos lo basico en unos segundos. Puedes saltar cuando quieras.":
        "Your assistant for freeing up space and keeping Windows clean.\n"
        "We'll show you the basics in a few seconds. You can skip anytime.",
    "Analizador de discos": "Disk analyzer",
    "Elige una unidad (C, D, E...) y la analizamos entera, clasificando cada "
    "archivo por tipo: videos, fotos, musica, documentos, juegos, programas...\n\n"
    "Veras un grafico y un desglose de que es lo que mas ocupa tu disco.":
        "Pick a drive (C, D, E...) and we'll scan it completely, classifying every "
        "file by type: videos, photos, music, documents, games, programs...\n\n"
        "You'll see a chart and a breakdown of what's taking up your space.",
    "Limpieza rapida": "Quick cleanup",
    "Elimina archivos temporales, caches de navegadores y restos de Windows "
    "Update que se regeneran solos.\n\n"
    "Es la forma mas rapida y segura de recuperar espacio.":
        "Removes temporary files, browser caches, and Windows Update leftovers "
        "that regenerate on their own.\n\n"
        "It's the fastest and safest way to free up space.",
    "Mover a una carpeta  o  borrar directamente": "Move to a folder  or  delete directly",
    "En Configuracion puedes asignar una CARPETA DE DESTINO (por ejemplo un "
    "disco externo) para MOVER ahi los archivos que quieras quitar de en medio "
    "sin borrarlos todavia.\n\n"
    "Y si lo prefieres, desde el detalle de cada categoria puedes enviarlos "
    "directamente a la Papelera de Windows (recuperables).":
        "In Settings you can set a DESTINATION FOLDER (an external drive, for "
        "example) to MOVE there the files you want out of the way without "
        "deleting them yet.\n\n"
        "Or, if you prefer, from each category's detail view you can send them "
        "straight to the Windows Recycle Bin (recoverable).",
    "A tu gusto": "Make it yours",
    "Arriba a la derecha eliges el tema: claro, oscuro o segun tu sistema.\n\n"
    "Podras volver a ver este tutorial cuando quieras desde Configuracion.":
        "Up in the top right you choose the theme: light, dark, or follow your "
        "system.\n\nYou can watch this tutorial again anytime from Settings.",

    # --- dialogo de actualizaciones ---
    "Ahora no": "Not now",
    "Actualizar ahora  ▸": "Update now  ▸",
    "Ver en GitHub  ▸": "View on GitHub  ▸",
    "No avisar de esta version otra vez": "Don't notify me about this version again",
    "Descargando actualización...": "Downloading update...",
    "Hay una nueva version disponible": "A new version is available",
    "Sin notas de la version.": "No release notes.",
    "Esta release no tiene un .exe adjunto: se abrira la pagina de GitHub.":
        "This release has no .exe attached: the GitHub page will open instead.",
    "Ejecutando desde el codigo fuente: se abrira la pagina de GitHub\n"
    "(actualiza con git pull o descarga el .exe manualmente).":
        "Running from source code: the GitHub page will open instead\n"
        "(update with git pull or download the .exe manually).",
    "Buscando...": "Searching...",
    "Buscar actualizaciones": "Check for updates",
    "No se pudo comprobar (sin conexion).": "Couldn't check (no connection).",
    "¡Hay una version nueva:": "New version available:",
    "Ya tienes la ultima version.": "You already have the latest version.",
    "Descargando...": "Downloading...",
    "No se pudo descargar la actualización. Prueba a descargarla manualmente.":
        "Couldn't download the update. Try downloading it manually.",
    "Instalando y reiniciando...": "Installing and restarting...",
    "Tienes la version": "You have version",
    "la nueva es": "the new one is",
    "Version instalada:": "Installed version:",
    "Comprueba en GitHub si hay una version mas reciente.": "Check GitHub for a newer version.",

    # --- inicio ---
    "panel principal": "main panel",
    "Centro de control": "Control center",
    "Todas las utilidades de mantenimiento y limpieza en un solo lugar.":
        "All your maintenance and cleanup utilities in one place.",
    "discos detectados": "disks detected",
    "espacio libre total": "total free space",
    "Escanea unidades completas, clasifica cada archivo por tipo y "
    "descubre que esta ocupando tu espacio.":
        "Scan entire drives, classify every file by type, and discover "
        "what's taking up your space.",
    "unidades listas para analizar": "drives ready to analyze",
    "Elimina temporales, caches de navegadores y restos de Windows "
    "Update que se regeneran solos.":
        "Remove temp files, browser caches, and Windows Update leftovers "
        "that regenerate on their own.",
    "objetivos de limpieza": "cleanup targets",
    "Ajustes globales de la aplicacion: carpeta de destino para mover "
    "archivos, tema y tutorial.":
        "Global app settings: destination folder for moving files, theme, and tutorial.",
    "▸ Preferencias de la aplicacion": "▸ App preferences",

    # --- modulo discos: escanear ---
    "modulo // discos": "module // disks",
    "Selecciona una unidad: se recorrera entera y se clasificara cada archivo por tipo.":
        "Select a drive: it will be scanned completely and every file classified by type.",
    "⌖  Escanear": "⌖  Scan",
    "▤  Resultados": "▤  Results",
    "▦  Programas": "▦  Programs",
    "▞▞ AJUSTES DEL ESCANEO": "▞▞ SCAN SETTINGS",
    "Omitir carpetas del sistema (Windows, Program Files) - mas rapido":
        "Skip system folders (Windows, Program Files) - faster",
    "▶   INICIAR ESCANEO": "▶   START SCAN",
    "Iniciando...": "Starting...",
    "Cancelar": "Cancel",
    "ESCANEANDO...": "SCANNING...",
    "El escaneo de este SSD SATA puede tardar un poco.":
        "Scanning this SATA SSD may take a little while.",
    "Es un disco HDD: el escaneo va a tardar bastante, ten paciencia.":
        "This is an HDD: the scan will take a while, be patient.",
    "Disco": "Disk",
    "usados de": "used of",
    "libres": "free",
    "Analizando...": "Analyzing...",
    "archivos": "files",
    "archivos/seg": "files/sec",

    # --- modulo discos: resultados ---
    "Todavia no hay resultados": "No results yet",
    "Escanea primero una unidad para ver el desglose por categorias.":
        "Scan a drive first to see the breakdown by category.",
    "Ir a escanear": "Go scan",
    "Resultados": "Results",
    "en": "in",
    "archivos analizados": "files analyzed",
    "en total": "in total",
    "arch.": "files",

    # --- categorias ---
    "Fotos e imagenes": "Photos and images",
    "Musica y audio": "Music and audio",
    "Documentos": "Documents",
    "Juegos": "Games",
    "Comprimidos": "Archives",
    "Programas": "Programs",
    "Otros": "Other",

    # --- detalle de categoria ---
    "←  Volver": "←  Back",
    "\U0001F5D1  Enviar a la papelera": "\U0001F5D1  Send to recycle bin",
    "\U0001F4C1  Mover a carpeta de basura": "\U0001F4C1  Move to trash folder",
    "Mostrando los": "Showing the",
    "archivos mas grandes": "largest files",
    "de": "of",
    "Cargando...": "Loading...",
    "Cargando archivos...": "Loading files...",
    "Cargar mas": "Load more",
    "restantes": "remaining",
    "▶  Abrir": "▶  Open",
    "\U0001F4C2  Ubicacion": "\U0001F4C2  Location",

    # --- programas instalados ---
    "Sin datos de programas": "No program data",
    "Escanea primero una unidad. Si ya lo hiciste, este disco no "
    "tiene carpetas de programas (Program Files, ProgramData...).":
        "Scan a drive first. If you already did, this drive has no "
        "program folders (Program Files, ProgramData...).",
    "(pulsa uno para ver sus archivos)": "(click one to see its files)",
    "programas": "programs",
    "Archivos .exe/.dll sueltos": "Loose .exe/.dll files",
    "Cargando programas...": "Loading programs...",
    "Desinstalar desde Windows": "Uninstall from Windows",
    "\U0001F4C2  Abrir carpeta": "\U0001F4C2  Open folder",
    "Consejo: no borres archivos sueltos de un programa; si no lo usas, "
    "desinstalalo desde Windows.":
        "Tip: don't delete loose files from a program; if you don't use it, "
        "uninstall it from Windows.",

    # --- movimiento de archivos ---
    "Moviendo archivos...": "Moving files...",

    # --- limpieza rapida ---
    "modulo // limpieza": "module // cleanup",
    "Elimina archivos temporales y caches que Windows y los navegadores "
    "vuelven a crear solos.":
        "Removes temporary files and caches that Windows and browsers "
        "recreate on their own.",
    "☑  Seleccionar todo": "☑  Select all",
    "☐  Quitar seleccion": "☐  Clear selection",
    "Calculando tamanos...": "Calculating sizes...",
    "\U0001F9F9  LIMPIAR SELECCIONADOS": "\U0001F9F9  CLEAN SELECTED",
    "Calculando...": "Calculating...",
    "Calculando tamanos...": "Calculating sizes...",
    "Nada que limpiar": "Nothing to clean",
    "Selecciona elementos para ver cuanto espacio liberarian":
        "Select items to see how much space they'd free",
    "Limpiando, espera un momento...": "Cleaning, please wait...",
    "Se liberarian aprox.": "Approx. space to free:",
    "Archivos temporales de usuario": "User temporary files",
    "Restos que dejan los programas al ejecutarse.":
        "Leftovers that programs leave behind when running.",
    "Archivos temporales de Windows": "Windows temporary files",
    "Carpeta Temp del sistema (puede necesitar permisos de administrador).":
        "System Temp folder (may need administrator permissions).",
    "Papelera de reciclaje": "Recycle bin",
    "Vacia la papelera de todas las unidades.": "Empties the recycle bin on all drives.",
    "Cache de miniaturas": "Thumbnail cache",
    "Imagenes en miniatura que Windows vuelve a generar solo.":
        "Thumbnail images that Windows regenerates automatically.",
    "Cache de Windows Update": "Windows Update cache",
    "Instaladores ya usados de actualizaciones de Windows.":
        "Already-used Windows Update installers.",
    "Cache de Google Chrome": "Google Chrome cache",
    "Cache de navegacion (no borra contrasenas ni favoritos).":
        "Browsing cache (doesn't delete passwords or bookmarks).",
    "Cache de Microsoft Edge": "Microsoft Edge cache",
    "Cache de Firefox": "Firefox cache",

    # --- configuracion ---
    "modulo // ajustes": "module // settings",
    "Preferencias globales de la aplicacion.": "Global application preferences.",
    "\U0001F4C1  Carpeta de destino para mover archivos":
        "\U0001F4C1  Destination folder for moving files",
    "Elige una carpeta (puede estar en otro disco duro, por ejemplo uno externo)\n"
    "donde mover los archivos que quieras sacar de en medio antes de borrarlos.":
        "Choose a folder (it can be on another drive, e.g. an external one)\n"
        "where to move files you want out of the way before deleting them.",
    "No configurada todavia": "Not set yet",
    "Elegir carpeta...": "Choose folder...",
    "Quitar": "Remove",
    "Elige la carpeta destino": "Choose destination folder",
    "Cuando esta configurada, en el detalle de cada categoria del modulo Discos\n"
    "podras pulsar \"Mover a carpeta de basura\" para sacar archivos del disco\n"
    "analizado sin borrarlos todavia (ideal para pasarlos a un disco externo\n"
    "antes de decidir si los borras).":
        "Once set, in each category's detail view in the Disks module\n"
        "you'll be able to click \"Move to trash folder\" to get files off the\n"
        "scanned drive without deleting them yet (ideal for moving them to an\n"
        "external drive before deciding whether to delete them).",
    "⬡  Actualizaciones": "⬡  Updates",
    "\U0001F393  Tutorial de bienvenida": "\U0001F393  Welcome tutorial",
    "Vuelve a ver la guia rapida de como funciona la aplicacion.":
        "Watch the quick guide on how the app works again.",
    "Ver tutorial de nuevo": "Watch tutorial again",

    # --- procedencia de archivos ---
    "Descargas": "Downloads",
    "Escritorio": "Desktop",
    "Camara": "Camera",
    "Capturas": "Screenshots",
    "Papelera": "Recycle Bin",

    # --- cuadros de dialogo (messagebox) ---
    "No encontrado": "Not found",
    "El archivo ya no existe.": "The file no longer exists.",
    "No encontrada": "Not found",
    "La carpeta ya no existe.": "The folder no longer exists.",
    "No se pudo abrir": "Couldn't open",
    "Windows no tiene un programa asociado para este tipo de archivo\n"
    "o hubo un error al abrirlo:":
        "Windows has no program associated with this file type\n"
        "or there was an error opening it:",
    "Error": "Error",
    "No se pudo abrir la ubicacion:": "Couldn't open the location:",
    "No se pudo abrir la carpeta:": "Couldn't open the folder:",
    "Nada seleccionado": "Nothing selected",
    "Marca primero los archivos que quieres eliminar.":
        "First check the files you want to delete.",
    "Marca primero los archivos que quieres mover.":
        "First check the files you want to move.",
    "Marca algun elemento que tenga datos para limpiar.":
        "Check an item that has data to clean.",
    "Falta libreria": "Missing library",
    "Send2Trash no esta instalado, no se puede borrar de forma segura.":
        "Send2Trash isn't installed, files can't be safely deleted.",
    "Confirmar": "Confirm",
    "Se enviaran {n} archivo(s) a la PAPELERA de reciclaje.":
        "{n} file(s) will be sent to the RECYCLE BIN.",
    "Podras recuperarlos desde ahi.": "You'll be able to recover them from there.",
    "Continuar?": "Continue?",
    "Hecho": "Done",
    "Enviados a la papelera: {n}": "Sent to recycle bin: {n}",
    "Espacio liberado: {t}": "Space freed: {t}",
    "No se pudieron borrar: {n}": "Couldn't delete: {n}",
    "Carpeta no configurada": "Folder not set",
    "Todavia no has elegido una carpeta de destino.":
        "You haven't chosen a destination folder yet.",
    "¿Quieres configurarla ahora?": "Do you want to set it up now?",
    "Confirmar movimiento": "Confirm move",
    "Se moveran {n} archivo(s)  ({t})  a:": "{n} file(s)  ({t})  will be moved to:",
    "¿Continuar?": "Continue?",
    "Movidos: {n}": "Moved: {n}",
    "Espacio liberado en este disco: {t}": "Space freed on this drive: {t}",
    "No se pudieron mover: {n}": "Couldn't move: {n}",
    "Confirmar limpieza": "Confirm cleanup",
    "Se eliminaran de forma PERMANENTE (no van a la papelera):":
        "These will be PERMANENTLY deleted (not sent to the recycle bin):",
    "Espacio a liberar: aprox. {t}": "Space to free: approx. {t}",
    "Limpieza completada": "Cleanup completed",
    "{n} archivo(s) no se pudieron borrar (estaban en uso "
    "o hacen falta permisos de administrador).":
        "{n} file(s) couldn't be deleted (they were in use "
        "or administrator permissions are needed).",
}

TRADUCCIONES = {"en": TRADUCCIONES_EN}


# ----------------------------------------------------------------------------
#  Aplicacion
# ----------------------------------------------------------------------------
class CleanMyWin(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NOMBRE)
        self.geometry("1280x800")
        self.minsize(1020, 640)

        # estado general
        self.config = cargar_config()
        self.idioma = self.config.get("idioma", "es")
        self._modo_actual = _resolver_modo(self.config.get("tema", "sistema"))
        _aplicar_paleta(self._modo_actual)
        self.configure(fg_color=COL_FONDO)
        self.disco_sel = None
        self.omitir_sistema = ctk.BooleanVar(value=False)
        self.resultado = None
        self.resultado_programas = None
        self._cache_iconos = {}       # nombre de programa -> CTkImage
        self._token_iconos = None
        self._escaneando = False
        self._cancelar = False
        self._vista_actual = ""
        self._tipos_disco = {}        # LETRA -> {'tipo','media','bus'}
        self._tipos_disco_hecho = False
        self._tipos_disco_cargando = False

        # progreso del escaneo de disco (tipos simples = seguro con el GIL)
        self._p_count = 0
        self._p_size = 0
        self._p_actual = ""
        self._p_terminado = False
        self._t_inicio = 0


        self._vista_actual = "inicio"
        self._redibujar_actual = None
        self._topbar = None
        self._tut_top = None
        self._construir_topbar()
        self._construir_footer()
        self._contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self._contenedor.pack(side="top", fill="both", expand=True)

        self.mostrar_inicio()
        self.after(3000, self._chequear_tema_sistema)
        # primera vez que se abre la app: elegir idioma y luego ver el tutorial
        self.after(450, self._quiza_iniciar_configuracion_inicial)
        # comprobar actualizaciones en segundo plano (no bloquea el arranque)
        self._act_top = None
        self.after(1500, self._chequear_actualizaciones)

    def _construir_footer(self):
        pie = ctk.CTkFrame(self, height=26, corner_radius=0, fg_color=COL_PANEL)
        pie.pack(side="bottom", fill="x")
        pie.pack_propagate(False)
        ctk.CTkLabel(pie, text=f"{APP_NOMBRE} v{APP_VERSION}",
                     font=ctk.CTkFont(family=FUENTE_MONO, size=10),
                     text_color=COL_TEXTO_TENUE).pack(side="left", padx=(22, 0))
        ctk.CTkLabel(pie, text=APP_COPYRIGHT,
                     font=ctk.CTkFont(family=FUENTE_MONO, size=10),
                     text_color=COL_TEXTO_TENUE).pack(side="right", padx=(0, 22))
        self._footer = pie

    # ==========================================================================
    #  Barra superior (logo, volver a inicio, selector de tema) / navegacion
    # ==========================================================================
    NOMBRES_VISTA = {
        "discos": "Discos",
        "limpieza": "Limpieza",
        "config": "Configuracion",
    }

    def _construir_topbar(self):
        barra = ctk.CTkFrame(self, height=62, corner_radius=0, fg_color=COL_PANEL)
        # al reconstruirse (cambio de vista / de tema) el contenedor ya existe,
        # asi que hay que colocar la barra ANTES de el o quedaria por debajo.
        cont = getattr(self, "_contenedor", None)
        if cont is not None and cont.winfo_exists():
            barra.pack(side="top", fill="x", before=cont)
        else:
            barra.pack(side="top", fill="x")
        barra.pack_propagate(False)
        self._topbar = barra

        izq = ctk.CTkFrame(barra, fg_color="transparent")
        izq.pack(side="left", fill="y", padx=(22, 0))

        fila_logo = ctk.CTkFrame(izq, fg_color="transparent")
        fila_logo.pack(side="left", pady=12)
        ctk.CTkLabel(fila_logo, text="⬡", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COL_ACENTO).pack(side="left")
        ctk.CTkLabel(fila_logo, text=f" {APP_NOMBRE}", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COL_TEXTO).pack(side="left")

        if self._vista_actual != "inicio":
            ctk.CTkFrame(izq, width=1, height=26, fg_color=COL_BORDE).pack(side="left", padx=18)
            ctk.CTkButton(izq, text="←  Inicio", width=100, height=34, corner_radius=8,
                          fg_color="transparent", hover_color=COL_PANEL_HOVER,
                          text_color=COL_ACENTO, font=ctk.CTkFont(size=13, weight="bold"),
                          command=self.mostrar_inicio).pack(side="left")
            ctk.CTkLabel(izq, text=self.NOMBRES_VISTA.get(self._vista_actual, ""),
                         font=ctk.CTkFont(size=13),
                         text_color=COL_TEXTO_TENUE).pack(side="left", padx=(12, 0))

        der = ctk.CTkFrame(barra, fg_color="transparent")
        der.pack(side="right", fill="y", padx=(0, 22))
        self._construir_selector_tema(der)

    def _construir_selector_tema(self, padre):
        cont = ctk.CTkFrame(padre, fg_color=COL_PANEL_2, corner_radius=9)
        cont.pack(side="right", pady=13)
        opciones = [("sistema", "\U0001F5A5 Sistema"), ("claro", "☀ Claro"), ("oscuro", "☾ Oscuro")]
        pref_actual = self.config.get("tema", "sistema")
        for clave, texto in opciones:
            activo = clave == pref_actual
            ctk.CTkButton(
                cont, text=texto, height=30, width=88, corner_radius=7,
                fg_color=COL_ACENTO if activo else "transparent",
                text_color=COL_ACENTO_TXT if activo else COL_TEXTO_TENUE,
                hover_color=COL_ACENTO_HOV if activo else COL_PANEL_HOVER,
                font=ctk.CTkFont(size=11, weight="bold" if activo else "normal"),
                command=lambda c=clave: self._cambiar_tema(c)).pack(side="left", padx=3, pady=3)

    def _reconstruir_topbar(self):
        if self._topbar is not None:
            self._topbar.destroy()
        self._construir_topbar()
        if getattr(self, "_footer", None) is not None:
            self._footer.destroy()
            self._construir_footer()

    def _cambiar_tema(self, preferencia):
        self.config["tema"] = preferencia
        guardar_config(self.config)
        self._modo_actual = _resolver_modo(preferencia)
        _aplicar_paleta(self._modo_actual)
        self.configure(fg_color=COL_FONDO)
        self._reconstruir_topbar()
        if self._redibujar_actual:
            self._redibujar_actual()

    def _chequear_tema_sistema(self):
        if self.config.get("tema", "sistema") == "sistema":
            modo = _detectar_modo_sistema()
            if modo != self._modo_actual:
                self._modo_actual = modo
                _aplicar_paleta(modo)
                self.configure(fg_color=COL_FONDO)
                self._reconstruir_topbar()
                if self._redibujar_actual:
                    self._redibujar_actual()
        self.after(3000, self._chequear_tema_sistema)

    def _marcar_vista(self, clave, redibujar):
        self._redibujar_actual = redibujar
        if clave != self._vista_actual:
            self._vista_actual = clave
            self._reconstruir_topbar()
        # traducir la vista recien construida (tras devolver el control al
        # bucle de Tk, cuando todos los widgets ya existen)
        self.after(0, lambda: self._traducir_widgets(self))

    # ==========================================================================
    #  Idiomas: traduccion de texto y de la interfaz ya construida
    # ==========================================================================
    def t(self, texto):
        """Traduce 'texto' (tal cual aparece en el codigo, en espanol) al
        idioma activo. Si no hay traduccion o el idioma es espanol, lo
        devuelve sin cambios."""
        return TRADUCCIONES.get(self.idioma, {}).get(texto, texto)

    def _traducir_widgets(self, widget):
        """Recorre recursivamente los hijos de 'widget' y traduce cualquier
        texto que coincida con una entrada del diccionario. Red de seguridad
        para todo lo que se crea con texto literal en espanol (botones,
        etiquetas...); no hace falta tocar cada sitio donde se crean."""
        if self.idioma == "es":
            return
        try:
            hijos = widget.winfo_children()
        except Exception:
            return
        for w in hijos:
            try:
                actual = w.cget("text")
            except Exception:
                actual = None
            if isinstance(actual, str) and actual:
                nuevo = self.t(actual)
                if nuevo != actual:
                    try:
                        w.configure(text=nuevo)
                    except Exception:
                        pass
            self._traducir_widgets(w)

    def _cambiar_idioma(self, codigo):
        self.config["idioma"] = codigo
        guardar_config(self.config)
        self.idioma = codigo
        self._reconstruir_topbar()
        if self._redibujar_actual:
            self._redibujar_actual()

    def _mostrar_selector_idioma(self, inicial=False):
        ya = getattr(self, "_idi_top", None)
        if ya is not None:
            try:
                if ya.winfo_exists():
                    ya.lift()
                    return
            except Exception:
                pass

        top = ctk.CTkToplevel(self)
        top.title("Idioma / Language")
        top.configure(fg_color=COL_FONDO)
        top.resizable(False, False)
        self._idi_top = top

        cont = ctk.CTkFrame(top, fg_color=COL_PANEL, corner_radius=16,
                            border_width=1, border_color=COL_BORDE)
        cont.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(cont, text="⬡", font=ctk.CTkFont(size=44),
                     text_color=COL_ACENTO).pack(pady=(34, 6))
        ctk.CTkLabel(cont, text="Elige idioma  /  Choose language",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COL_TEXTO, wraplength=340,
                     justify="center").pack(padx=30, pady=(0, 26))

        def elegir(codigo):
            self._cambiar_idioma(codigo)
            try:
                top.grab_release()
                top.destroy()
            except Exception:
                pass
            self._idi_top = None
            if inicial:
                self.after(200, self._quiza_mostrar_tutorial)

        for codigo, etiqueta in IDIOMAS_DISPONIBLES.items():
            activo = codigo == self.idioma
            ctk.CTkButton(cont, text=etiqueta, width=280, height=54, corner_radius=12,
                          fg_color=COL_ACENTO if activo else COL_PANEL_2,
                          hover_color=COL_ACENTO_HOV,
                          text_color=COL_ACENTO_TXT if activo else COL_TEXTO,
                          font=ctk.CTkFont(size=15, weight="bold"),
                          command=lambda c=codigo: elegir(c)).pack(pady=7, padx=40)

        w, h = 420, 330
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        top.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
        top.transient(self)
        top.protocol("WM_DELETE_WINDOW", lambda: elegir(self.idioma))

        def _grab():
            try:
                top.grab_set()
            except Exception:
                pass
        top.after(150, _grab)

    # ==========================================================================
    #  Tutorial de bienvenida (primera ejecucion)
    # ==========================================================================
    PASOS_TUTORIAL = [
        ("\U0001F44B", "Te damos la bienvenida a " + APP_NOMBRE,
         "Tu asistente para liberar espacio y mantener Windows limpio.\n"
         "Te ensenamos lo basico en unos segundos. Puedes saltar cuando quieras."),
        ("\U0001F4BE", "Analizador de discos",
         "Elige una unidad (C, D, E...) y la analizamos entera, clasificando cada "
         "archivo por tipo: videos, fotos, musica, documentos, juegos, programas...\n\n"
         "Veras un grafico y un desglose de que es lo que mas ocupa tu disco."),
        ("\U0001F9F9", "Limpieza rapida",
         "Elimina archivos temporales, caches de navegadores y restos de Windows "
         "Update que se regeneran solos.\n\n"
         "Es la forma mas rapida y segura de recuperar espacio."),
        ("\U0001F4C1", "Mover a una carpeta  o  borrar directamente",
         "En Configuracion puedes asignar una CARPETA DE DESTINO (por ejemplo un "
         "disco externo) para MOVER ahi los archivos que quieras quitar de en medio "
         "sin borrarlos todavia.\n\n"
         "Y si lo prefieres, desde el detalle de cada categoria puedes enviarlos "
         "directamente a la Papelera de Windows (recuperables)."),
        ("\U0001F3A8", "A tu gusto",
         "Arriba a la derecha eliges el tema: claro, oscuro o segun tu sistema.\n\n"
         "Podras volver a ver este tutorial cuando quieras desde Configuracion."),
    ]

    def _quiza_iniciar_configuracion_inicial(self):
        if "idioma" not in self.config:
            self._mostrar_selector_idioma(inicial=True)
        else:
            self._quiza_mostrar_tutorial()

    def _quiza_mostrar_tutorial(self):
        if not self.config.get("tutorial_visto"):
            self._mostrar_tutorial()

    def _mostrar_tutorial(self):
        # no abrir un segundo tutorial si ya hay uno visible
        ya = getattr(self, "_tut_top", None)
        if ya is not None:
            try:
                if ya.winfo_exists():
                    ya.lift()
                    return
            except Exception:
                pass
        top = ctk.CTkToplevel(self)
        top.title(f"{APP_NOMBRE} · {self.t('Bienvenida')}")
        top.configure(fg_color=COL_FONDO)
        top.resizable(False, False)
        self._tut_paso = 0
        self._tut_top = top
        self._tut_anim_token = 0

        cont = ctk.CTkFrame(top, fg_color=COL_PANEL, corner_radius=16,
                            border_width=1, border_color=COL_BORDE)
        cont.pack(fill="both", expand=True, padx=16, pady=16)

        # --- botones (anclados ABAJO: nunca se salen aunque el texto crezca) ---
        botones = ctk.CTkFrame(cont, fg_color="transparent")
        botones.pack(side="bottom", fill="x", padx=26, pady=(0, 24))
        self._tut_btn_saltar = ctk.CTkButton(
            botones, text="Saltar", width=90, height=40, corner_radius=8,
            fg_color="transparent", hover_color=COL_PANEL_HOVER,
            text_color=COL_TEXTO_TENUE, command=self._cerrar_tutorial)
        self._tut_btn_saltar.pack(side="left")
        self._tut_btn_sig = ctk.CTkButton(
            botones, text="Siguiente  ▸", width=150, height=40, corner_radius=8,
            fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV, text_color=COL_ACENTO_TXT,
            font=ctk.CTkFont(size=13, weight="bold"), command=self._tut_siguiente)
        self._tut_btn_sig.pack(side="right")
        self._tut_btn_atras = ctk.CTkButton(
            botones, text="◂  Atras", width=90, height=40, corner_radius=8,
            fg_color="transparent", hover_color=COL_PANEL_HOVER, border_width=1,
            border_color=COL_BORDE, text_color=COL_TEXTO, command=self._tut_atras)
        self._tut_btn_atras.pack(side="right", padx=(0, 10))

        # --- puntos de progreso (justo encima de los botones) ---
        self._tut_puntos_frame = ctk.CTkFrame(cont, fg_color="transparent")
        self._tut_puntos_frame.pack(side="bottom", pady=(0, 18))
        self._tut_puntos = []
        for _ in self.PASOS_TUTORIAL:
            p = ctk.CTkFrame(self._tut_puntos_frame, width=9, height=9, corner_radius=5,
                             fg_color=COL_BORDE)
            p.pack(side="left", padx=4)
            p.pack_propagate(False)
            self._tut_puntos.append(p)

        # --- contenido (rellena el espacio de arriba) ---
        contenido = ctk.CTkFrame(cont, fg_color="transparent")
        contenido.pack(side="top", fill="both", expand=True)
        self._tut_icono = ctk.CTkLabel(contenido, text="", font=ctk.CTkFont(size=52),
                                       text_color=COL_ACENTO)
        self._tut_icono.pack(pady=(30, 8))
        self._tut_titulo = ctk.CTkLabel(contenido, text="", font=ctk.CTkFont(size=21, weight="bold"),
                                        text_color=COL_TEXTO, wraplength=470, justify="center")
        self._tut_titulo.pack(padx=30)
        self._tut_texto = ctk.CTkLabel(contenido, text="", font=ctk.CTkFont(size=13),
                                       text_color=COL_TEXTO_TENUE, wraplength=470,
                                       justify="center")
        self._tut_texto.pack(padx=30, pady=(12, 0))

        self._tut_render()

        # tamano fijo, holgado para que quepa el paso mas largo
        w, h = 580, 500
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        top.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
        top.transient(self)
        top.protocol("WM_DELETE_WINDOW", self._cerrar_tutorial)

        def _grab():
            try:
                top.grab_set()
            except Exception:
                pass
        top.after(150, _grab)   # modal (tras estabilizar la ventana)
        self.after(0, lambda: self._traducir_widgets(top))

    def _tut_render(self):
        icono, titulo, texto = self.PASOS_TUTORIAL[self._tut_paso]
        self._tut_icono.configure(text=icono)
        self._tut_titulo.configure(text=self.t(titulo))
        self._tut_texto.configure(text=self.t(texto))
        for i, p in enumerate(self._tut_puntos):
            p.configure(fg_color=COL_ACENTO if i == self._tut_paso else COL_BORDE)
        self._tut_btn_atras.configure(state="normal" if self._tut_paso > 0 else "disabled")
        ultimo = self._tut_paso == len(self.PASOS_TUTORIAL) - 1
        self._tut_btn_sig.configure(text=self.t("¡Empezar!  ✓" if ultimo else "Siguiente  ▸"))
        # pequena animacion de fundido al cambiar de paso
        self._tut_anim_token += 1
        self._tut_fade(0, self._tut_anim_token)

    def _tut_fade(self, i, token):
        if token != self._tut_anim_token:
            return
        top = getattr(self, "_tut_top", None)
        if top is None or not top.winfo_exists():
            return
        N = 7
        t = min(i / N, 1.0)
        try:
            self._tut_icono.configure(text_color=_mezclar_hex(COL_PANEL, COL_ACENTO, t))
            self._tut_titulo.configure(text_color=_mezclar_hex(COL_PANEL, COL_TEXTO, t))
            self._tut_texto.configure(text_color=_mezclar_hex(COL_PANEL, COL_TEXTO_TENUE, t))
        except Exception:
            return
        if i < N:
            top.after(22, lambda: self._tut_fade(i + 1, token))

    def _tut_siguiente(self):
        if self._tut_paso >= len(self.PASOS_TUTORIAL) - 1:
            self._cerrar_tutorial()
        else:
            self._tut_paso += 1
            self._tut_render()

    def _tut_atras(self):
        if self._tut_paso > 0:
            self._tut_paso -= 1
            self._tut_render()

    def _cerrar_tutorial(self):
        self.config["tutorial_visto"] = True
        guardar_config(self.config)
        try:
            self._tut_top.grab_release()
            self._tut_top.destroy()
        except Exception:
            pass
        self._tut_top = None

    # ==========================================================================
    #  Comprobador de actualizaciones (consulta GitHub Releases)
    # ==========================================================================
    def _chequear_actualizaciones(self):
        threading.Thread(target=self._hilo_chequear_actualizaciones, daemon=True).start()

    def _hilo_chequear_actualizaciones(self):
        release = consultar_ultima_release()
        if release is None:
            return
        if not _version_es_mas_nueva(release["version"], APP_VERSION):
            return
        # el usuario pudo pedir "no avisar de nuevo" para esta version concreta
        if release["version"] == self.config.get("actualizacion_omitida"):
            return
        # volver al hilo principal de Tk para tocar la interfaz
        self.after(0, lambda: self._mostrar_dialogo_actualizacion(release))

    def _mostrar_dialogo_actualizacion(self, release):
        ya = getattr(self, "_act_top", None)
        if ya is not None:
            try:
                if ya.winfo_exists():
                    ya.lift()
                    return
            except Exception:
                pass

        top = ctk.CTkToplevel(self)
        top.title(f"{APP_NOMBRE} · Actualización disponible")
        top.configure(fg_color=COL_FONDO)
        top.resizable(False, False)
        self._act_top = top
        self._act_release = release
        self._act_descargando = False

        cont = ctk.CTkFrame(top, fg_color=COL_PANEL, corner_radius=16,
                            border_width=1, border_color=COL_BORDE)
        cont.pack(fill="both", expand=True, padx=16, pady=16)

        # se puede autoactualizar solo si esto es un .exe empaquetado
        # (no un "python main.py" desde el codigo fuente) y la release
        # tiene un .exe adjunto
        puede_auto = bool(getattr(sys, "frozen", False)) and bool(release.get("asset_url"))

        botones = ctk.CTkFrame(cont, fg_color="transparent")
        botones.pack(side="bottom", fill="x", padx=26, pady=(0, 22))
        self._act_btn_cerrar = ctk.CTkButton(
            botones, text="Ahora no", width=110, height=40, corner_radius=8,
            fg_color="transparent", hover_color=COL_PANEL_HOVER,
            text_color=COL_TEXTO_TENUE, command=self._cerrar_dialogo_actualizacion)
        self._act_btn_cerrar.pack(side="left")
        self._act_btn_principal = ctk.CTkButton(
            botones,
            text="Actualizar ahora  ▸" if puede_auto else "Ver en GitHub  ▸",
            width=190, height=40, corner_radius=8,
            fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV, text_color=COL_ACENTO_TXT,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._actualizar_ahora if puede_auto else self._abrir_descarga_actualizacion)
        self._act_btn_principal.pack(side="right")

        omitir = ctk.CTkFrame(cont, fg_color="transparent")
        omitir.pack(side="bottom", pady=(0, 4))
        self._act_omitir_var = ctk.BooleanVar(value=False)
        self._act_chk_omitir = ctk.CTkCheckBox(
            omitir, text="No avisar de esta version otra vez",
            variable=self._act_omitir_var, font=ctk.CTkFont(size=12),
            text_color=COL_TEXTO_TENUE, checkbox_width=18, checkbox_height=18,
            fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV)
        self._act_chk_omitir.pack()

        # barra de progreso de la descarga (oculta hasta que se pulsa "Actualizar ahora")
        self._act_progreso_frame = ctk.CTkFrame(cont, fg_color="transparent")
        self._act_lbl_progreso = ctk.CTkLabel(
            self._act_progreso_frame, text="Descargando actualización...",
            font=ctk.CTkFont(size=12), text_color=COL_TEXTO_TENUE)
        self._act_lbl_progreso.pack(pady=(0, 6))
        self._act_barra_progreso = ctk.CTkProgressBar(
            self._act_progreso_frame, width=380, height=10, corner_radius=5,
            progress_color=COL_ACENTO, fg_color=COL_PANEL_2)
        self._act_barra_progreso.set(0)
        self._act_barra_progreso.pack()
        # (se hace pack() de _act_progreso_frame solo cuando arranca la descarga)

        contenido = ctk.CTkFrame(cont, fg_color="transparent")
        contenido.pack(side="top", fill="both", expand=True, padx=30, pady=(28, 6))
        ctk.CTkLabel(contenido, text="⬡", font=ctk.CTkFont(size=44),
                     text_color=COL_ACENTO).pack(pady=(4, 6))
        ctk.CTkLabel(contenido, text="Hay una nueva version disponible",
                     font=ctk.CTkFont(size=19, weight="bold"),
                     text_color=COL_TEXTO, wraplength=440, justify="center").pack()
        ctk.CTkLabel(contenido,
                     text=f"{self.t('Tienes la version')} {APP_VERSION}  ·  "
                          f"{self.t('la nueva es')} {release['version']}",
                     font=ctk.CTkFont(size=13), text_color=COL_TEXTO_TENUE).pack(pady=(6, 14))

        if not puede_auto and getattr(sys, "frozen", False):
            ctk.CTkLabel(contenido,
                         text="Esta release no tiene un .exe adjunto: se abrira la pagina de GitHub.",
                         font=ctk.CTkFont(size=11), text_color=COL_AMBAR,
                         wraplength=440, justify="center").pack(pady=(0, 8))
        elif not puede_auto:
            ctk.CTkLabel(contenido,
                         text="Ejecutando desde el codigo fuente: se abrira la pagina de GitHub\n"
                              "(actualiza con git pull o descarga el .exe manualmente).",
                         font=ctk.CTkFont(size=11), text_color=COL_TEXTO_TENUE,
                         wraplength=440, justify="center").pack(pady=(0, 8))

        notas = (release.get("notas") or self.t("Sin notas de la version.")).strip()
        if len(notas) > 500:
            notas = notas[:500].rstrip() + "…"
        caja_notas = ctk.CTkTextbox(contenido, width=440, height=140, corner_radius=10,
                                     fg_color=COL_PANEL_2, text_color=COL_TEXTO_TENUE,
                                     font=ctk.CTkFont(family=FUENTE_MONO, size=12),
                                     wrap="word")
        caja_notas.pack(fill="x")
        caja_notas.insert("1.0", notas)
        caja_notas.configure(state="disabled")
        self._act_caja_notas = caja_notas

        w, h = 500, 500
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        top.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
        top.transient(self)
        top.protocol("WM_DELETE_WINDOW", self._cerrar_dialogo_actualizacion)

        def _grab():
            try:
                top.grab_set()
            except Exception:
                pass
        top.after(150, _grab)
        self.after(0, lambda: self._traducir_widgets(top))

    def _buscar_actualizaciones_manual(self):
        self._btn_buscar_act.configure(state="disabled", text=self.t("Buscando..."))
        self._lbl_estado_act.configure(text="")
        threading.Thread(target=self._hilo_buscar_actualizaciones_manual, daemon=True).start()

    def _hilo_buscar_actualizaciones_manual(self):
        release = consultar_ultima_release()
        self.after(0, lambda: self._al_terminar_busqueda_manual(release))

    def _al_terminar_busqueda_manual(self, release):
        try:
            self._btn_buscar_act.configure(state="normal", text=self.t("Buscar actualizaciones"))
        except Exception:
            return  # la vista de configuracion ya no esta visible
        if release is None:
            self._lbl_estado_act.configure(text=self.t("No se pudo comprobar (sin conexion)."),
                                            text_color=COL_ROJO)
        elif _version_es_mas_nueva(release["version"], APP_VERSION):
            self._lbl_estado_act.configure(
                text=f"{self.t('¡Hay una version nueva:')} {release['version']}!",
                text_color=COL_ACENTO)
            self._mostrar_dialogo_actualizacion(release)
        else:
            self._lbl_estado_act.configure(text=self.t("Ya tienes la ultima version."),
                                            text_color=COL_VERDE)

    def _abrir_descarga_actualizacion(self):
        url = self._act_release.get("url") if self._act_release else None
        if url:
            webbrowser.open(url)
        self._cerrar_dialogo_actualizacion()

    def _cerrar_dialogo_actualizacion(self):
        if self._act_descargando:
            return  # no dejar cerrar la ventana a medio descargar
        if getattr(self, "_act_omitir_var", None) is not None and self._act_omitir_var.get():
            self.config["actualizacion_omitida"] = self._act_release["version"]
            guardar_config(self.config)
        try:
            self._act_top.grab_release()
            self._act_top.destroy()
        except Exception:
            pass
        self._act_top = None

    # --- actualizacion automatica: descarga el .exe de la release y se relanza ---
    def _actualizar_ahora(self):
        self._act_descargando = True
        self._act_btn_principal.configure(state="disabled", text=self.t("Descargando..."))
        self._act_btn_cerrar.configure(state="disabled")
        self._act_chk_omitir.configure(state="disabled")
        self._act_progreso_frame.pack(side="bottom", fill="x", padx=30, pady=(0, 14))
        threading.Thread(target=self._hilo_actualizar_ahora,
                          args=(self._act_release,), daemon=True).start()

    def _hilo_actualizar_ahora(self, release):
        try:
            exe_actual = sys.executable
            exe_nuevo = exe_actual + ".nuevo"
            peticion = urllib.request.Request(
                release["asset_url"], headers={"User-Agent": APP_NOMBRE})
            with urllib.request.urlopen(peticion, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0)) or release.get("asset_tam", 0)
                leido = 0
                with open(exe_nuevo, "wb") as f:
                    while True:
                        bloque = resp.read(262144)
                        if not bloque:
                            break
                        f.write(bloque)
                        leido += len(bloque)
                        if total:
                            frac = min(leido / total, 1.0)
                            self.after(0, lambda v=frac: self._act_progreso(v))
            if os.path.getsize(exe_nuevo) < 1024:
                raise RuntimeError("La descarga parece incompleta.")
        except Exception as e:
            mensaje = str(e)
            try:
                os.remove(exe_nuevo)
            except Exception:
                pass
            self.after(0, lambda m=mensaje: self._act_error_descarga(m))
            return
        self.after(0, lambda: self._act_lanzar_instalador(exe_actual, exe_nuevo))

    def _act_progreso(self, frac):
        try:
            self._act_barra_progreso.set(frac)
            self._act_lbl_progreso.configure(
                text=f"{self.t('Descargando actualización...')} {int(frac * 100)}%")
        except Exception:
            pass

    def _act_error_descarga(self, mensaje):
        self._act_descargando = False
        try:
            self._act_lbl_progreso.configure(
                text=self.t("No se pudo descargar la actualización. Prueba a descargarla manualmente."),
                text_color=COL_ROJO)
            self._act_btn_principal.configure(state="normal", text=self.t("Ver en GitHub  ▸"),
                                               command=self._abrir_descarga_actualizacion)
            self._act_btn_cerrar.configure(state="normal")
            self._act_chk_omitir.configure(state="normal")
        except Exception:
            pass

    def _act_lanzar_instalador(self, exe_actual, exe_nuevo):
        self._act_lbl_progreso.configure(text=self.t("Instalando y reiniciando..."))
        pid = os.getpid()
        bat_path = os.path.join(tempfile.gettempdir(), "cleanmywin_actualizar.bat")
        contenido_bat = (
            "@echo off\r\n"
            ":espera\r\n"
            f'tasklist /fi "PID eq {pid}" | find "{pid}" >nul\r\n'
            "if not errorlevel 1 (\r\n"
            "  timeout /t 1 /nobreak >nul\r\n"
            "  goto espera\r\n"
            ")\r\n"
            f'move /y "{exe_nuevo}" "{exe_actual}" >nul 2>&1\r\n'
            f'start "" "{exe_actual}"\r\n'
            'del "%~f0"\r\n'
        )
        try:
            with open(bat_path, "w", encoding="mbcs") as f:
                f.write(contenido_bat)
            subprocess.Popen(["cmd", "/c", bat_path],
                              creationflags=subprocess.CREATE_NO_WINDOW,
                              close_fds=True)
        except Exception as e:
            self._act_error_descarga(str(e))
            return
        # cerrar ya: el .bat espera a que este proceso termine para reemplazar el exe
        self.after(400, lambda: os._exit(0))

    # ==========================================================================
    #  Deteccion del tipo de disco (SSD / NVMe / HDD) en segundo plano
    # ==========================================================================
    def _asegurar_tipos_disco(self):
        if self._tipos_disco_hecho or self._tipos_disco_cargando:
            return
        self._tipos_disco_cargando = True

        def trabajo():
            tipos = detectar_tipos_discos()

            def aplicar():
                self._tipos_disco = tipos
                self._tipos_disco_hecho = True
                self._tipos_disco_cargando = False
                # si seguimos en la pantalla de escaneo, redibujar con los tipos
                if self._vista_actual == "discos_escanear" and not self._escaneando:
                    self.mostrar_discos_escanear()
            try:
                self.after(0, aplicar)
            except Exception:
                pass

        threading.Thread(target=trabajo, daemon=True).start()

    # ==========================================================================
    #  Spinner de carga + render por tandas (evita congelar la UI)
    # ==========================================================================
    def _barra_carga(self, padre, fondo, texto="Cargando..."):
        """Devuelve un frame con un circulo girando + texto. El caller lo
        coloca (pack o grid). Expone .step() para avanzar el giro manualmente
        durante trabajo pesado (cuando el temporizador no puede dispararse)."""
        texto = self.t(texto)
        barra = ctk.CTkFrame(padre, fg_color="transparent")
        SZ = 24
        cv = tk.Canvas(barra, width=SZ, height=SZ, bg=fondo,
                       highlightthickness=0, bd=0)
        cv.pack(side="left", padx=(2, 10))
        pad = 3
        cv.create_oval(pad, pad, SZ - pad, SZ - pad, outline=COL_BORDE, width=3)
        arco = cv.create_arc(pad, pad, SZ - pad, SZ - pad, start=90, extent=90,
                             style="arc", outline=COL_ACENTO, width=3)
        ctk.CTkLabel(barra, text=texto, font=ctk.CTkFont(size=12),
                     text_color=COL_TEXTO_TENUE).pack(side="left")
        st = {"ang": 90}

        def _pintar(delta):
            try:
                if cv.winfo_exists():
                    st["ang"] = (st["ang"] - delta) % 360
                    cv.itemconfig(arco, start=st["ang"])
            except Exception:
                pass

        def girar():
            try:
                if not cv.winfo_exists():
                    return
            except Exception:
                return
            _pintar(20)
            cv.after(28, girar)
        girar()
        barra.step = lambda: _pintar(34)
        return barra

    def _stream_filas(self, tok_attr, lista, indices, construir_una,
                      al_terminar=None, barra=None, tam_tanda=4):
        """Renderiza 'indices' en tandas pequenas para no congelar la interfaz.
        Tras cada tanda avanza el spinner y fuerza un repintado, de modo que
        las filas van apareciendo y el circulo gira de verdad. Cancelable si
        cambia la vista. construir_una(i) crea una fila."""
        tok = object()
        setattr(self, tok_attr, tok)
        estado = {"pos": 0}

        def tanda():
            if getattr(self, tok_attr, None) is not tok:
                return
            try:
                if not lista.winfo_exists():
                    return
            except Exception:
                return
            fin = min(estado["pos"] + tam_tanda, len(indices))
            for k in range(estado["pos"], fin):
                construir_una(indices[k])
            estado["pos"] = fin
            if barra is not None:
                try:
                    barra.step()
                except Exception:
                    pass
            try:
                self.update_idletasks()   # pintar filas + spinner ya mismo
            except Exception:
                pass
            if fin < len(indices):
                self.after(1, tanda)
            elif al_terminar:
                al_terminar()
        # diferir la primera tanda para que la cabecera y el spinner se pinten
        self.after(16, tanda)

    def _limpiar_contenedor(self):
        for w in self._contenedor.winfo_children():
            w.destroy()

    def _cabecera(self, padre, kicker, titulo, sub=None):
        kicker, titulo, sub = self.t(kicker), self.t(titulo), self.t(sub) if sub else sub
        ctk.CTkLabel(padre, text="▞▞ " + " ".join(kicker.upper()),
                     font=ctk.CTkFont(family=FUENTE_MONO, size=12, weight="bold"),
                     text_color=COL_ACENTO).pack(anchor="w")
        ctk.CTkLabel(padre, text=titulo,
                     font=ctk.CTkFont(size=27, weight="bold"),
                     text_color=COL_TEXTO).pack(anchor="w", pady=(2, 0))
        if sub:
            ctk.CTkLabel(padre, text=sub, font=ctk.CTkFont(size=13),
                         text_color=COL_TEXTO_TENUE, justify="left").pack(anchor="w", pady=(3, 0))

    def _barra_tabs(self, padre, tabs, activa):
        """Sub-navegacion dentro de un modulo. tabs = [(clave, texto, comando)]"""
        cont = ctk.CTkFrame(padre, fg_color=COL_PANEL, corner_radius=12)
        cont.pack(anchor="w", pady=(16, 18))
        for clave, texto, cmd in tabs:
            activo = (clave == activa)
            ctk.CTkButton(
                cont, text=texto, height=34, corner_radius=9, width=150,
                fg_color=COL_ACENTO if activo else "transparent",
                text_color=COL_ACENTO_TXT if activo else COL_TEXTO_TENUE,
                hover_color=COL_ACENTO_HOV if activo else COL_PANEL_HOVER,
                font=ctk.CTkFont(size=13, weight="bold" if activo else "normal"),
                command=cmd).pack(side="left", padx=4, pady=4)

    # ==========================================================================
    #  MODULO: INICIO (panel de control)
    # ==========================================================================
    def mostrar_inicio(self):
        self._limpiar_contenedor()
        self._marcar_vista("inicio", self.mostrar_inicio)

        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=36, pady=30)

        self._cabecera(marco, "panel principal", "Centro de control",
                       "Todas las utilidades de mantenimiento y limpieza en un solo lugar.")

        # ----- tira de estadisticas rapidas -----
        discos = listar_discos()
        libre_total = sum(d["libre"] for d in discos)
        tira = ctk.CTkFrame(marco, fg_color="transparent")
        tira.pack(fill="x", pady=(24, 26))
        self._mini_stat(tira, str(len(discos)), "discos detectados", COL_ACENTO)
        self._mini_stat(tira, formato_tamano(libre_total), "espacio libre total", COL_VERDE)

        # ----- rejilla de modulos (3 columnas, 1 fila) -----
        rejilla = ctk.CTkFrame(marco, fg_color="transparent")
        rejilla.pack(fill="both", expand=True)
        rejilla.grid_columnconfigure(0, weight=1, uniform="mod")
        rejilla.grid_columnconfigure(1, weight=1, uniform="mod")
        rejilla.grid_columnconfigure(2, weight=1, uniform="mod")
        rejilla.grid_rowconfigure(0, weight=1, uniform="modf")

        self._tarjeta_modulo(
            rejilla, 0, 0, "\U0001F4BE", COL_ACENTO, "Analizador de discos",
            "Escanea unidades completas, clasifica cada archivo por tipo y "
            "descubre que esta ocupando tu espacio.",
            f"▸ {len(discos)} {self.t('unidades listas para analizar')}",
            self.mostrar_discos)

        self._tarjeta_modulo(
            rejilla, 0, 1, "\U0001F9F9", COL_VERDE, "Limpieza rapida",
            "Elimina temporales, caches de navegadores y restos de Windows "
            "Update que se regeneran solos.",
            f"▸ {len(limpiezas_disponibles())} {self.t('objetivos de limpieza')}",
            self.mostrar_limpieza)

        self._tarjeta_modulo(
            rejilla, 0, 2, "⚙", COL_VIOLETA, "Configuracion",
            "Ajustes globales de la aplicacion: carpeta de destino para mover "
            "archivos, tema y tutorial.",
            "▸ Preferencias de la aplicacion",
            self.mostrar_configuracion)

    def _mini_stat(self, padre, valor, etiqueta, color):
        etiqueta = self.t(etiqueta)
        card = ctk.CTkFrame(padre, fg_color=COL_PANEL, corner_radius=12,
                            border_width=1, border_color=COL_BORDE)
        card.pack(side="left", padx=(0, 12), ipadx=18, ipady=4)
        ctk.CTkLabel(card, text=valor, font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=color).pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(card, text=etiqueta.upper(),
                     font=ctk.CTkFont(family=FUENTE_MONO, size=10),
                     text_color=COL_TEXTO_TENUE).pack(anchor="w", padx=14, pady=(0, 10))

    def _tarjeta_modulo(self, padre, r, c, icono, color, titulo, desc, estado, comando):
        card = ctk.CTkFrame(padre, corner_radius=20, fg_color=COL_PANEL,
                            border_width=1, border_color=COL_BORDE)
        card.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        fila = ctk.CTkFrame(inner, fg_color="transparent")
        fila.pack(fill="x")
        ctk.CTkLabel(fila, text=icono, font=ctk.CTkFont(size=46),
                     text_color=color).pack(side="left")
        ctk.CTkLabel(fila, text="↗", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COL_TEXTO_TENUE).pack(side="right")

        ctk.CTkLabel(inner, text=titulo, font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COL_TEXTO).pack(anchor="w", pady=(14, 4))
        ctk.CTkLabel(inner, text=desc, font=ctk.CTkFont(size=14),
                     text_color=COL_TEXTO_TENUE, wraplength=300,
                     justify="left").pack(anchor="w")
        ctk.CTkLabel(inner, text=estado,
                     font=ctk.CTkFont(family=FUENTE_MONO, size=13),
                     text_color=color).pack(anchor="w", pady=(16, 0))

        def entrar(_=None):
            card.configure(border_color=color)

        def salir(_=None):
            card.configure(border_color=COL_BORDE)

        def abrir(_=None):
            comando()

        widgets = [card, inner, fila, *inner.winfo_children(), *fila.winfo_children()]
        for w in widgets:
            w.bind("<Button-1>", abrir)
            w.bind("<Enter>", entrar)
            w.bind("<Leave>", salir)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

    # ==========================================================================
    #  MODULO: DISCOS  (tabs: Escanear / Resultados / Programas)
    # ==========================================================================
    def mostrar_discos(self):
        self.mostrar_discos_escanear()

    def _tabs_discos(self, marco, activa):
        self._barra_tabs(marco, [
            ("escanear", "⌖  Escanear", self.mostrar_discos_escanear),
            ("resultados", "▤  Resultados", self.mostrar_discos_resultados),
            ("programas", "▦  Programas", self.mostrar_discos_programas),
        ], activa)

    # ---------- Tab: escanear -------------------------------------------------
    def mostrar_discos_escanear(self):
        if self._escaneando:
            return
        self._limpiar_contenedor()
        self._marcar_vista("discos", self.mostrar_discos_escanear)
        self._vista_actual = "discos_escanear"

        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=34, pady=26)

        self._cabecera(marco, "modulo // discos", "Analizador de discos",
                       "Selecciona una unidad: se recorrera entera y se clasificara cada archivo por tipo.")
        self._tabs_discos(marco, "escanear")

        # detectar tipo de disco (SSD/NVMe/HDD) en segundo plano la primera vez
        self._asegurar_tipos_disco()

        # tarjetas de discos
        fila = ctk.CTkFrame(marco, fg_color="transparent")
        fila.pack(fill="x")
        self._tarjetas_disco = {}
        for i, d in enumerate(listar_discos()):
            self._tarjeta_disco(fila, d, i)

        # aviso segun el tipo del disco seleccionado (nvme: nada)
        if self.disco_sel:
            info = self._tipos_disco.get(self.disco_sel["letra"])
            if info:
                texto, color = aviso_disco(info["tipo"])
                if texto:
                    aviso = ctk.CTkFrame(marco, fg_color=COL_PANEL, corner_radius=10,
                                         border_width=1, border_color=color)
                    aviso.pack(fill="x", pady=(14, 0))
                    ctk.CTkLabel(aviso, text=f"⏱  {self.t(texto)}",
                                 font=ctk.CTkFont(size=13, weight="bold"),
                                 text_color=color).pack(anchor="w", padx=16, pady=10)

        # opciones propias del modulo
        opciones = ctk.CTkFrame(marco, fg_color=COL_PANEL, corner_radius=12,
                                border_width=1, border_color=COL_BORDE)
        opciones.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(opciones, text="▞▞ AJUSTES DEL ESCANEO",
                     font=ctk.CTkFont(family=FUENTE_MONO, size=10, weight="bold"),
                     text_color=COL_TEXTO_TENUE).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkCheckBox(opciones,
                        text="Omitir carpetas del sistema (Windows, Program Files) - mas rapido",
                        variable=self.omitir_sistema,
                        font=ctk.CTkFont(size=12),
                        text_color=COL_TEXTO_TENUE,
                        fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV,
                        checkmark_color=COL_ACENTO_TXT).pack(anchor="w", padx=16, pady=(0, 14))

        # boton escanear
        self._btn_escanear = ctk.CTkButton(
            marco, text="▶   INICIAR ESCANEO", height=52, width=260,
            corner_radius=26, font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV,
            text_color=COL_ACENTO_TXT,
            command=self.iniciar_escaneo)
        self._btn_escanear.pack(pady=(24, 6))
        if self.disco_sel is None:
            self._btn_escanear.configure(state="disabled")

        # zona de progreso (oculta al inicio)
        self._zona_progreso = ctk.CTkFrame(marco, fg_color="transparent")
        self._zona_progreso.pack(fill="x", pady=(10, 0))

    def _tarjeta_disco(self, padre, d, idx):
        seleccionada = (self.disco_sel and self.disco_sel["letra"] == d["letra"])
        borde = COL_ACENTO if seleccionada else COL_BORDE
        card = ctk.CTkFrame(padre, width=210, height=124, corner_radius=14,
                            fg_color=COL_PANEL, border_width=2, border_color=borde)
        card.grid(row=0, column=idx, padx=8, pady=8, sticky="w")
        card.grid_propagate(False)

        ctk.CTkLabel(card, text=f"\U0001F4BE  {self.t('Disco')} {d['letra']}:",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COL_ACENTO if seleccionada else COL_TEXTO).place(x=14, y=12)

        # badge con el tipo de disco (NVMe / SSD / HDD), si ya se detecto
        info = self._tipos_disco.get(d["letra"])
        if info and info["tipo"] in ETIQUETA_DISCO:
            col_badge = {"nvme": COL_VERDE, "ssd": COL_AMBAR,
                         "hdd": COL_NARANJA}[info["tipo"]]
            ctk.CTkLabel(card, text=f" {ETIQUETA_DISCO[info['tipo']]} ",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=col_badge, fg_color=COL_SIDEBAR,
                         corner_radius=5).place(x=150, y=14)
        elif self._tipos_disco_cargando:
            ctk.CTkLabel(card, text="···", font=ctk.CTkFont(size=12),
                         text_color=COL_TEXTO_TENUE).place(x=176, y=14)

        pct = d["usado"] / d["total"] if d["total"] else 0
        barra = ctk.CTkProgressBar(card, width=180, height=8,
                                   progress_color=COL_ACENTO, fg_color=COL_SIDEBAR)
        barra.set(pct)
        barra.place(x=14, y=52)

        ctk.CTkLabel(card,
                     text=f"{formato_tamano(d['usado'])} {self.t('usados de')} {formato_tamano(d['total'])}",
                     font=ctk.CTkFont(size=11), text_color=COL_TEXTO_TENUE).place(x=14, y=66)
        ctk.CTkLabel(card, text=f"{formato_tamano(d['libre'])} {self.t('libres')}",
                     font=ctk.CTkFont(size=11), text_color=COL_VERDE).place(x=14, y=90)

        def elegir(_=None, disco=d):
            self.disco_sel = disco
            self.mostrar_discos_escanear()

        for w in (card, *card.winfo_children()):
            w.bind("<Button-1>", elegir)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

    # ---------- Escaneo de disco (hilo) ---------------------------------------
    def iniciar_escaneo(self):
        if self.disco_sel is None or self._escaneando:
            return
        self._escaneando = True
        self._cancelar = False
        self._p_count = 0
        self._p_size = 0
        self._p_actual = ""
        self._p_terminado = False
        self._t_inicio = time.time()

        self._btn_escanear.configure(state="disabled", text=self.t("ESCANEANDO..."))

        # UI de progreso
        for w in self._zona_progreso.winfo_children():
            w.destroy()
        self._prog_barra = ctk.CTkProgressBar(self._zona_progreso, height=10,
                                              mode="indeterminate",
                                              progress_color=COL_ACENTO,
                                              fg_color=COL_PANEL)
        self._prog_barra.pack(fill="x", pady=(6, 8))
        self._prog_barra.start()
        self._prog_txt = ctk.CTkLabel(self._zona_progreso, text="Iniciando...",
                                      font=ctk.CTkFont(size=13, weight="bold"),
                                      text_color=COL_TEXTO)
        self._prog_txt.pack(anchor="w")
        self._prog_sub = ctk.CTkLabel(self._zona_progreso, text="",
                                      font=ctk.CTkFont(family=FUENTE_MONO, size=11),
                                      text_color=COL_TEXTO_TENUE)
        self._prog_sub.pack(anchor="w")
        self._btn_cancelar = ctk.CTkButton(
            self._zona_progreso, text="Cancelar", width=120, height=34,
            fg_color="transparent", border_width=1, border_color=COL_ROJO,
            text_color=COL_ROJO, hover_color=COL_PANEL,
            command=self.cancelar_escaneo)
        self._btn_cancelar.pack(anchor="w", pady=10)

        hilo = threading.Thread(target=self._trabajo_escaneo,
                                args=(self.disco_sel["raiz"],), daemon=True)
        hilo.start()
        self.after(120, self._refrescar_progreso)

    def cancelar_escaneo(self):
        self._cancelar = True

    def _trabajo_escaneo(self, raiz):
        cats = {n: {"size": 0, "count": 0, "heap": []} for n in CATEGORIAS}
        progs = {}          # nombre de programa -> datos
        omitir = self.omitir_sistema.get()
        rutas_omitir = []
        if omitir:
            letra = raiz[0]
            rutas_omitir = [
                f"{letra}:\\windows",
                f"{letra}:\\program files",
                f"{letra}:\\program files (x86)",
                f"{letra}:\\programdata",
                f"{letra}:\\$recycle.bin",
            ]
        contador = 0
        acum_size = 0
        for dirpath, dirnames, filenames in os.walk(raiz, onerror=lambda e: None):
            if self._cancelar:
                break
            dp_min = dirpath.lower()
            if omitir and any(dp_min.startswith(x) for x in rutas_omitir):
                dirnames[:] = []
                continue
            for f in filenames:
                if self._cancelar:
                    break
                ruta = os.path.join(dirpath, f)
                try:
                    size = os.path.getsize(ruta)
                except OSError:
                    continue
                ext = os.path.splitext(f)[1].lower()
                ruta_min = ruta.lower()
                cat = clasificar(ruta_min, ext)
                d = cats[cat]
                d["size"] += size
                d["count"] += 1
                h = d["heap"]
                if len(h) < MAX_GUARDAR:
                    heapq.heappush(h, (size, ruta))
                elif h[0][0] < size:
                    heapq.heappushpop(h, (size, ruta))

                # agrupar por programa instalado
                nombre_prog, base_prog = detectar_programa(ruta_min, ruta)
                if nombre_prog:
                    p = progs.get(nombre_prog)
                    if p is None:
                        p = {"size": 0, "count": 0, "heap": [], "base": base_prog,
                             "exe": None}
                        progs[nombre_prog] = p
                    p["size"] += size
                    p["count"] += 1
                    hp = p["heap"]
                    if len(hp) < 300:
                        heapq.heappush(hp, (size, ruta))
                    elif hp[0][0] < size:
                        heapq.heappushpop(hp, (size, ruta))
                    if ext == ".exe" and (p["exe"] is None or size > p["exe"][0]):
                        p["exe"] = (size, ruta)
                contador += 1
                acum_size += size
                if (contador & 0x3FF) == 0:      # cada 1024 archivos
                    self._p_count = contador
                    self._p_size = acum_size
                    self._p_actual = dirpath

        self._p_count = contador
        self._p_size = acum_size
        # ordenar de mayor a menor para mostrar
        for n, d in cats.items():
            d["items"] = sorted(d["heap"], reverse=True)
            d.pop("heap", None)
        for n, p in progs.items():
            p["items"] = sorted(p["heap"], reverse=True)
            p.pop("heap", None)
        self.resultado = cats
        self.resultado_programas = progs
        self._cache_iconos = {}
        self._p_terminado = True

    def _refrescar_progreso(self):
        if not self._escaneando:
            return
        seg = max(0.001, time.time() - self._t_inicio)
        vel = self._p_count / seg
        try:
            self._prog_txt.configure(
                text=f"{self.t('Analizando...')}  {self._p_count:,} {self.t('archivos')}"
                     f"  -  {formato_tamano(self._p_size)}"
                .replace(",", "."))
            actual = self._p_actual
            if len(actual) > 70:
                actual = "..." + actual[-67:]
            self._prog_sub.configure(
                text=f"{actual}    ({int(vel):,} {self.t('archivos/seg')})".replace(",", "."))
        except Exception:
            pass

        if self._p_terminado:
            self._escaneando = False
            try:
                self._prog_barra.stop()
            except Exception:
                pass
            self.mostrar_discos_resultados()
            return
        self.after(150, self._refrescar_progreso)

    # ---------- Tab: resultados ------------------------------------------------
    def mostrar_discos_resultados(self):
        self._limpiar_contenedor()
        self._marcar_vista("discos", self.mostrar_discos_resultados)
        self._vista_actual = "discos_resultados"

        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=34, pady=26)

        if self.resultado is None:
            self._cabecera(marco, "modulo // discos", "Resultados")
            self._tabs_discos(marco, "resultados")
            self._estado_vacio(marco, "\U0001F4BE",
                               "Todavia no hay resultados",
                               "Escanea primero una unidad para ver el desglose por categorias.",
                               "Ir a escanear", self.mostrar_discos_escanear)
            return

        total_size = sum(d["size"] for d in self.resultado.values())
        total_count = sum(d["count"] for d in self.resultado.values())

        self._cabecera(marco, "modulo // discos",
                       f"{self.t('Resultados')} · {self.t('Disco')} {self.disco_sel['letra']}:",
                       f"{formato_tamano(total_size)} {self.t('en')} {total_count:,} "
                       f"{self.t('archivos analizados')}".replace(",", "."))
        self._tabs_discos(marco, "resultados")

        ordenadas = sorted(self.resultado.items(),
                           key=lambda kv: kv[1]["size"], reverse=True)

        # grafico circular (donut) interactivo con el reparto del disco
        panel = ctk.CTkFrame(marco, fg_color=COL_PANEL, corner_radius=14,
                             border_width=1, border_color=COL_BORDE)
        panel.pack(fill="x", pady=(4, 12))
        self._grafico_disco(panel, ordenadas, total_size, total_count)

        # rejilla de tarjetas por categoria
        rejilla = ctk.CTkScrollableFrame(marco, fg_color="transparent")
        rejilla.pack(fill="both", expand=True)
        for c in range(4):
            rejilla.grid_columnconfigure(c, weight=1, uniform="cat")

        idx = 0
        for nombre, datos in ordenadas:
            if datos["count"] == 0:
                continue
            self._tarjeta_categoria(rejilla, nombre, datos, total_size,
                                    idx // 4, idx % 4)
            idx += 1

    def _abrir_categoria(self, nombre):
        if nombre == "Programas" and self.resultado_programas:
            self.mostrar_discos_programas()
        else:
            self.mostrar_detalle(nombre)

    def _grafico_disco(self, padre, ordenadas, total_size, total_count):
        """Donut interactivo: cada porcion es una categoria; al pasar el cursor
        la porcion se separa un poco y el centro muestra el detalle."""
        import math
        cats = [(n, d) for n, d in ordenadas if d["count"] > 0 and d["size"] > 0]
        if not cats or total_size <= 0:
            return

        cont = ctk.CTkFrame(padre, fg_color="transparent")
        cont.pack(fill="x", padx=18, pady=16)

        SZ, R, RIN = 250, 112, 60
        cx = cy = SZ // 2
        canvas = tk.Canvas(cont, width=SZ, height=SZ, bg=COL_PANEL,
                           highlightthickness=0, bd=0)
        canvas.pack(side="left", padx=(4, 26))

        slices = {}
        ang = 90.0                       # empezar arriba
        for nombre, datos in cats:
            ext = 360.0 * datos["size"] / total_size
            if ext <= 0:
                continue
            color = CATEGORIAS[nombre][1]
            item = canvas.create_arc(cx - R, cy - R, cx + R, cy + R,
                                     start=ang, extent=-ext, fill=color,
                                     outline=COL_PANEL, width=2, style="pieslice")
            slices[nombre] = {"id": item, "mid": ang - ext / 2.0, "a0": ang,
                              "ext": ext, "color": color, "datos": datos, "out": False}
            ang -= ext

        # agujero central (efecto donut)
        canvas.create_oval(cx - RIN, cy - RIN, cx + RIN, cy + RIN,
                           fill=COL_PANEL, outline="")
        t_val = canvas.create_text(cx, cy - 12, text=formato_tamano(total_size),
                                   fill=COL_TEXTO, font=(FUENTE_MONO, 15, "bold"))
        t_nom = canvas.create_text(cx, cy + 8, text=self.t("en total"),
                                   fill=COL_TEXTO_TENUE, font=(FUENTE_MONO, 10))
        t_sub = canvas.create_text(cx, cy + 24,
                                   text=f"{total_count:,} {self.t('archivos')}".replace(",", "."),
                                   fill=COL_TEXTO_TENUE, font=(FUENTE_MONO, 9))

        # porcion actualmente resaltada (evita repetir trabajo y bucles de eventos)
        estado = {"hover": None}

        def explotar(nombre, on):
            s = slices[nombre]
            if s["out"] == on:
                return
            m = math.radians(s["mid"])
            dx, dy = 12 * math.cos(m), -12 * math.sin(m)
            if not on:
                dx, dy = -dx, -dy
            canvas.move(s["id"], dx, dy)
            s["out"] = on

        def resaltar(nombre):
            if estado["hover"] == nombre:
                return
            estado["hover"] = nombre
            for n in slices:
                explotar(n, n == nombre)
            s = slices[nombre]
            d = s["datos"]
            pct = 100.0 * d["size"] / total_size
            canvas.itemconfig(t_val, text=formato_tamano(d["size"]), fill=s["color"])
            canvas.itemconfig(t_nom, text=self.t(nombre))
            canvas.itemconfig(t_sub,
                              text=f"{pct:.1f}%  ·  {d['count']:,} {self.t('arch.')}".replace(",", "."))

        def restaurar(_=None):
            if estado["hover"] is None:
                return
            estado["hover"] = None
            for n in slices:
                explotar(n, False)
            canvas.itemconfig(t_val, text=formato_tamano(total_size), fill=COL_TEXTO)
            canvas.itemconfig(t_nom, text=self.t("en total"))
            canvas.itemconfig(t_sub,
                              text=f"{total_count:,} {self.t('archivos')}".replace(",", "."))

        def porcion_en(x, y):
            """Que porcion hay bajo (x,y), por ANGULO (no por la geometria del
            arco, que se mueve al explotar -> evita el bucle de eventos)."""
            dx, dy = x - cx, cy - y          # invertir Y (el canvas crece hacia abajo)
            r = math.hypot(dx, dy)
            if r < RIN * 0.7 or r > R + 18:
                return None
            theta = math.degrees(math.atan2(dy, dx)) % 360.0
            for nombre, s in slices.items():
                if (s["a0"] - theta) % 360.0 < s["ext"]:
                    return nombre
            return None

        def on_motion(e):
            n = porcion_en(e.x, e.y)
            if n is None:
                restaurar()
            else:
                resaltar(n)

        def on_click(e):
            n = porcion_en(e.x, e.y)
            if n is not None:
                self._abrir_categoria(n)

        canvas.bind("<Motion>", on_motion)
        canvas.bind("<Leave>", restaurar)
        canvas.bind("<Button-1>", on_click)

        # ---- leyenda a la derecha ----
        leyenda = ctk.CTkFrame(cont, fg_color="transparent")
        leyenda.pack(side="left", fill="both", expand=True, pady=4)
        for nombre, datos in cats:
            color = CATEGORIAS[nombre][1]
            pct = 100.0 * datos["size"] / total_size
            row = ctk.CTkFrame(leyenda, fg_color="transparent")
            row.pack(fill="x", pady=1)
            sw = ctk.CTkFrame(row, width=12, height=12, fg_color=color, corner_radius=3)
            sw.pack(side="left", padx=(0, 10))
            sw.pack_propagate(False)
            ctk.CTkLabel(row, text=nombre, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=COL_TEXTO, anchor="w", width=170).pack(side="left")
            ctk.CTkLabel(row, text=formato_tamano(datos["size"]),
                         font=ctk.CTkFont(size=13, weight="bold"), text_color=color,
                         width=90, anchor="e").pack(side="left", padx=(0, 12))
            ctk.CTkLabel(row, text=f"{pct:.1f}%",
                         font=ctk.CTkFont(family=FUENTE_MONO, size=11),
                         text_color=COL_TEXTO_TENUE, width=52, anchor="e").pack(side="left")
            for w in (row, *row.winfo_children()):
                w.bind("<Enter>", lambda e, n=nombre: resaltar(n))
                w.bind("<Leave>", restaurar)
                w.bind("<Button-1>", lambda e, n=nombre: self._abrir_categoria(n))
                try:
                    w.configure(cursor="hand2")
                except Exception:
                    pass

    def _estado_vacio(self, padre, icono, titulo, texto, boton_txt, comando):
        card = ctk.CTkFrame(padre, fg_color=COL_PANEL, corner_radius=16,
                            border_width=1, border_color=COL_BORDE)
        card.pack(fill="x", pady=20)
        ctk.CTkLabel(card, text=icono, font=ctk.CTkFont(size=40),
                     text_color=COL_TEXTO_TENUE).pack(pady=(28, 6))
        ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=COL_TEXTO).pack()
        ctk.CTkLabel(card, text=texto, font=ctk.CTkFont(size=12),
                     text_color=COL_TEXTO_TENUE).pack(pady=(4, 14))
        ctk.CTkButton(card, text=boton_txt, height=38, width=180, corner_radius=10,
                      fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV,
                      text_color=COL_ACENTO_TXT,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=comando).pack(pady=(0, 28))

    def _tarjeta_categoria(self, padre, nombre, datos, total_size, r, c):
        emoji, color, _ = CATEGORIAS[nombre]
        card = ctk.CTkFrame(padre, height=150, corner_radius=14,
                            fg_color=COL_PANEL, border_width=1, border_color=COL_BORDE)
        card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
        card.grid_propagate(False)

        ctk.CTkLabel(card, text=emoji, font=ctk.CTkFont(size=30)).place(x=16, y=14)
        ctk.CTkLabel(card, text=nombre, font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COL_TEXTO, wraplength=160, justify="left").place(x=64, y=18)

        ctk.CTkLabel(card, text=formato_tamano(datos["size"]),
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=color).place(x=16, y=62)
        ctk.CTkLabel(card, text=f"{datos['count']:,} {self.t('archivos')}".replace(",", "."),
                     font=ctk.CTkFont(size=12), text_color=COL_TEXTO_TENUE).place(x=16, y=96)

        pct = datos["size"] / total_size if total_size else 0
        barra = ctk.CTkProgressBar(card, height=6, progress_color=color,
                                   fg_color=COL_SIDEBAR)
        barra.set(pct)
        barra.place(x=16, y=124, relwidth=0.86)

        def abrir(_=None, n=nombre):
            self._abrir_categoria(n)

        for w in (card, *card.winfo_children()):
            w.bind("<Button-1>", abrir)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

    # ---------- Vista: detalle de categoria ----------------------------------
    def mostrar_detalle(self, nombre):
        datos = self.resultado[nombre]
        emoji, color, _ = CATEGORIAS[nombre]
        self._limpiar_contenedor()
        self._marcar_vista("discos", lambda: self.mostrar_detalle(nombre))
        self._vista_actual = "discos_detalle"
        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=34, pady=24)

        cab = ctk.CTkFrame(marco, fg_color="transparent")
        cab.pack(fill="x")
        ctk.CTkButton(cab, text="←  Volver", width=110, height=36,
                      corner_radius=8, fg_color=COL_PANEL, hover_color=COL_PANEL_HOVER,
                      command=self.mostrar_discos_resultados).pack(side="left")
        ctk.CTkLabel(cab, text=f"   {emoji}  {self.t(nombre)}",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COL_TEXTO).pack(side="left")

        ctk.CTkLabel(marco,
                     text=f"{formato_tamano(datos['size'])}  {self.t('en')}  "
                          f"{datos['count']:,} {self.t('archivos')}"
                     .replace(",", "."),
                     font=ctk.CTkFont(size=14), text_color=color).pack(anchor="w", pady=(6, 4))

        items = datos["items"]
        nota = (f"{self.t('Mostrando los')} {min(len(items), MAX_MOSTRAR)} "
                f"{self.t('archivos mas grandes')}")
        if datos["count"] > len(items):
            nota += f" ({self.t('de')} {datos['count']:,} {self.t('en total')})".replace(",", ".")
        ctk.CTkLabel(marco, text=nota, font=ctk.CTkFont(size=11),
                     text_color=COL_TEXTO_TENUE).pack(anchor="w")

        # barra de acciones
        acciones = ctk.CTkFrame(marco, fg_color="transparent")
        acciones.pack(fill="x", pady=(10, 6))
        self._acciones_frame = acciones
        ctk.CTkButton(acciones, text="\U0001F5D1  Enviar a la papelera",
                      height=38, corner_radius=8, fg_color=COL_ROJO,
                      hover_color=COL_ROJO_HOV,
                      command=lambda n=nombre: self._borrar_seleccionados(n)
                      ).pack(side="left")
        ctk.CTkButton(acciones, text="\U0001F4C1  Mover a carpeta de basura",
                      height=38, corner_radius=8, fg_color=COL_SIDEBAR,
                      hover_color=COL_PANEL_HOVER, border_width=1, border_color=COL_BORDE,
                      command=lambda n=nombre: self._mover_seleccionados(n)
                      ).pack(side="left", padx=(10, 0))

        # cabecera de la lista
        lista = ctk.CTkScrollableFrame(marco, fg_color=COL_PANEL, corner_radius=12)
        lista.pack(fill="both", expand=True, pady=(6, 0))
        lista.grid_columnconfigure(1, weight=1)

        # se renderiza por paginas (60 filas) con un boton "Cargar mas"
        self._checks_detalle = []   # (var, ruta)  se acumula entre paginas
        self._det_lista = lista
        self._det_items = items[:MAX_MOSTRAR]
        self._det_color = color
        self._det_cursor = 0
        self._det_boton_mas = None
        self._render_pagina_detalle()

    def _render_pagina_detalle(self):
        PAGINA = 60
        if self._det_boton_mas is not None:
            self._det_boton_mas.destroy()
            self._det_boton_mas = None
        ini = self._det_cursor
        fin = min(ini + PAGINA, len(self._det_items))
        self._det_cursor = fin
        indices = list(range(ini, fin))

        barra = self._barra_carga(self._det_lista, COL_PANEL, "Cargando archivos...")
        barra.grid(row=len(self._det_items) + 2, column=0, columnspan=4,
                   sticky="w", padx=10, pady=10)

        def construir(i):
            size, ruta = self._det_items[i]
            self._fila_archivo(self._det_lista, i, size, ruta, self._det_color)

        def terminado():
            try:
                barra.destroy()
            except Exception:
                pass
            if self._det_cursor < len(self._det_items):
                restantes = len(self._det_items) - self._det_cursor
                self._det_boton_mas = ctk.CTkButton(
                    self._det_lista,
                    text=f"{self.t('Cargar mas')}  ({restantes} {self.t('restantes')})",
                    height=38, corner_radius=8, fg_color=COL_PANEL_2,
                    hover_color=COL_PANEL_HOVER, text_color=COL_TEXTO,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    command=self._render_pagina_detalle)
                self._det_boton_mas.grid(row=len(self._det_items) + 1, column=0,
                                         columnspan=4, sticky="ew", padx=6, pady=(8, 4))

        self._stream_filas("_det_tok", self._det_lista, indices, construir,
                           al_terminar=terminado, barra=barra)

    def _fila_archivo(self, padre, i, size, ruta, color):
        fondo = COL_PANEL if i % 2 == 0 else COL_PANEL_2
        fila = ctk.CTkFrame(padre, fg_color=fondo, corner_radius=6)
        fila.grid(row=i, column=0, columnspan=4, sticky="ew", padx=4, pady=1)
        fila.grid_columnconfigure(1, weight=1)

        var = ctk.BooleanVar(value=False)
        self._checks_detalle.append((var, ruta))
        ctk.CTkCheckBox(fila, text="", variable=var, width=24,
                        fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV,
                        checkmark_color=COL_ACENTO_TXT
                        ).grid(row=0, column=0, padx=(8, 4), pady=6)

        nombre = os.path.basename(ruta)
        carpeta = os.path.dirname(ruta)
        texto = ctk.CTkFrame(fila, fg_color="transparent")
        texto.grid(row=0, column=1, sticky="ew", padx=4)

        linea = ctk.CTkFrame(texto, fg_color="transparent")
        linea.pack(anchor="w")
        ctk.CTkLabel(linea, text=nombre, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COL_TEXTO, anchor="w").pack(side="left")
        origen = procedencia(ruta)
        if origen:
            ctk.CTkLabel(linea, text=f"  {self.t(origen)}  ", font=ctk.CTkFont(size=10),
                         text_color=COL_ACENTO, fg_color=COL_SIDEBAR,
                         corner_radius=6).pack(side="left", padx=(8, 0))

        cp = carpeta if len(carpeta) < 80 else "..." + carpeta[-77:]
        ctk.CTkLabel(texto, text=cp, font=ctk.CTkFont(family=FUENTE_MONO, size=10),
                     text_color=COL_TEXTO_TENUE, anchor="w").pack(anchor="w")

        ctk.CTkLabel(fila, text=formato_tamano(size),
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=color, width=90).grid(row=0, column=2, padx=8)

        ctk.CTkButton(fila, text="▶  Abrir", width=76, height=28, corner_radius=6,
                      fg_color=COL_SIDEBAR, hover_color=COL_PANEL_HOVER,
                      command=lambda r=ruta: self._abrir_archivo(r)
                      ).grid(row=0, column=3, padx=(4, 4))

        ctk.CTkButton(fila, text="\U0001F4C2  Ubicacion", width=96, height=28, corner_radius=6,
                      fg_color=COL_SIDEBAR, hover_color=COL_PANEL_HOVER,
                      command=lambda r=ruta: self._abrir_ubicacion(r)
                      ).grid(row=0, column=4, padx=(0, 10))

    # ---------- Acciones sobre archivos --------------------------------------
    def _abrir_archivo(self, ruta):
        """Abre el archivo con su programa predeterminado (doble clic virtual)."""
        try:
            if os.path.exists(ruta):
                os.startfile(os.path.normpath(ruta))
            else:
                messagebox.showwarning(self.t("No encontrado"), self.t("El archivo ya no existe."))
        except OSError as e:
            messagebox.showerror(
                self.t("No se pudo abrir"),
                self.t("Windows no tiene un programa asociado para este tipo de archivo\n"
                       "o hubo un error al abrirlo:") + f"\n{e}")

    def _abrir_ubicacion(self, ruta):
        try:
            if os.path.exists(ruta):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(ruta)])
            else:
                messagebox.showwarning(self.t("No encontrado"), self.t("El archivo ya no existe."))
        except Exception as e:
            messagebox.showerror(self.t("Error"), self.t("No se pudo abrir la ubicacion:") + f"\n{e}")

    def _borrar_seleccionados(self, nombre):
        sel = [r for var, r in self._checks_detalle if var.get()]
        if not sel:
            messagebox.showinfo(self.t("Nada seleccionado"),
                                self.t("Marca primero los archivos que quieres eliminar."))
            return
        if not HAY_PAPELERA:
            messagebox.showerror(self.t("Falta libreria"),
                                 self.t("Send2Trash no esta instalado, no se puede borrar de forma segura."))
            return
        if not messagebox.askyesno(
                self.t("Confirmar"),
                self.t("Se enviaran {n} archivo(s) a la PAPELERA de reciclaje.").format(n=len(sel))
                + "\n" + self.t("Podras recuperarlos desde ahi.")
                + "\n\n" + self.t("Continuar?")):
            return

        borrados, fallos, liberado = 0, 0, 0
        rutas_ok = set()
        for r in sel:
            try:
                tam = os.path.getsize(r) if os.path.exists(r) else 0
                send2trash(r)
                borrados += 1
                liberado += tam
                rutas_ok.add(r)
            except Exception:
                fallos += 1

        # actualizar datos en memoria
        datos = self.resultado[nombre]
        datos["items"] = [(s, r) for (s, r) in datos["items"] if r not in rutas_ok]
        datos["count"] -= borrados
        datos["size"] = max(0, datos["size"] - liberado)

        messagebox.showinfo(
            self.t("Hecho"),
            self.t("Enviados a la papelera: {n}").format(n=borrados) + "\n"
            + self.t("Espacio liberado: {t}").format(t=formato_tamano(liberado))
            + (("\n" + self.t("No se pudieron borrar: {n}").format(n=fallos)) if fallos else ""))
        self.mostrar_detalle(nombre)

    def _mover_seleccionados(self, nombre):
        destino_base = self.config.get("carpeta_basura")
        if not destino_base or not os.path.isdir(destino_base):
            if messagebox.askyesno(
                    self.t("Carpeta no configurada"),
                    self.t("Todavia no has elegido una carpeta de destino.") + "\n\n"
                    + self.t("¿Quieres configurarla ahora?")):
                self.mostrar_configuracion()
            return

        sel = [r for var, r in self._checks_detalle if var.get()]
        if not sel:
            messagebox.showinfo(self.t("Nada seleccionado"),
                                self.t("Marca primero los archivos que quieres mover."))
            return

        try:
            total = sum(os.path.getsize(r) for r in sel if os.path.exists(r))
        except OSError:
            total = 0

        if not messagebox.askyesno(
                self.t("Confirmar movimiento"),
                self.t("Se moveran {n} archivo(s)  ({t})  a:").format(n=len(sel), t=formato_tamano(total))
                + f"\n{destino_base}\n\n" + self.t("¿Continuar?")):
            return

        self._mov_hecho = 0
        self._mov_total = total
        self._mov_terminado = False
        self._mov_resultado = None

        self._mostrar_progreso_mover()
        threading.Thread(target=self._trabajo_mover,
                         args=(destino_base, nombre, sel), daemon=True).start()
        self.after(150, self._refrescar_progreso_mover, nombre)

    def _mostrar_progreso_mover(self):
        for w in self._acciones_frame.winfo_children():
            w.destroy()
        self._mov_barra = ctk.CTkProgressBar(self._acciones_frame, width=300, height=10,
                                             progress_color=COL_ACENTO, fg_color=COL_PANEL)
        self._mov_barra.set(0)
        self._mov_barra.pack(side="left", padx=(0, 12))
        self._mov_lbl = ctk.CTkLabel(self._acciones_frame, text=self.t("Moviendo archivos..."),
                                     font=ctk.CTkFont(size=12), text_color=COL_TEXTO_TENUE)
        self._mov_lbl.pack(side="left")

    def _ruta_destino_libre(self, carpeta, nombre_archivo):
        destino = os.path.join(carpeta, nombre_archivo)
        if not os.path.exists(destino):
            return destino
        base, ext = os.path.splitext(nombre_archivo)
        i = 2
        while True:
            candidato = os.path.join(carpeta, f"{base} ({i}){ext}")
            if not os.path.exists(candidato):
                return candidato
            i += 1

    def _trabajo_mover(self, destino_base, categoria, rutas):
        carpeta_destino = os.path.join(destino_base, categoria)
        try:
            os.makedirs(carpeta_destino, exist_ok=True)
        except OSError:
            pass

        movidos, fallos, liberado = 0, 0, 0
        ok = set()
        for r in rutas:
            tam = 0
            try:
                if os.path.exists(r):
                    tam = os.path.getsize(r)
                destino = self._ruta_destino_libre(carpeta_destino, os.path.basename(r))
                shutil.move(r, destino)
                movidos += 1
                liberado += tam
                ok.add(r)
            except Exception:
                fallos += 1
            self._mov_hecho += tam

        self._mov_resultado = (movidos, fallos, liberado, ok)
        self._mov_terminado = True

    def _refrescar_progreso_mover(self, nombre):
        frac = min(1.0, self._mov_hecho / self._mov_total) if self._mov_total else 1.0
        try:
            self._mov_barra.set(frac)
            self._mov_lbl.configure(
                text=f"{self.t('Moviendo archivos...')}  {formato_tamano(self._mov_hecho)} / "
                     f"{formato_tamano(self._mov_total)}")
        except Exception:
            pass

        if self._mov_terminado:
            movidos, fallos, liberado, ok = self._mov_resultado
            datos = self.resultado[nombre]
            datos["items"] = [(s, r) for (s, r) in datos["items"] if r not in ok]
            datos["count"] -= movidos
            datos["size"] = max(0, datos["size"] - liberado)
            messagebox.showinfo(
                self.t("Hecho"),
                self.t("Movidos: {n}").format(n=movidos) + "\n"
                + self.t("Espacio liberado en este disco: {t}").format(t=formato_tamano(liberado))
                + (("\n" + self.t("No se pudieron mover: {n}").format(n=fallos)) if fallos else ""))
            self.mostrar_detalle(nombre)
            return
        self.after(150, self._refrescar_progreso_mover, nombre)

    # ---------- Tab: programas instalados --------------------------------------
    def mostrar_discos_programas(self):
        self._limpiar_contenedor()
        self._marcar_vista("discos", self.mostrar_discos_programas)
        self._vista_actual = "discos_programas"

        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=34, pady=26)

        if not self.resultado_programas:
            self._cabecera(marco, "modulo // discos", "Programas")
            self._tabs_discos(marco, "programas")
            self._estado_vacio(marco, "▦",
                               "Sin datos de programas",
                               "Escanea primero una unidad. Si ya lo hiciste, este disco no "
                               "tiene carpetas de programas (Program Files, ProgramData...).",
                               "Ir a escanear", self.mostrar_discos_escanear)
            return

        total = sum(p["size"] for p in self.resultado_programas.values())
        self._cabecera(marco, "modulo // discos",
                       f"{self.t('Programas')} · {self.t('Disco')} {self.disco_sel['letra']}:",
                       f"{len(self.resultado_programas)} {self.t('programas')} · "
                       f"{formato_tamano(total)} {self.t('en total')} "
                       f"{self.t('(pulsa uno para ver sus archivos)')}")
        self._tabs_discos(marco, "programas")

        fila_extra = ctk.CTkFrame(marco, fg_color="transparent")
        fila_extra.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(fila_extra, text="Archivos .exe/.dll sueltos", width=180, height=32,
                      corner_radius=8, fg_color=COL_PANEL, hover_color=COL_PANEL_HOVER,
                      command=lambda: self.mostrar_detalle("Programas")).pack(side="right")

        lista = ctk.CTkScrollableFrame(marco, fg_color="transparent")
        lista.pack(fill="both", expand=True)

        # se renderiza por paginas (60 filas cada vez) con un boton "Cargar mas"
        # para no construir cientos de widgets de golpe (congelaba la pantalla).
        self._prog_lista = lista
        self._prog_ordenados = sorted(self.resultado_programas.items(),
                                      key=lambda kv: kv[1]["size"], reverse=True)[:200]
        self._prog_cursor = 0
        self._prog_boton_mas = None

        # estado de carga de iconos en segundo plano (por lotes)
        self._token_iconos = object()
        self._iconos_pendientes = []
        self._iconos_lock = threading.Lock()
        self._iconos_threads_activos = 0
        self._icono_poll_activo = False

        self._render_pagina_programas()

    def _render_pagina_programas(self):
        PAGINA = 60
        if self._prog_boton_mas is not None:
            self._prog_boton_mas.destroy()
            self._prog_boton_mas = None

        ini = self._prog_cursor
        fin = min(ini + PAGINA, len(self._prog_ordenados))
        self._prog_cursor = fin
        indices = list(range(ini, fin))
        nuevas = []

        barra = self._barra_carga(self._prog_lista, COL_FONDO, "Cargando programas...")
        barra.pack(side="bottom", fill="x", pady=10)

        def construir(i):
            nombre, datos = self._prog_ordenados[i]
            nuevas.append(self._fila_programa(self._prog_lista, nombre, datos))

        def terminado():
            try:
                barra.destroy()
            except Exception:
                pass
            if self._prog_cursor < len(self._prog_ordenados):
                restantes = len(self._prog_ordenados) - self._prog_cursor
                self._prog_boton_mas = ctk.CTkButton(
                    self._prog_lista,
                    text=f"{self.t('Cargar mas')}  ({restantes} {self.t('restantes')})",
                    height=38, corner_radius=8, fg_color=COL_PANEL_2,
                    hover_color=COL_PANEL_HOVER, text_color=COL_TEXTO,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    command=self._render_pagina_programas)
                self._prog_boton_mas.pack(fill="x", pady=(10, 4))
            # cargar los iconos reales de las filas nuevas en segundo plano
            with self._iconos_lock:
                self._iconos_threads_activos += 1
            threading.Thread(target=self._cargar_iconos,
                             args=(self._token_iconos, nuevas), daemon=True).start()
            if not self._icono_poll_activo:
                self._icono_poll_activo = True
                self.after(50, self._vaciar_iconos_pendientes, self._token_iconos)

        self._stream_filas("_prog_tok", self._prog_lista, indices, construir,
                           al_terminar=terminado, barra=barra)

    def _fila_programa(self, padre, nombre, datos):
        card = ctk.CTkFrame(padre, fg_color=COL_PANEL, corner_radius=10,
                            border_width=1, border_color=COL_BORDE)
        card.pack(fill="x", pady=4)
        card.grid_columnconfigure(2, weight=1)

        lbl_icono = ctk.CTkLabel(card, text="⚙", font=ctk.CTkFont(size=22),
                                 width=44, text_color=COL_TEXTO_TENUE)
        lbl_icono.grid(row=0, column=0, rowspan=2, padx=(12, 4), pady=10)
        img = self._cache_iconos.get(nombre)
        if img is not None:
            lbl_icono.configure(image=img, text="")

        ctk.CTkLabel(card, text=nombre, font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COL_TEXTO, anchor="w").grid(
                     row=0, column=1, columnspan=2, sticky="w", pady=(10, 0))
        base = datos["base"]
        if len(base) > 80:
            base = "..." + base[-77:]
        ctk.CTkLabel(card, text=base, font=ctk.CTkFont(family=FUENTE_MONO, size=10),
                     text_color=COL_TEXTO_TENUE, anchor="w").grid(
                     row=1, column=1, columnspan=2, sticky="w", pady=(0, 10))

        ctk.CTkLabel(card, text=formato_tamano(datos["size"]),
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#06b6d4", width=100, anchor="e").grid(
                     row=0, column=3, rowspan=2, padx=(8, 2))
        ctk.CTkLabel(card, text=f"{datos['count']:,} {self.t('archivos')}".replace(",", "."),
                     font=ctk.CTkFont(size=11), text_color=COL_TEXTO_TENUE,
                     width=100, anchor="e").grid(row=0, column=4, rowspan=2, padx=(2, 14))

        def abrir(_=None, n=nombre):
            self.mostrar_detalle_programa(n)

        for w in (card, *card.winfo_children()):
            w.bind("<Button-1>", abrir)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass
        return {"nombre": nombre, "label": lbl_icono,
                "exe": datos["exe"][1] if datos["exe"] else None}

    def _cargar_iconos(self, token, filas):
        """Extrae los iconos (llamadas Win32 lentas) en un hilo aparte y los
        deja en una cola; el hilo NO toca widgets de Tk. Un unico sondeo en el
        hilo principal (_vaciar_iconos_pendientes) los aplica por lotes."""
        try:
            ctypes.windll.ole32.CoInitialize(None)
        except Exception:
            pass
        try:
            for fila in filas:
                if token is not self._token_iconos:
                    return
                if fila["nombre"] in self._cache_iconos or not fila["exe"]:
                    continue
                img = icono_de_exe(fila["exe"])
                if img is not None:
                    with self._iconos_lock:
                        self._iconos_pendientes.append((fila, img))
        finally:
            with self._iconos_lock:
                self._iconos_threads_activos -= 1

    def _vaciar_iconos_pendientes(self, token):
        if token is not self._token_iconos:
            self._icono_poll_activo = False
            return
        with self._iconos_lock:
            lote = self._iconos_pendientes
            self._iconos_pendientes = []
        for fila, img in lote:
            try:
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(28, 28))
                self._cache_iconos[fila["nombre"]] = ctk_img
                fila["label"].configure(image=ctk_img, text="")
            except Exception:
                pass
        with self._iconos_lock:
            quedan = self._iconos_threads_activos > 0 or bool(self._iconos_pendientes)
        if quedan:
            self.after(50, self._vaciar_iconos_pendientes, token)
        else:
            self._icono_poll_activo = False

    def mostrar_detalle_programa(self, nombre):
        datos = self.resultado_programas[nombre]
        self._limpiar_contenedor()
        self._marcar_vista("discos", lambda: self.mostrar_detalle_programa(nombre))
        self._vista_actual = "discos_detalle_programa"
        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=34, pady=24)

        cab = ctk.CTkFrame(marco, fg_color="transparent")
        cab.pack(fill="x")
        ctk.CTkButton(cab, text="←  Volver", width=110, height=36,
                      corner_radius=8, fg_color=COL_PANEL, hover_color=COL_PANEL_HOVER,
                      command=self.mostrar_discos_programas).pack(side="left")

        img = self._cache_iconos.get(nombre)
        if img is not None:
            ctk.CTkLabel(cab, text="", image=img).pack(side="left", padx=(14, 0))
        ctk.CTkLabel(cab, text=f"  {nombre}",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COL_TEXTO).pack(side="left")

        ctk.CTkButton(cab, text="Desinstalar desde Windows", width=190, height=36,
                      corner_radius=8, fg_color=COL_PANEL, hover_color=COL_PANEL_HOVER,
                      command=self._abrir_desinstalar).pack(side="right")
        ctk.CTkButton(cab, text="\U0001F4C2  Abrir carpeta", width=130, height=36,
                      corner_radius=8, fg_color=COL_PANEL, hover_color=COL_PANEL_HOVER,
                      command=lambda b=datos["base"]: self._abrir_carpeta(b)
                      ).pack(side="right", padx=8)

        ctk.CTkLabel(marco,
                     text=f"{formato_tamano(datos['size'])}  {self.t('en')}  "
                          f"{datos['count']:,} {self.t('archivos')}"
                     .replace(",", ".") + f"    -    {datos['base']}",
                     font=ctk.CTkFont(size=13), text_color="#06b6d4").pack(
                     anchor="w", pady=(8, 2))
        ctk.CTkLabel(marco,
                     text="Consejo: no borres archivos sueltos de un programa; si no lo usas, "
                          "desinstalalo desde Windows.",
                     font=ctk.CTkFont(size=11), text_color=COL_TEXTO_TENUE).pack(anchor="w")

        lista = ctk.CTkScrollableFrame(marco, fg_color=COL_PANEL, corner_radius=12)
        lista.pack(fill="both", expand=True, pady=(10, 0))
        lista.grid_columnconfigure(1, weight=1)

        # se renderiza por paginas (60 filas) con un boton "Cargar mas"
        self._detp_lista = lista
        self._detp_items = datos["items"][:MAX_MOSTRAR]
        self._detp_cursor = 0
        self._detp_boton_mas = None
        self._render_pagina_detalle_programa()

    def _render_pagina_detalle_programa(self):
        PAGINA = 60
        if self._detp_boton_mas is not None:
            self._detp_boton_mas.destroy()
            self._detp_boton_mas = None
        ini = self._detp_cursor
        fin = min(ini + PAGINA, len(self._detp_items))
        self._detp_cursor = fin
        indices = list(range(ini, fin))

        barra = self._barra_carga(self._detp_lista, COL_PANEL, "Cargando archivos...")
        barra.grid(row=len(self._detp_items) + 2, column=0, sticky="w",
                   padx=10, pady=10)

        def construir(i):
            size, ruta = self._detp_items[i]
            self._fila_archivo_simple(self._detp_lista, i, size, ruta)

        def terminado():
            try:
                barra.destroy()
            except Exception:
                pass
            if self._detp_cursor < len(self._detp_items):
                restantes = len(self._detp_items) - self._detp_cursor
                self._detp_boton_mas = ctk.CTkButton(
                    self._detp_lista,
                    text=f"{self.t('Cargar mas')}  ({restantes} {self.t('restantes')})",
                    height=38, corner_radius=8, fg_color=COL_PANEL_2,
                    hover_color=COL_PANEL_HOVER, text_color=COL_TEXTO,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    command=self._render_pagina_detalle_programa)
                self._detp_boton_mas.grid(row=len(self._detp_items) + 1, column=0,
                                          sticky="ew", padx=6, pady=(8, 4))

        self._stream_filas("_detp_tok", self._detp_lista, indices, construir,
                           al_terminar=terminado, barra=barra)

    def _fila_archivo_simple(self, padre, i, size, ruta):
        """Fila de archivo sin checkbox (para el detalle de un programa)."""
        fondo = COL_PANEL if i % 2 == 0 else COL_PANEL_2
        fila = ctk.CTkFrame(padre, fg_color=fondo, corner_radius=6)
        fila.grid(row=i, column=0, sticky="ew", padx=4, pady=1)
        fila.grid_columnconfigure(0, weight=1)

        nombre = os.path.basename(ruta)
        carpeta = os.path.dirname(ruta)
        texto = ctk.CTkFrame(fila, fg_color="transparent")
        texto.grid(row=0, column=0, sticky="ew", padx=(12, 4), pady=4)
        ctk.CTkLabel(texto, text=nombre, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COL_TEXTO, anchor="w").pack(anchor="w")
        cp = carpeta if len(carpeta) < 85 else "..." + carpeta[-82:]
        ctk.CTkLabel(texto, text=cp, font=ctk.CTkFont(family=FUENTE_MONO, size=10),
                     text_color=COL_TEXTO_TENUE, anchor="w").pack(anchor="w")

        ctk.CTkLabel(fila, text=formato_tamano(size),
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#06b6d4", width=90).grid(row=0, column=1, padx=8)
        ctk.CTkButton(fila, text="▶  Abrir", width=76, height=28, corner_radius=6,
                      fg_color=COL_SIDEBAR, hover_color=COL_PANEL_HOVER,
                      command=lambda r=ruta: self._abrir_archivo(r)
                      ).grid(row=0, column=2, padx=(4, 4))
        ctk.CTkButton(fila, text="\U0001F4C2  Ubicacion", width=96, height=28, corner_radius=6,
                      fg_color=COL_SIDEBAR, hover_color=COL_PANEL_HOVER,
                      command=lambda r=ruta: self._abrir_ubicacion(r)
                      ).grid(row=0, column=3, padx=(0, 10))

    def _abrir_carpeta(self, carpeta):
        try:
            if os.path.isdir(carpeta):
                os.startfile(carpeta)
            else:
                messagebox.showwarning(self.t("No encontrada"), self.t("La carpeta ya no existe."))
        except OSError as e:
            messagebox.showerror(self.t("Error"), self.t("No se pudo abrir la carpeta:") + f"\n{e}")

    def _abrir_desinstalar(self):
        try:
            os.startfile("ms-settings:appsfeatures")
        except OSError:
            subprocess.Popen(["control", "appwiz.cpl"])

    # ==========================================================================
    #  MODULO: LIMPIEZA RAPIDA
    # ==========================================================================
    def mostrar_limpieza(self):
        self._limpiar_contenedor()
        self._marcar_vista("limpieza", self.mostrar_limpieza)
        self._vista_actual = "limpieza"

        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=34, pady=26)

        self._cabecera(marco, "modulo // limpieza", "Limpieza rapida",
                       "Elimina archivos temporales y caches que Windows y los navegadores "
                       "vuelven a crear solos.")

        # barra de acciones del modulo
        barra = ctk.CTkFrame(marco, fg_color="transparent")
        barra.pack(fill="x", pady=(16, 8))
        ctk.CTkButton(barra, text="☑  Seleccionar todo", width=160, height=32,
                      corner_radius=8, fg_color=COL_PANEL, hover_color=COL_PANEL_HOVER,
                      text_color=COL_TEXTO,
                      command=self._seleccionar_todo_limpieza).pack(side="left")
        ctk.CTkButton(barra, text="☐  Quitar seleccion", width=160, height=32,
                      corner_radius=8, fg_color=COL_PANEL, hover_color=COL_PANEL_HOVER,
                      text_color=COL_TEXTO_TENUE,
                      command=self._deseleccionar_todo_limpieza).pack(side="left", padx=8)

        lista = ctk.CTkScrollableFrame(marco, fg_color="transparent")
        lista.pack(fill="both", expand=True)

        self._limpieza_items = []
        for info in limpiezas_disponibles():
            fila = self._tarjeta_limpieza(lista, info)
            self._limpieza_items.append(fila)

        pie = ctk.CTkFrame(marco, fg_color="transparent")
        pie.pack(fill="x", pady=(16, 0))
        self._lbl_total_limpieza = ctk.CTkLabel(
            pie, text="Calculando tamanos...", font=ctk.CTkFont(size=13),
            text_color=COL_TEXTO_TENUE)
        self._lbl_total_limpieza.pack(side="left")
        ctk.CTkButton(pie, text="\U0001F9F9  LIMPIAR SELECCIONADOS", height=46, width=250,
                      corner_radius=23, font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color=COL_ROJO, hover_color=COL_ROJO_HOV,
                      command=self._limpiar_seleccion).pack(side="right")

        self._token_limpieza = object()
        threading.Thread(target=self._calcular_limpiezas,
                         args=(self._token_limpieza,), daemon=True).start()

    def _seleccionar_todo_limpieza(self):
        for f in getattr(self, "_limpieza_items", []):
            if f["size"] > 0:
                f["var"].set(True)
        self._actualizar_total_limpieza()

    def _deseleccionar_todo_limpieza(self):
        for f in getattr(self, "_limpieza_items", []):
            f["var"].set(False)
        self._actualizar_total_limpieza()

    def _tarjeta_limpieza(self, padre, info):
        card = ctk.CTkFrame(padre, fg_color=COL_PANEL, corner_radius=12,
                            border_width=1, border_color=COL_BORDE)
        card.pack(fill="x", pady=5)
        card.grid_columnconfigure(1, weight=1)

        var = ctk.BooleanVar(value=False)
        fila = {"info": info, "var": var, "size": 0, "count": 0}

        ctk.CTkCheckBox(card, text="", variable=var, width=24,
                        fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV,
                        checkmark_color=COL_ACENTO_TXT,
                        command=self._actualizar_total_limpieza
                        ).grid(row=0, column=0, rowspan=2, padx=(14, 6), pady=14)

        ctk.CTkLabel(card, text=info["nombre"], font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COL_TEXTO, anchor="w").grid(row=0, column=1, sticky="w", pady=(12, 0))
        ctk.CTkLabel(card, text=info["desc"], font=ctk.CTkFont(size=11),
                     text_color=COL_TEXTO_TENUE, anchor="w").grid(row=1, column=1, sticky="w", pady=(0, 12))

        lbl_size = ctk.CTkLabel(card, text="Calculando...", font=ctk.CTkFont(size=13, weight="bold"),
                                text_color=COL_TEXTO_TENUE, width=170, anchor="e")
        lbl_size.grid(row=0, column=2, rowspan=2, padx=16)
        fila["label"] = lbl_size
        return fila

    def _calcular_limpiezas(self, token):
        for fila in list(self._limpieza_items):
            if token is not self._token_limpieza:
                return
            info = fila["info"]
            if info["tipo"] == "papelera":
                count, size = tamano_papelera()
            else:
                count, size = calcular_tamano_rutas(info["rutas"], info.get("patron"))
            self.after(0, self._actualizar_fila_limpieza, token, fila, count, size)

    def _actualizar_fila_limpieza(self, token, fila, count, size):
        if token is not self._token_limpieza:
            return
        fila["size"] = size
        fila["count"] = count
        try:
            if size == 0:
                fila["label"].configure(text=self.t("Nada que limpiar"), text_color=COL_TEXTO_TENUE)
            else:
                texto = f"{formato_tamano(size)}   ({count:,} {self.t('archivos')})".replace(",", ".")
                fila["label"].configure(text=texto, text_color=COL_VERDE)
        except Exception:
            return
        self._actualizar_total_limpieza()

    def _actualizar_total_limpieza(self):
        if not hasattr(self, "_limpieza_items"):
            return
        total = sum(f["size"] for f in self._limpieza_items if f["var"].get())
        try:
            if total:
                self._lbl_total_limpieza.configure(
                    text=f"{self.t('Se liberarian aprox.')} {formato_tamano(total)}",
                    text_color=COL_ACENTO)
            else:
                self._lbl_total_limpieza.configure(
                    text=self.t("Selecciona elementos para ver cuanto espacio liberarian"),
                    text_color=COL_TEXTO_TENUE)
        except Exception:
            pass

    def _limpiar_seleccion(self):
        seleccion = [f for f in self._limpieza_items if f["var"].get() and f["size"] > 0]
        if not seleccion:
            messagebox.showinfo(self.t("Nada seleccionado"),
                                self.t("Marca algun elemento que tenga datos para limpiar."))
            return
        total = sum(f["size"] for f in seleccion)
        nombres = "\n".join(f"  -  {f['info']['nombre']}" for f in seleccion)
        if not messagebox.askyesno(
                self.t("Confirmar limpieza"),
                self.t("Se eliminaran de forma PERMANENTE (no van a la papelera):") +
                f"\n\n{nombres}\n\n" +
                self.t("Espacio a liberar: aprox. {t}").format(t=formato_tamano(total)) +
                f"\n\n{self.t('¿Continuar?')}"):
            return

        self._lbl_total_limpieza.configure(text=self.t("Limpiando, espera un momento..."),
                                           text_color=COL_TEXTO_TENUE)
        threading.Thread(target=self._trabajo_limpiar, args=(seleccion,), daemon=True).start()

    def _trabajo_limpiar(self, seleccion):
        liberado_total = 0
        fallos_total = 0
        for fila in seleccion:
            info = fila["info"]
            if info["tipo"] == "papelera":
                if vaciar_papelera():
                    liberado_total += fila["size"]
                else:
                    fallos_total += 1
            else:
                _borrados, fallos, liberado = limpiar_rutas(info["rutas"], info.get("patron"))
                liberado_total += liberado
                fallos_total += fallos
        self.after(0, self._limpieza_terminada, liberado_total, fallos_total)

    def _limpieza_terminada(self, liberado, fallos):
        msg = self.t("Espacio liberado: {t}").format(t=formato_tamano(liberado))
        if fallos:
            msg += "\n\n" + self.t(
                "{n} archivo(s) no se pudieron borrar (estaban en uso "
                "o hacen falta permisos de administrador).").format(n=fallos)
        messagebox.showinfo(self.t("Limpieza completada"), msg)
        self.mostrar_limpieza()

    # ==========================================================================
    #  MODULO: CONFIGURACION
    # ==========================================================================
    def mostrar_configuracion(self):
        self._limpiar_contenedor()
        self._marcar_vista("config", self.mostrar_configuracion)

        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=34, pady=26)

        self._cabecera(marco, "modulo // ajustes", "Configuracion",
                       "Preferencias globales de la aplicacion.")

        # ----- tarjeta: idioma -----
        tarjeta_idi = ctk.CTkFrame(marco, fg_color=COL_PANEL, corner_radius=14,
                                    border_width=1, border_color=COL_BORDE)
        tarjeta_idi.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(tarjeta_idi, text="\U0001F310  Idioma / Language",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COL_TEXTO).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(tarjeta_idi, text=IDIOMAS_DISPONIBLES.get(self.idioma, self.idioma),
                     font=ctk.CTkFont(size=12), text_color=COL_TEXTO_TENUE
                     ).pack(anchor="w", padx=20, pady=(0, 10))
        ctk.CTkButton(tarjeta_idi, text=self.t("Cambiar idioma"), width=200, height=38,
                      corner_radius=8, fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV,
                      text_color=COL_ACENTO_TXT, font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda: self._mostrar_selector_idioma(inicial=False)
                      ).pack(anchor="w", padx=20, pady=(0, 20))

        tarjeta = ctk.CTkFrame(marco, fg_color=COL_PANEL, corner_radius=14,
                               border_width=1, border_color=COL_BORDE)
        tarjeta.pack(fill="x", pady=(20, 0))

        ctk.CTkLabel(tarjeta, text="\U0001F4C1  Carpeta de destino para mover archivos",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COL_TEXTO).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            tarjeta,
            text="Elige una carpeta (puede estar en otro disco duro, por ejemplo uno externo)\n"
                 "donde mover los archivos que quieras sacar de en medio antes de borrarlos.",
            font=ctk.CTkFont(size=12), text_color=COL_TEXTO_TENUE,
            justify="left").pack(anchor="w", padx=20, pady=(0, 10))

        ruta_actual = self.config.get("carpeta_basura", "")
        self._lbl_carpeta_basura = ctk.CTkLabel(
            tarjeta,
            text=ruta_actual if ruta_actual else "No configurada todavia",
            font=ctk.CTkFont(family=FUENTE_MONO, size=12),
            text_color=COL_VERDE if ruta_actual else COL_TEXTO_TENUE)
        self._lbl_carpeta_basura.pack(anchor="w", padx=20, pady=(0, 16))

        fila_botones = ctk.CTkFrame(tarjeta, fg_color="transparent")
        fila_botones.pack(anchor="w", padx=20, pady=(0, 20))
        ctk.CTkButton(fila_botones, text="Elegir carpeta...", width=160, height=38,
                      corner_radius=8, fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV,
                      text_color=COL_ACENTO_TXT, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._elegir_carpeta_basura).pack(side="left")
        ctk.CTkButton(fila_botones, text="Quitar", width=100, height=38,
                      corner_radius=8, fg_color="transparent", border_width=1,
                      border_color=COL_ROJO, text_color=COL_ROJO,
                      hover_color=COL_PANEL_HOVER,
                      command=self._quitar_carpeta_basura).pack(side="left", padx=8)

        ctk.CTkLabel(
            marco,
            text="Cuando esta configurada, en el detalle de cada categoria del modulo Discos\n"
                 "podras pulsar \"Mover a carpeta de basura\" para sacar archivos del disco\n"
                 "analizado sin borrarlos todavia (ideal para pasarlos a un disco externo\n"
                 "antes de decidir si los borras).",
            font=ctk.CTkFont(size=12), text_color=COL_TEXTO_TENUE,
            justify="left").pack(anchor="w", pady=(18, 0))

        # ----- tarjeta: actualizaciones -----
        tarjeta_act = ctk.CTkFrame(marco, fg_color=COL_PANEL, corner_radius=14,
                                    border_width=1, border_color=COL_BORDE)
        tarjeta_act.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(tarjeta_act, text="⬡  Actualizaciones",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COL_TEXTO).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            tarjeta_act,
            text=f"{self.t('Version instalada:')} {APP_VERSION}. "
                 f"{self.t('Comprueba en GitHub si hay una version mas reciente.')}",
            font=ctk.CTkFont(size=12), text_color=COL_TEXTO_TENUE,
            justify="left").pack(anchor="w", padx=20, pady=(0, 10))
        fila_act = ctk.CTkFrame(tarjeta_act, fg_color="transparent")
        fila_act.pack(anchor="w", padx=20, pady=(0, 20))
        self._btn_buscar_act = ctk.CTkButton(
            fila_act, text="Buscar actualizaciones", width=200, height=38, corner_radius=8,
            fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV, text_color=COL_ACENTO_TXT,
            font=ctk.CTkFont(size=13, weight="bold"), command=self._buscar_actualizaciones_manual)
        self._btn_buscar_act.pack(side="left")
        self._lbl_estado_act = ctk.CTkLabel(fila_act, text="", font=ctk.CTkFont(size=12),
                                             text_color=COL_TEXTO_TENUE)
        self._lbl_estado_act.pack(side="left", padx=14)

        # ----- tarjeta: tutorial / ayuda -----
        tarjeta2 = ctk.CTkFrame(marco, fg_color=COL_PANEL, corner_radius=14,
                                border_width=1, border_color=COL_BORDE)
        tarjeta2.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(tarjeta2, text="\U0001F393  Tutorial de bienvenida",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COL_TEXTO).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            tarjeta2,
            text="Vuelve a ver la guia rapida de como funciona la aplicacion.",
            font=ctk.CTkFont(size=12), text_color=COL_TEXTO_TENUE,
            justify="left").pack(anchor="w", padx=20, pady=(0, 10))
        ctk.CTkButton(tarjeta2, text="Ver tutorial de nuevo", width=200, height=38,
                      corner_radius=8, fg_color=COL_ACENTO, hover_color=COL_ACENTO_HOV,
                      text_color=COL_ACENTO_TXT, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._mostrar_tutorial).pack(anchor="w", padx=20, pady=(0, 20))

        # ----- pie con la marca -----
        ctk.CTkLabel(
            marco, text=f"{APP_NOMBRE} v{APP_VERSION}   ·   {APP_COPYRIGHT}",
            font=ctk.CTkFont(family=FUENTE_MONO, size=11),
            text_color=COL_TEXTO_TENUE).pack(anchor="w", pady=(22, 0))

    def _elegir_carpeta_basura(self):
        ruta = filedialog.askdirectory(title=self.t("Elige la carpeta destino"))
        if not ruta:
            return
        self.config["carpeta_basura"] = ruta
        guardar_config(self.config)
        self._lbl_carpeta_basura.configure(text=ruta, text_color=COL_VERDE)

    def _quitar_carpeta_basura(self):
        self.config.pop("carpeta_basura", None)
        guardar_config(self.config)
        self._lbl_carpeta_basura.configure(text=self.t("No configurada todavia"),
                                           text_color=COL_TEXTO_TENUE)


if __name__ == "__main__":
    app = CleanMyWin()
    app.mainloop()
