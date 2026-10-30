"""
================================================================================
PROJETO: AutoDoc IT — Gravador Inteligente de Procedimentos e Documentação
DESENVOLVEDOR: Raffael Dutra (© 2026 Todos os direitos reservados)
COMPATIBILIDADE: Multiplataforma (Windows & Linux)
DESCRIÇÃO:
    Aplicação Desktop para captura automática de fluxos operacionais (cliques,
    duplos cliques, atalhos, área de transferência e comandos de terminal CLI),
    com edição visual de imagens (Blur, Setas, Retângulos, Textos), geração
    automatizada de documentação via Google Gemini API (gemini-2.5-flash) e
    exportação para Markdown, HTML Interativo (Zoom In/Out) e PDF.
================================================================================
"""

import os
import sys
import re
import math
import json
import time
import shutil
import atexit
import base64
import hashlib
import ctypes
import threading
import subprocess
import platform
import unicodedata
from datetime import datetime
from typing import List, Tuple, Optional
import tkinter as tk
from tkinter import filedialog, messagebox

# Importa submódulos exclusivos do Windows apenas se estiver rodando no Windows
if platform.system() == "Windows":
    from ctypes import wintypes

import mss
import markdown
import customtkinter as ctk
from xhtml2pdf import pisa
from PIL import Image, ImageDraw, ImageFilter, ImageTk
from pynput import mouse, keyboard
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


# ==============================================================================
# SEÇÃO 1: CONSTANTES GLOBAIS E CONFIGURAÇÃO DE AMBIENTE
# ==============================================================================

# Chave de API opcional em código (Recomenda-se usar o botão "🔑 API" na interface)
GEMINI_API_KEY_DIRETA = ""

# Ajuste de DPI Awareness no Windows para garantir precisão nas coordenadas (X, Y)
if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

# Configuração visual padrão do CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Lista de termos para detecção automática de janelas de Terminal / Console / CLI
TERMOS_TERMINAL = (
    "cmd.exe", "prompt de comando", "command prompt", "powershell", "pwsh",
    "terminal", "putty", "mobaxterm", "securecrt", "teraterm", "kitty",
    "git bash", "mingw", "wsl", "ubuntu", "debian", "kali", "centos",
    "ssh", "telnet", "winbox", "console", "hyper", "alacritty", "wezterm",
    "konsole", "gnome-terminal", "xfce4-terminal", "terminator", "tilix"
)

# Valores padrão para os templates de documentação (personalizáveis na interface)
TEMPLATES_PADRAO_DEFAULT = {
    "autor_padrao": "Raffael Dutra — Equipe de TI / Infraestrutura",
    "org_padrao": "Tecnologia da Informação e Comunicação",
    "incluir_janela_passo": True,
    "incluir_nota_ia": True,
    "instrucao_extra_ia": (
        "Use linguagem técnica clara e direta. Quando o usuário pressionar [Enter] após digitar, "
        "deixe explícito na instrução que deve pressionar a tecla Enter para confirmar ou pesquisar."
    ),
    "rodape_customizado": "© Desenvolvido por Raffael Dutra — Documentação gerada via AutoDoc IT."
}


def obter_diretorio_base() -> str:
    """
    Retorna o diretório físico real onde o executável (.exe / binário ELF) ou script (.py)
    está rodando. Essencial quando compilado com PyInstaller (--onefile).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def limpar_nome_pasta(texto: str, max_len: int = 45) -> str:
    """
    Sanitiza strings para uso seguro como nome de diretório no Windows e Linux,
    removendo acentuação e caracteres proibidos pelo sistema de arquivos.
    """
    sem_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    limpo = re.sub(r'[<>:"/\\|?*\n\r\t]+', "", sem_acentos)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    return limpo[:max_len].strip()


# ==============================================================================
# SEÇÃO 2: SEGURANÇA E CRIPTOGRAFIA DA API KEY (DPAPI + PBKDF2 SHA-256)
# ==============================================================================

if platform.system() == "Windows":
    class DATA_BLOB(ctypes.Structure):
        """Estrutura nativa da API do Windows (crypt32.dll) para manipulação de blocos de dados."""
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char))
        ]


def _gerar_chave_maquina_sha256() -> bytes:
    """
    Deriva uma chave criptográfica de 256 bits exclusiva para a máquina e usuário atuais
    utilizando PBKDF2-HMAC-SHA256 com 100.000 iterações (compatível com Windows e Linux).
    """
    usuario = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    identificador = f"{platform.node()}|{usuario}|AutoDocIT_Salt_2026"
    return hashlib.pbkdf2_hmac("sha256", identificador.encode("utf-8"), b"AutoDoc_Sec", 100000)


def proteger_api_key(chave_plana: str) -> str:
    """
    Criptografa a API Key antes de persistir no arquivo config.json.
    Usa Windows DPAPI no Windows e derivação PBKDF2-HMAC-SHA256 no Linux.
    """
    chave_plana = chave_plana.strip()
    if not chave_plana:
        return ""

    dados_bytes = chave_plana.encode("utf-8")

    # 1. Criptografia Nativa Windows DPAPI (Executada apenas no Windows)
    if platform.system() == "Windows":
        try:
            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32
            blob_in = DATA_BLOB(len(dados_bytes), ctypes.create_string_buffer(dados_bytes, len(dados_bytes)))
            blob_out = DATA_BLOB()

            if crypt32.CryptProtectData(
                ctypes.byref(blob_in), "AutoDocIT_Key", None, None, None, 0, ctypes.byref(blob_out)
            ):
                raw_enc = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                kernel32.LocalFree(blob_out.pbData)
                return "DPAPI:" + base64.b64encode(raw_enc).decode("ascii")
        except Exception:
            pass

    # 2. Criptografia Padrão Linux / Multiplataforma (PBKDF2-HMAC-SHA256)
    chave_sha = _gerar_chave_maquina_sha256()
    cifrado = bytes([b ^ chave_sha[i % len(chave_sha)] for i, b in enumerate(dados_bytes)])
    return "SHA256_ENC:" + base64.b64encode(cifrado).decode("ascii")


def desproteger_api_key(valor_salvo: str) -> str:
    """
    Descriptografa a API Key lida do arquivo config.json em memória durante a execução.
    Se o arquivo config.json for copiado para outro computador, a descriptografia falhará.
    """
    valor_salvo = valor_salvo.strip()
    if not valor_salvo:
        return ""

    if valor_salvo.startswith("DPAPI:") and platform.system() == "Windows":
        try:
            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32
            raw_enc = base64.b64decode(valor_salvo.replace("DPAPI:", "", 1))
            blob_in = DATA_BLOB(len(raw_enc), ctypes.create_string_buffer(raw_enc, len(raw_enc)))
            blob_out = DATA_BLOB()

            if crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
            ):
                texto_plano = ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
                kernel32.LocalFree(blob_out.pbData)
                return texto_plano
        except Exception:
            return ""

    if valor_salvo.startswith("SHA256_ENC:"):
        try:
            cifrado = base64.b64decode(valor_salvo.replace("SHA256_ENC:", "", 1))
            chave_sha = _gerar_chave_maquina_sha256()
            decifrado = bytes([b ^ chave_sha[i % len(chave_sha)] for i, b in enumerate(cifrado)])
            return decifrado.decode("utf-8")
        except Exception:
            return ""

    return valor_salvo


# ==============================================================================
# SEÇÃO 3: INTEGRAÇÃO COM O SISTEMA OPERACIONAL (WINDOWS WIN32 E LINUX X11)
# ==============================================================================

if platform.system() == "Windows":
    class GUITHREADINFO(ctypes.Structure):
        """Estrutura Win32 para inspeção de foco de teclado e posição do Caret (cursor de texto)."""
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT),
        ]


def obter_posicao_atual_mouse(fallback_xy: Optional[Tuple[int, int]] = None) -> Tuple[int, int]:
    """Obtém a coordenada (X, Y) instantânea do ponteiro do mouse na tela (Windows e Linux)."""
    if platform.system() == "Windows":
        try:
            pt = wintypes.POINT()
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                return (int(pt.x), int(pt.y))
        except Exception:
            pass
    try:
        ctrl = mouse.Controller()
        pos = ctrl.position
        return (int(pos[0]), int(pos[1]))
    except Exception:
        return fallback_xy if fallback_xy else (960, 540)


def obter_contexto_janela_ativa() -> Tuple[str, bool]:
    """
    Captura o título da janela que está em primeiro plano (Foreground Window)
    tanto no Windows (user32.dll) quanto no Linux (xdotool) e identifica se é um Terminal/CLI.
    """
    titulo = "Sistema Operacional"
    sistema = platform.system()

    if sistema == "Windows":
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if buf.value.strip():
                        titulo = buf.value.strip()
        except Exception:
            pass

    elif sistema == "Linux":
        try:
            res = subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowname"],
                stderr=subprocess.DEVNULL, timeout=0.3
            ).decode("utf-8", errors="ignore").strip()
            if res:
                titulo = res
        except Exception:
            pass

    titulo_lower = titulo.lower()
    eh_terminal = any(termo in titulo_lower for termo in TERMOS_TERMINAL)
    return titulo, eh_terminal


def ler_texto_clipboard(tk_root=None) -> str:
    """
    Lê o conteúdo de texto da Área de Transferência (Clipboard) no Windows e no Linux.
    """
    if platform.system() == "Windows":
        CF_UNICODETEXT = 13
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL

        kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        try:
            if user32.OpenClipboard(None):
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if handle:
                    ponteiro = kernel32.GlobalLock(handle)
                    if ponteiro:
                        texto = ctypes.wstring_at(ponteiro)
                        kernel32.GlobalUnlock(handle)
                        user32.CloseClipboard()
                        return texto.strip()
                user32.CloseClipboard()
        except Exception:
            pass

    # Fallback nativo para Linux e macOS via Tkinter Clipboard
    if tk_root is not None:
        try:
            return tk_root.clipboard_get().strip()
        except Exception:
            pass
    return ""


def obter_posicao_foco_digitacao(fallback_xy: Optional[Tuple[int, int]]) -> Tuple[int, int]:
    """
    Localiza a coordenada (X, Y) do campo de texto ativo onde o usuário está digitando.
    Suporta Caret/Focus via Win32 no Windows e geometria de janela ativa no Linux.
    """
    sistema = platform.system()

    if sistema == "Windows":
        try:
            user32 = ctypes.windll.user32
            gui_info = GUITHREADINFO()
            gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)

            if user32.GetGUIThreadInfo(0, ctypes.byref(gui_info)):
                if gui_info.hwndCaret:
                    pt = wintypes.POINT(
                        (gui_info.rcCaret.left + gui_info.rcCaret.right) // 2,
                        (gui_info.rcCaret.top + gui_info.rcCaret.bottom) // 2,
                    )
                    if user32.ClientToScreen(gui_info.hwndCaret, ctypes.byref(pt)):
                        if pt.x > 0 or pt.y > 0:
                            return (int(pt.x), int(pt.y))

                if gui_info.hwndFocus:
                    rect = wintypes.RECT()
                    if user32.GetWindowRect(gui_info.hwndFocus, ctypes.byref(rect)):
                        largura = rect.right - rect.left
                        altura = rect.bottom - rect.top
                        if 0 < largura < 1400 and 0 < altura < 600:
                            cx = (rect.left + rect.right) // 2
                            cy = (rect.top + rect.bottom) // 2
                            return (int(cx), int(cy))
        except Exception:
            pass

    elif sistema == "Linux" and fallback_xy is None:
        try:
            # Caso o usuário digite no Linux sem ter clicado antes, tenta centralizar na janela ativa
            saida = subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowgeometry", "--shell"],
                stderr=subprocess.DEVNULL, timeout=0.3
            ).decode("utf-8", errors="ignore")
            geo = {}
            for linha in saida.splitlines():
                if "=" in linha:
                    k, v = linha.split("=", 1)
                    geo[k.strip()] = int(v.strip())
            if "X" in geo and "Y" in geo and "WIDTH" in geo and "HEIGHT" in geo:
                return (geo["X"] + geo["WIDTH"] // 2, geo["Y"] + geo["HEIGHT"] // 2)
        except Exception:
            pass

    if fallback_xy:
        return fallback_xy
    return (960, 540)


# ==============================================================================
# SEÇÃO 4: PROCESSAMENTO DE IMAGEM E ESTÚDIO VISUAL (BLUR, SETAS, CAIXAS)
# ==============================================================================

def aplicar_operacao_desenho(
    img: Image.Image, op: dict, offset_xy: Tuple[int, int] = (0, 0)
) -> Image.Image:
    """
    Renderiza anotações visuais ou censura (Blur/Pixelate, Retângulo, Seta ou Texto)
    sobre um objeto PIL.Image.
    """
    ox, oy = offset_xy
    tipo = op["tipo"]
    img_out = img.copy()

    if tipo == "blur":
        x1, y1, x2, y2 = op["coords"]
        x1, y1, x2, y2 = x1 + ox, y1 + oy, x2 + ox, y2 + oy
        largura, altura = x2 - x1, y2 - y1
        if largura >= 4 and altura >= 4:
            recorte = img_out.crop((x1, y1, x2, y2))
            fator_pixel = max(1, min(largura, altura) // 10)
            pequena = recorte.resize(
                (max(1, largura // fator_pixel), max(1, altura // fator_pixel)),
                resample=Image.Resampling.BILINEAR
            )
            pixelada = pequena.resize(recorte.size, Image.Resampling.NEAREST)
            censurada = pixelada.filter(ImageFilter.GaussianBlur(radius=3))
            img_out.paste(censurada, (x1, y1))
        return img_out

    draw = ImageDraw.Draw(img_out)

    if tipo == "retangulo":
        x1, y1, x2, y2 = op["coords"]
        draw.rectangle(
            (x1 + ox, y1 + oy, x2 + ox, y2 + oy),
            outline=(255, 59, 48), width=4
        )

    elif tipo == "seta":
        x1, y1, x2, y2 = op["coords"]
        x1, y1, x2, y2 = x1 + ox, y1 + oy, x2 + ox, y2 + oy
        draw.line((x1, y1, x2, y2), fill=(255, 59, 48), width=4)
        angulo = math.atan2(y2 - y1, x2 - x1)
        comp_ponta = 16
        abertura = math.pi / 6
        p1_x = x2 - comp_ponta * math.cos(angulo - abertura)
        p1_y = y2 - comp_ponta * math.sin(angulo - abertura)
        p2_x = x2 - comp_ponta * math.cos(angulo + abertura)
        p2_y = y2 - comp_ponta * math.sin(angulo + abertura)
        draw.polygon([(x2, y2), (p1_x, p1_y), (p2_x, p2_y)], fill=(255, 59, 48))

    elif tipo == "texto":
        x, y = op["coords"]
        x, y = x + ox, y + oy
        texto = op.get("texto", "")
        if texto:
            largura_caixa = max(60, len(texto) * 8 + 18)
            draw.rounded_rectangle(
                (x, y - 14, x + largura_caixa, y + 14),
                radius=5, fill=(15, 23, 42), outline=(255, 59, 48), width=2
            )
            draw.text((x + 9, y - 6), texto, fill=(255, 255, 255))

    return img_out


# ==============================================================================
# SEÇÃO 5: MODELOS DE DADOS PYDANTIC (SAÍDA ESTRUTURADA DA GEMINI API)
# ==============================================================================

class PassoDocumentado(BaseModel):
    """Representa a estrutura individual de um passo analisado pelo Gemini."""
    numero_passo: int = Field(description="Número sequencial exato do passo enviado no prompt (1, 2, 3...).")
    titulo: str = Field(description="Título curto e direto da ação.")
    descricao: str = Field(description="Instrução técnica clara explicando o que fazer ou verificar neste passo.")
    comando_cli: str = Field(
        default="",
        description="Se a ação foi digitar ou colar um comando em um Terminal/CLI/Console, coloque o comando exato aqui. Caso contrário, deixe vazio ''."
    )
    observacao: str = Field(description="Dica técnica ou observação importante sobre a tela.")


class DocumentoProcedimento(BaseModel):
    """Esquema completo exigido da Gemini API via Structured Outputs."""
    titulo_geral: str = Field(description="Título sugerido para o procedimento completo.")
    resumo_objetivo: str = Field(description="Breve descrição do objetivo deste procedimento.")
    pre_requisitos: List[str] = Field(description="Lista de pré-requisitos ou acessos necessários identificados.")
    passos: List[PassoDocumentado]
    validacao_pos: List[str] = Field(description="Checklist para validar se o procedimento funcionou com sucesso.")
    procedimento_rollback: str = Field(description="Instruções de como reverter/desfazer a alteração em caso de falha.")


# ==============================================================================
# SEÇÃO 6: JANELAS MODAIS SECUNDÁRIAS (ESTÚDIO DE IMAGEM, TEMPLATES, BIBLIOTECA)
# ==============================================================================

class EditorImagemModal(ctk.CTkToplevel):
    """Janela modal interativa para aplicar Blur, Retângulos, Setas e Textos nos prints."""

    def __init__(self, parent, item_passo: dict, pasta_sessao: str, callback_atualizar):
        super().__init__(parent)
        self.title("🎨 Estúdio de Anotação e Censura (Blur, Retângulo, Seta e Texto)")
        self.item = item_passo
        self.pasta_sessao = pasta_sessao
        self.callback_atualizar = callback_atualizar

        self.img_zoom_original = item_passo["pil_img"].copy()
        self.img_zoom_trabalho = item_passo["pil_img"].copy()
        self.historico_operacoes = []

        largura_img, altura_img = self.img_zoom_trabalho.size
        self.geometry(f"{max(660, largura_img + 80)}x{altura_img + 165}")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        frame_tools = ctk.CTkFrame(self, fg_color="transparent")
        frame_tools.pack(fill="x", padx=20, pady=(12, 4))

        ctk.CTkLabel(
            frame_tools, text="Ferramenta:", font=("Segoe UI", 13, "bold")
        ).pack(side="left", padx=(5, 8))

        self.seletor_ferramenta = ctk.CTkSegmentedButton(
            frame_tools,
            values=["💧 Borrar (Blur)", "🟥 Retângulo", "↗️ Seta", "🔤 Texto"],
            font=("Segoe UI", 12, "bold")
        )
        self.seletor_ferramenta.set("💧 Borrar (Blur)")
        self.seletor_ferramenta.pack(side="left", fill="x", expand=True, padx=5)

        lbl_dica = ctk.CTkLabel(
            self,
            text="Clique e arraste na imagem (ou clique para inserir texto). As marcações são replicadas no Zoom e na Tela Cheia.",
            font=("Segoe UI", 12), text_color="#adb5bd"
        )
        lbl_dica.pack(pady=(0, 6))

        self.canvas = tk.Canvas(
            self, width=largura_img, height=altura_img,
            cursor="crosshair", highlightthickness=2, highlightbackground="#0dcaf0"
        )
        self.canvas.pack(padx=20, pady=4)

        self.tk_img = ImageTk.PhotoImage(self.img_zoom_trabalho)
        self.img_canvas_id = self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        self.inicio_x = None
        self.inicio_y = None
        self.preview_id = None

        self.canvas.bind("<ButtonPress-1>", self._ao_pressionar_mouse)
        self.canvas.bind("<B1-Motion>", self._ao_arrastar_mouse)
        self.canvas.bind("<ButtonRelease-1>", self._ao_soltar_mouse)

        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=25, pady=12)

        ctk.CTkButton(
            frame_botoes, text="↩ Desfazer Último", width=140, fg_color="#6c757d",
            hover_color="#5c636a", command=self.desfazer_ultimo
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_botoes, text="Cancelar", width=110, fg_color="#dc3545",
            hover_color="#bb2d3b", command=self.destroy
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            frame_botoes, text="✅ Salvar Alterações", width=165, fg_color="#198754",
            hover_color="#157347", font=("Segoe UI", 13, "bold"), command=self.salvar_alteracoes
        ).pack(side="right", padx=5)

    def _obter_tipo_ferramenta_atual(self) -> str:
        val = self.seletor_ferramenta.get()
        if "Retângulo" in val:
            return "retangulo"
        if "Seta" in val:
            return "seta"
        if "Texto" in val:
            return "texto"
        return "blur"

    def _ao_pressionar_mouse(self, event):
        tipo = self._obter_tipo_ferramenta_atual()
        self.inicio_x = event.x
        self.inicio_y = event.y

        if self.preview_id:
            self.canvas.delete(self.preview_id)
            self.preview_id = None

        if tipo == "texto":
            dialogo = ctk.CTkInputDialog(
                text="Digite o texto de destaque para inserir neste ponto da imagem:",
                title="Inserir Anotação de Texto"
            )
            texto_usuario = dialogo.get_input()
            if texto_usuario and texto_usuario.strip():
                op = {"tipo": "texto", "coords": (event.x, event.y), "texto": texto_usuario.strip()}
                self.historico_operacoes.append(op)
                self.img_zoom_trabalho = aplicar_operacao_desenho(self.img_zoom_trabalho, op)
                self._atualizar_canvas()
            return

        if tipo in ("blur", "retangulo"):
            traco = (4, 2) if tipo == "blur" else ()
            self.preview_id = self.canvas.create_rectangle(
                self.inicio_x, self.inicio_y, event.x, event.y,
                outline="#ff3b30", width=3, dash=traco
            )
        elif tipo == "seta":
            self.preview_id = self.canvas.create_line(
                self.inicio_x, self.inicio_y, event.x, event.y,
                fill="#ff3b30", width=4, arrow=tk.LAST
            )

    def _ao_arrastar_mouse(self, event):
        if self.preview_id:
            self.canvas.coords(self.preview_id, self.inicio_x, self.inicio_y, event.x, event.y)

    def _ao_soltar_mouse(self, event):
        tipo = self._obter_tipo_ferramenta_atual()
        if tipo == "texto":
            return

        if self.preview_id:
            self.canvas.delete(self.preview_id)
            self.preview_id = None

        largura_max, altura_max = self.img_zoom_trabalho.size

        if tipo == "seta":
            dist = math.hypot(event.x - self.inicio_x, event.y - self.inicio_y)
            if dist >= 10:
                op = {"tipo": "seta", "coords": (self.inicio_x, self.inicio_y, event.x, event.y)}
                self.historico_operacoes.append(op)
                self.img_zoom_trabalho = aplicar_operacao_desenho(self.img_zoom_trabalho, op)
                self._atualizar_canvas()
        else:
            x1 = max(0, min(self.inicio_x, event.x))
            y1 = max(0, min(self.inicio_y, event.y))
            x2 = min(largura_max, max(self.inicio_x, event.x))
            y2 = min(altura_max, max(self.inicio_y, event.y))
            if (x2 - x1) >= 5 and (y2 - y1) >= 5:
                op = {"tipo": tipo, "coords": (x1, y1, x2, y2)}
                self.historico_operacoes.append(op)
                self.img_zoom_trabalho = aplicar_operacao_desenho(self.img_zoom_trabalho, op)
                self._atualizar_canvas()

    def desfazer_ultimo(self):
        if not self.historico_operacoes:
            return
        self.historico_operacoes.pop()
        self.img_zoom_trabalho = self.img_zoom_original.copy()
        for op in self.historico_operacoes:
            self.img_zoom_trabalho = aplicar_operacao_desenho(self.img_zoom_trabalho, op)
        self._atualizar_canvas()

    def _atualizar_canvas(self):
        self.tk_img = ImageTk.PhotoImage(self.img_zoom_trabalho)
        self.canvas.itemconfig(self.img_canvas_id, image=self.tk_img)

    def salvar_alteracoes(self):
        if not self.historico_operacoes:
            self.destroy()
            return

        caminho_abs_zoom = os.path.join(self.pasta_sessao, self.item["imagem"])
        self.img_zoom_trabalho.save(caminho_abs_zoom, "PNG")
        self.item["pil_img"] = self.img_zoom_trabalho

        base_sem_ext, ext = os.path.splitext(caminho_abs_zoom)
        caminho_abs_full = f"{base_sem_ext}_full{ext}"

        if os.path.exists(caminho_abs_full):
            try:
                img_full = Image.open(caminho_abs_full).convert("RGB")
                offset_xy = self.item.get("crop_offset", (0, 0))
                for op in self.historico_operacoes:
                    img_full = aplicar_operacao_desenho(img_full, op, offset_xy=offset_xy)
                img_full.save(caminho_abs_full, "PNG")
            except Exception:
                pass

        self.callback_atualizar()
        self.destroy()


class ConfigTemplateModal(ctk.CTkToplevel):
    """Janela modal para customização de metadados do template (Autor, Setor, Rodapé e Prompt IA)."""

    def __init__(self, parent, config_atual: dict, callback_salvar):
        super().__init__(parent)
        self.title("⚙️ Personalizar Estrutura do Template e Instruções do Gemini")
        self.geometry("680x560")
        self.resizable(False, False)
        self.config_atual = config_atual.copy()
        self.callback_salvar = callback_salvar

        self.transient(parent)
        self.grab_set()

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            frame, text="Personalização do Documento e IA", font=("Segoe UI", 16, "bold")
        ).pack(anchor="w", padx=15, pady=(12, 10))

        ctk.CTkLabel(
            frame, text="Autor / Equipe Responsável (Exibido no Cabeçalho):", font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=15)
        self.entry_autor = ctk.CTkEntry(frame, width=600, font=("Segoe UI", 13))
        self.entry_autor.pack(padx=15, pady=(2, 10))
        self.entry_autor.insert(0, self.config_atual.get("autor_padrao", ""))

        ctk.CTkLabel(
            frame, text="Organização / Setor / Esquadrão:", font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=15)
        self.entry_org = ctk.CTkEntry(frame, width=600, font=("Segoe UI", 13))
        self.entry_org.pack(padx=15, pady=(2, 10))
        self.entry_org.insert(0, self.config_atual.get("org_padrao", ""))

        frame_checks = ctk.CTkFrame(frame, fg_color="transparent")
        frame_checks.pack(fill="x", padx=15, pady=6)

        self.chk_janela = ctk.CTkCheckBox(
            frame_checks, text="Mostrar linha 'Janela / Aplicação' em cada passo", font=("Segoe UI", 12)
        )
        if self.config_atual.get("incluir_janela_passo", True):
            self.chk_janela.select()
        self.chk_janela.pack(side="left", padx=(0, 20))

        self.chk_nota = ctk.CTkCheckBox(
            frame_checks, text="Mostrar bloco '> Nota Técnica' gerado pela IA", font=("Segoe UI", 12)
        )
        if self.config_atual.get("incluir_nota_ia", True):
            self.chk_nota.select()
        self.chk_nota.pack(side="left")

        ctk.CTkLabel(
            frame,
            text="Instruções Extras para o Gemini (Regras de escrita, vocabulário ou detalhes específicos):",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 2))

        self.txt_instrucao_ia = ctk.CTkTextbox(frame, height=110, width=600, font=("Segoe UI", 12))
        self.txt_instrucao_ia.pack(padx=15, pady=(2, 10))
        self.txt_instrucao_ia.insert("0.0", self.config_atual.get("instrucao_extra_ia", ""))

        ctk.CTkLabel(
            frame, text="Texto de Rodapé do Documento:", font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=15)
        self.entry_rodape = ctk.CTkEntry(frame, width=600, font=("Segoe UI", 13))
        self.entry_rodape.pack(padx=15, pady=(2, 15))
        self.entry_rodape.insert(0, self.config_atual.get("rodape_customizado", ""))

        frame_btn = ctk.CTkFrame(frame, fg_color="transparent")
        frame_btn.pack(fill="x", padx=15, pady=10)

        ctk.CTkButton(
            frame_btn, text="Restaurar Padrão", width=130, fg_color="#6c757d",
            command=self._restaurar_padrao
        ).pack(side="left")

        ctk.CTkButton(
            frame_btn, text="Cancelar", width=100, fg_color="#dc3545", command=self.destroy
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            frame_btn, text="💾 Salvar Preferências", width=165, fg_color="#198754",
            font=("Segoe UI", 13, "bold"), command=self._salvar
        ).pack(side="right", padx=5)

    def _restaurar_padrao(self):
        self.entry_autor.delete(0, "end")
        self.entry_autor.insert(0, TEMPLATES_PADRAO_DEFAULT["autor_padrao"])
        self.entry_org.delete(0, "end")
        self.entry_org.insert(0, TEMPLATES_PADRAO_DEFAULT["org_padrao"])
        self.chk_janela.select()
        self.chk_nota.select()
        self.txt_instrucao_ia.delete("0.0", "end")
        self.txt_instrucao_ia.insert("0.0", TEMPLATES_PADRAO_DEFAULT["instrucao_extra_ia"])
        self.entry_rodape.delete(0, "end")
        self.entry_rodape.insert(0, TEMPLATES_PADRAO_DEFAULT["rodape_customizado"])

    def _salvar(self):
        nova_cfg = {
            "autor_padrao": self.entry_autor.get().strip(),
            "org_padrao": self.entry_org.get().strip(),
            "incluir_janela_passo": bool(self.chk_janela.get()),
            "incluir_nota_ia": bool(self.chk_nota.get()),
            "instrucao_extra_ia": self.txt_instrucao_ia.get("0.0", "end").strip(),
            "rodape_customizado": self.entry_rodape.get().strip()
        }
        self.callback_salvar(nova_cfg)
        self.destroy()


class BibliotecaModal(ctk.CTkToplevel):
    """Gerenciador e buscador local para reabrir procedimentos salvos na árvore 'Procedimentos/'."""

    def __init__(self, parent, diretorio_base: str, callback_carregar_sessao):
        super().__init__(parent)
        self.title("📚 Biblioteca de Procedimentos (Organização Hierárquica)")
        self.geometry("950x600")
        self.minsize(820, 480)
        self.diretorio_base = diretorio_base
        self.pasta_procedimentos_raiz = os.path.join(diretorio_base, "Procedimentos")
        self.callback_carregar_sessao = callback_carregar_sessao

        self.transient(parent)
        self.grab_set()

        frame_busca = ctk.CTkFrame(self, fg_color="transparent")
        frame_busca.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            frame_busca, text="🔍 Buscar Procedimento:", font=("Segoe UI", 14, "bold")
        ).pack(side="left", padx=(0, 10))

        self.entry_busca = ctk.CTkEntry(
            frame_busca,
            placeholder_text="Pesquise por título, data (ex: 28-10-2026), comando ou palavra-chave...",
            font=("Segoe UI", 13), width=460
        )
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=5)
        self.entry_busca.bind("<KeyRelease>", lambda e: self.listar_procedimentos())

        ctk.CTkButton(
            frame_busca, text="📂 Abrir Pasta Raiz", width=130, fg_color="#6c757d",
            command=lambda: self._abrir_arquivo_sistema(self.pasta_procedimentos_raiz)
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            frame_busca, text="🔄 Atualizar", width=95, fg_color="#495057",
            command=self.listar_procedimentos
        ).pack(side="right", padx=5)

        self.scroll_lista = ctk.CTkScrollableFrame(
            self, label_text="Procedimentos / Sessão Data XX-XX-XXXX / Procedimento X"
        )
        self.scroll_lista.pack(fill="both", expand=True, padx=20, pady=(5, 15))
        self.scroll_lista.grid_columnconfigure(0, weight=1)

        self.listar_procedimentos()

    def _coletar_todas_pastas_procedimentos(self) -> List[str]:
        encontradas = []

        if os.path.exists(self.pasta_procedimentos_raiz):
            try:
                for pasta_dia in os.listdir(self.pasta_procedimentos_raiz):
                    caminho_dia = os.path.join(self.pasta_procedimentos_raiz, pasta_dia)
                    if os.path.isdir(caminho_dia):
                        for proc_item in os.listdir(caminho_dia):
                            caminho_proc = os.path.join(caminho_dia, proc_item)
                            if os.path.isdir(caminho_proc):
                                encontradas.append(caminho_proc)
            except Exception:
                pass

        try:
            for item in os.listdir(self.diretorio_base):
                caminho = os.path.join(self.diretorio_base, item)
                if os.path.isdir(caminho) and item.startswith("sessao_"):
                    encontradas.append(caminho)
        except Exception:
            pass

        encontradas.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
        return encontradas

    def _ler_dados_sessao(self, caminho_pasta: str) -> dict:
        nome_pasta = os.path.basename(caminho_pasta)
        pasta_pai_dia = os.path.basename(os.path.dirname(caminho_pasta))
        meta_path = os.path.join(caminho_pasta, "sessao_meta.json")
        md_path = os.path.join(caminho_pasta, "procedimento.md")

        dados = {
            "pasta": caminho_pasta,
            "nome_pasta": nome_pasta,
            "pasta_dia": pasta_pai_dia if pasta_pai_dia.startswith("Sessão Data") else "Raiz",
            "titulo": nome_pasta,
            "resumo": "Sem descrição gerada pela IA ainda.",
            "data": datetime.fromtimestamp(os.path.getmtime(caminho_pasta)).strftime("%d/%m/%Y %H:%M"),
            "template": "Padrão",
            "qtd_passos": 0,
            "conteudo_md": ""
        }

        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    if meta.get("titulo_geral"):
                        dados["titulo"] = f"{nome_pasta.split(' - ')[0]} — {meta['titulo_geral']}"
                    dados["resumo"] = meta.get("resumo_objetivo") or dados["resumo"]
                    dados["data"] = meta.get("data_formatada") or dados["data"]
                    dados["template"] = meta.get("template") or "Padrão"
                    dados["qtd_passos"] = len(meta.get("passos", []))
            except Exception:
                pass

        if os.path.exists(md_path):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    dados["conteudo_md"] = f.read()
            except Exception:
                pass

        if dados["qtd_passos"] == 0:
            pasta_img = os.path.join(caminho_pasta, "imagens")
            if os.path.exists(pasta_img):
                imgs = [
                    arq for arq in os.listdir(pasta_img)
                    if arq.endswith(".png") and not arq.endswith("_full.png")
                ]
                dados["qtd_passos"] = len(imgs)

        return dados

    def listar_procedimentos(self):
        for w in self.scroll_lista.winfo_children():
            w.destroy()

        termo = self.entry_busca.get().strip().lower()
        pastas = self._coletar_todas_pastas_procedimentos()

        linha_atual = 0
        for caminho_pasta in pastas:
            info = self._ler_dados_sessao(caminho_pasta)
            if info["qtd_passos"] == 0 and not info["conteudo_md"]:
                continue

            texto_pesquisavel = (
                f"{info['titulo']} {info['pasta_dia']} {info['nome_pasta']} "
                f"{info['resumo']} {info['conteudo_md']} {info['template']}"
            ).lower()
            if termo and (termo not in texto_pesquisavel):
                continue

            card = ctk.CTkFrame(self.scroll_lista, corner_radius=8, fg_color="#2b2b2b")
            card.grid(row=linha_atual, column=0, sticky="ew", padx=6, pady=6)
            card.grid_columnconfigure(0, weight=1)

            frame_info = ctk.CTkFrame(card, fg_color="transparent")
            frame_info.grid(row=0, column=0, sticky="nsew", padx=14, pady=10)

            lbl_tit = ctk.CTkLabel(
                frame_info, text=f"📄 {info['titulo']}",
                font=("Segoe UI", 15, "bold"), anchor="w", text_color="#ffffff"
            )
            lbl_tit.pack(fill="x")

            subtitulo = (
                f"📁 {info['pasta_dia']}   |   🕒 {info['data']}   |   "
                f"🗂 {info['template']}   |   📸 {info['qtd_passos']} passo(s)"
            )
            ctk.CTkLabel(
                frame_info, text=subtitulo, font=("Segoe UI", 12, "bold"),
                text_color="#0dcaf0", anchor="w"
            ).pack(fill="x", pady=(2, 2))

            resumo_curto = info["resumo"][:130] + ("..." if len(info["resumo"]) > 130 else "")
            ctk.CTkLabel(
                frame_info, text=resumo_curto, font=("Segoe UI", 12),
                text_color="#adb5bd", anchor="w"
            ).pack(fill="x")

            frame_acoes = ctk.CTkFrame(card, fg_color="transparent")
            frame_acoes.grid(row=0, column=1, padx=12, pady=10)

            ctk.CTkButton(
                frame_acoes, text="✏️ Carregar no Editor", width=145, fg_color="#0d6efd",
                hover_color="#0b5ed7", font=("Segoe UI", 12, "bold"),
                command=lambda p=caminho_pasta: self._acionar_carregar(p)
            ).pack(side="left", padx=4)

            arquivos_html = [a for a in os.listdir(caminho_pasta) if a.endswith(".html")]
            if arquivos_html:
                caminho_html = os.path.join(caminho_pasta, arquivos_html[0])
                ctk.CTkButton(
                    frame_acoes, text="🌐 HTML", width=85, fg_color="#0dcaf0",
                    text_color="#000000", hover_color="#31d2f2",
                    command=lambda h=caminho_html: self._abrir_arquivo_sistema(h)
                ).pack(side="left", padx=4)

            arquivos_pdf = [a for a in os.listdir(caminho_pasta) if a.endswith(".pdf")]
            if arquivos_pdf:
                caminho_pdf = os.path.join(caminho_pasta, arquivos_pdf[0])
                ctk.CTkButton(
                    frame_acoes, text="📄 PDF", width=80, fg_color="#dc3545",
                    hover_color="#bb2d3b",
                    command=lambda pdf=caminho_pdf: self._abrir_arquivo_sistema(pdf)
                ).pack(side="left", padx=4)

            ctk.CTkButton(
                frame_acoes, text="📂 Pasta", width=80, fg_color="#6c757d",
                hover_color="#5c636a",
                command=lambda p=caminho_pasta: self._abrir_arquivo_sistema(p)
            ).pack(side="left", padx=4)

            linha_atual += 1

        if linha_atual == 0:
            ctk.CTkLabel(
                self.scroll_lista,
                text="Nenhum procedimento encontrado na pasta Procedimentos.",
                font=("Segoe UI", 13, "italic"), text_color="#adb5bd"
            ).grid(row=0, column=0, pady=30)

    def _acionar_carregar(self, caminho_pasta: str):
        self.callback_carregar_sessao(caminho_pasta)
        self.destroy()

    def _abrir_arquivo_sistema(self, caminho: str):
        if not os.path.splitext(caminho)[1]:
            os.makedirs(caminho, exist_ok=True)
        sistema = platform.system()
        if sistema == "Windows":
            os.startfile(caminho)
        elif sistema == "Darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])

class ProgressoGeracaoModal(ctk.CTkToplevel):
    """Janela modal que exibe o progresso em tempo real, cronômetro e logs da geração via Gemini."""

    def __init__(self, parent, total_passos: int, nome_template: str):
        super().__init__(parent)
        self.title("⏳ Gerando Documentação com Gemini 2.5 Flash")
        self.geometry("640x430")
        self.resizable(False, False)

        self.total_passos = total_passos
        self.cancelado = False
        self.finalizado = False
        self.inicio_ts = time.time()

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._ao_clicar_fechar)

        # Container Principal
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Cabeçalho + Cronômetro
        frame_topo = ctk.CTkFrame(frame, fg_color="transparent")
        frame_topo.pack(fill="x", padx=15, pady=(12, 4))

        self.lbl_etapa = ctk.CTkLabel(
            frame_topo,
            text="🚀 Inicializando preparação dos dados...",
            font=("Segoe UI", 15, "bold"),
            text_color="#ffffff",
            anchor="w"
        )
        self.lbl_etapa.pack(side="left", fill="x", expand=True)

        self.lbl_tempo = ctk.CTkLabel(
            frame_topo,
            text="⏱️ 00:00s",
            font=("Consolas", 13, "bold"),
            text_color="#0dcaf0"
        )
        self.lbl_tempo.pack(side="right")

        # Subtítulo com detalhes em tempo real (Streaming)
        self.lbl_detalhe = ctk.CTkLabel(
            frame,
            text=f"Template: {nome_template} | Total de passos: {total_passos}",
            font=("Segoe UI", 12),
            text_color="#adb5bd",
            anchor="w"
        )
        self.lbl_detalhe.pack(fill="x", padx=15, pady=(0, 10))

        # Barra de Progresso + Percentual
        frame_barra = ctk.CTkFrame(frame, fg_color="transparent")
        frame_barra.pack(fill="x", padx=15, pady=(0, 12))

        self.barra_progresso = ctk.CTkProgressBar(frame_barra, height=16, corner_radius=8)
        self.barra_progresso.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.barra_progresso.set(0.0)

        self.lbl_percentual = ctk.CTkLabel(
            frame_barra,
            text="0%",
            font=("Segoe UI", 13, "bold"),
            width=45,
            text_color="#0dcaf0"
        )
        self.lbl_percentual.pack(side="right")

        # Caixa de Log em Tempo Real
        ctk.CTkLabel(
            frame,
            text="Log de Execução em Tempo Real:",
            font=("Segoe UI", 12, "bold"),
            anchor="w"
        ).pack(fill="x", padx=15, pady=(2, 4))

        self.txt_log = ctk.CTkTextbox(
            frame,
            height=185,
            font=("Consolas", 12),
            fg_color="#18181b",
            text_color="#e4e4e7"
        )
        self.txt_log.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        self.txt_log.configure(state="disabled")

        # Botão Inferior (Cancelar / Fechar)
        frame_botoes = ctk.CTkFrame(frame, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=15, pady=(0, 8))

        self.btn_acao = ctk.CTkButton(
            frame_botoes,
            text="✖ Cancelar Operação",
            fg_color="#dc3545",
            hover_color="#bb2d3b",
            font=("Segoe UI", 12, "bold"),
            width=170,
            command=self._ao_clicar_fechar
        )
        self.btn_acao.pack(side="right")

        self.adicionar_log(f"Iniciando processamento de {total_passos} passo(s)...")
        self.adicionar_log(f"Template selecionado: {nome_template}")
        self._atualizar_cronometro()

    def _atualizar_cronometro(self):
        if not self.finalizado and self.winfo_exists():
            decorrido = int(time.time() - self.inicio_ts)
            mins, segs = divmod(decorrido, 60)
            self.lbl_tempo.configure(text=f"⏱️ {mins:02d}:{segs:02d}s")
            self.after(250, self._atualizar_cronometro)

    def adicionar_log(self, mensagem: str):
        if not self.winfo_exists():
            return
        hora_str = datetime.now().strftime("%H:%M:%S")
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"[{hora_str}] {mensagem}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def atualizar_progresso(self, valor: float, etapa: Optional[str] = None, detalhe: Optional[str] = None):
        if not self.winfo_exists():
            return
        valor_limpo = max(0.0, min(1.0, valor))
        self.barra_progresso.set(valor_limpo)
        self.lbl_percentual.configure(text=f"{int(valor_limpo * 100)}%")

        if etapa:
            self.lbl_etapa.configure(text=etapa)
        if detalhe:
            self.lbl_detalhe.configure(text=detalhe)

    def marcar_sucesso(self, msg_final: str):
        if not self.winfo_exists():
            return
        self.finalizado = True
        self.atualizar_progresso(
            1.0,
            etapa="✅ Documentação gerada com sucesso!",
            detalhe=msg_final
        )
        self.barra_progresso.configure(progress_color="#198754")
        self.lbl_percentual.configure(text_color="#20c997")
        self.adicionar_log("🎉 Processamento concluído! O documento já está disponível no editor.")
        self.btn_acao.configure(
            text="✅ Fechar Janela",
            fg_color="#198754",
            hover_color="#157347"
        )
        # Fecha automaticamente após 1.5s para agilizar o fluxo
        self.after(1500, lambda: self.destroy() if self.winfo_exists() else None)

    def marcar_erro(self, erro_str: str):
        if not self.winfo_exists():
            return
        self.finalizado = True
        self.lbl_etapa.configure(text="❌ Falha ao gerar o relatório", text_color="#ff6b6b")
        self.lbl_detalhe.configure(text="Verifique os detalhes do erro no log abaixo.")
        self.barra_progresso.configure(progress_color="#dc3545")
        self.lbl_percentual.configure(text_color="#ff6b6b")
        self.adicionar_log("--------------------------------------------------")
        self.adicionar_log(f"ERRO REPORTADO: {erro_str}")
        self.adicionar_log("Dica: Verifique sua conexão com a internet e sua Gemini API Key.")
        self.btn_acao.configure(
            text="Fechar",
            fg_color="#6c757d",
            hover_color="#5c636a"
        )

    def _ao_clicar_fechar(self):
        if not self.finalizado:
            self.cancelado = True
            self.adicionar_log("⚠️ Cancelamento solicitado pelo usuário. Interrompendo...")
        self.destroy()

# ==============================================================================
# SEÇÃO 7: APLICAÇÃO PRINCIPAL (INTERFACE, LISTENERS, IA E LIMPEZA DE PASTAS)
# ==============================================================================

class AutoDocApp(ctk.CTk):
    """Classe principal do aplicativo AutoDoc IT."""

    def __init__(self):
        super().__init__()
        self.title("AutoDoc IT - Gravador Inteligente de Procedimentos | © Raffael Dutra")
        self.geometry("1540x780")
        self.minsize(1220, 660)

        # Caminhos Base e Configuração Criptografada
        self.diretorio_base = obter_diretorio_base()
        self.caminho_config = os.path.join(self.diretorio_base, "config.json")
        self.config_template = TEMPLATES_PADRAO_DEFAULT.copy()
        self.api_key_atual = self._carregar_config_local()

        # Estado da Gravação e Controle de Concorrência (Thread Lock)
        self.gravando = False
        self.modo_senha = False
        self.tamanho_zoom = 550
        self.contador_arquivos = 0
        self.passos = []
        self.buffer_texto = []
        self.ultimo_clique_xy = None
        self.ultimo_clique_ts = 0.0
        self.ultimo_clique_botao = None
        self.foco_digitacao_xy = None
        self.janela_digitacao_atual = ("Sistema Operacional", False)
        self.modificadores_ativos = set()
        self.ultimo_atalho_ts = 0.0
        self.lock = threading.Lock()
        self.rect_janela = (0, 0, 0, 0)

        # 1. Antes de criar a sessão atual, remove eventuais pastas vazias de execuções anteriores
        self._varrer_e_limpar_sessoes_orfas()

        # 2. Cria a estrutura hierárquica da sessão atual
        self.numero_proc_atual = 1
        self.timestamp_proc_atual = ""
        self.pasta_sessao, self.pasta_imagens = self._criar_diretorio_procedimento_organizado()

        # 3. Registra hooks de fechamento seguro para apagar a sessão atual se sair sem gravar nada
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar_aplicacao)
        atexit.register(self._limpar_sessao_atual_no_encerramento)

        self._construir_interface()
        self._iniciar_listeners_globais()
        self._atualizar_geometria_loop()

    # --------------------------------------------------------------------------
    # SUBSEÇÃO 7.1: GERENCIAMENTO HIERÁRQUICO DE PASTAS E LIMPEZA AUTOMÁTICA
    # --------------------------------------------------------------------------

    def _diretorio_procedimento_esta_vazio(self, caminho_proc: str) -> bool:
        """
        Verifica se uma pasta de procedimento é considerada 'vazia' (sem dados úteis).
        Retorna True se não houver nenhuma captura de tela (.png) nem documento salvo (.md/.html/.pdf).
        """
        if not caminho_proc or not os.path.exists(caminho_proc):
            return False

        for arq in ("procedimento.md", "procedimento_interativo.html", "procedimento.pdf"):
            if os.path.exists(os.path.join(caminho_proc, arq)):
                return False

        try:
            for item in os.listdir(caminho_proc):
                if item.endswith((".md", ".html", ".pdf")):
                    return False
        except Exception:
            pass

        pasta_img = os.path.join(caminho_proc, "imagens")
        if os.path.exists(pasta_img):
            try:
                imagens = [f for f in os.listdir(pasta_img) if f.endswith(".png")]
                if len(imagens) > 0:
                    return False
            except Exception:
                pass

        return True

    def _limpar_diretorio_se_vazio(self, caminho_proc: str):
        """
        Remove o diretório do procedimento caso esteja vazio.
        Se a pasta pai ('Sessão Data DD-MM-AAAA') também ficar vazia após a remoção,
        remove a pasta do dia em cascata para manter o diretório 'Procedimentos/' limpo.
        """
        if not caminho_proc or not os.path.exists(caminho_proc):
            return

        if self._diretorio_procedimento_esta_vazio(caminho_proc):
            pasta_pai_dia = os.path.dirname(caminho_proc)
            try:
                shutil.rmtree(caminho_proc, ignore_errors=True)
            except Exception:
                pass

            if os.path.exists(pasta_pai_dia) and os.path.basename(pasta_pai_dia).startswith("Sessão Data"):
                try:
                    if len(os.listdir(pasta_pai_dia)) == 0:
                        os.rmdir(pasta_pai_dia)
                except Exception:
                    pass

    def _varrer_e_limpar_sessoes_orfas(self):
        """
        Executado na inicialização do aplicativo: varre 'Procedimentos/' e remove
        quaisquer pastas de procedimentos ou dias que tenham ficado vazias anteriormente.
        """
        pasta_raiz = os.path.join(self.diretorio_base, "Procedimentos")
        if not os.path.exists(pasta_raiz):
            return

        try:
            for nome_dia in os.listdir(pasta_raiz):
                caminho_dia = os.path.join(pasta_raiz, nome_dia)
                if os.path.isdir(caminho_dia) and nome_dia.startswith("Sessão Data"):
                    for nome_proc in os.listdir(caminho_dia):
                        caminho_proc = os.path.join(caminho_dia, nome_proc)
                        if os.path.isdir(caminho_proc):
                            self._limpar_diretorio_se_vazio(caminho_proc)

                    if os.path.exists(caminho_dia) and len(os.listdir(caminho_dia)) == 0:
                        os.rmdir(caminho_dia)
        except Exception:
            pass

    def _limpar_sessao_atual_no_encerramento(self):
        """Hook registrado no atexit para limpeza garantida ao fechar o processo Python."""
        if not self.passos:
            self._limpar_diretorio_se_vazio(self.pasta_sessao)

    def ao_fechar_aplicacao(self):
        """
        Callback acionado quando o usuário clica no botão 'X' para fechar a janela.
        """
        self.gravando = False
        try:
            if hasattr(self, "mouse_listener"):
                self.mouse_listener.stop()
            if hasattr(self, "kb_listener"):
                self.kb_listener.stop()
        except Exception:
            pass

        if not self.passos:
            self._limpar_diretorio_se_vazio(self.pasta_sessao)

        self.destroy()

    def _criar_diretorio_procedimento_organizado(self) -> Tuple[str, str]:
        """
        Cria a estrutura padronizada de diretórios:
        Procedimentos/
          └── Sessão Data DD-MM-AAAA/
                └── Procedimento X - DD-MM-AAAA HHhMMmSSs/
                      └── imagens/
        """
        agora = datetime.now()
        data_str = agora.strftime("%d-%m-%Y")
        data_hora_str = agora.strftime("%d-%m-%Y %Hh%Mm%Ss")
        self.timestamp_proc_atual = data_hora_str

        pasta_raiz_proc = os.path.join(self.diretorio_base, "Procedimentos")
        pasta_sessao_dia = os.path.join(pasta_raiz_proc, f"Sessão Data {data_str}")
        os.makedirs(pasta_sessao_dia, exist_ok=True)

        existentes = [
            d for d in os.listdir(pasta_sessao_dia)
            if os.path.isdir(os.path.join(pasta_sessao_dia, d)) and d.startswith("Procedimento ")
        ]
        self.numero_proc_atual = len(existentes) + 1

        nome_pasta_proc = f"Procedimento {self.numero_proc_atual} - {data_hora_str}"
        caminho_proc = os.path.join(pasta_sessao_dia, nome_pasta_proc)
        caminho_imagens = os.path.join(caminho_proc, "imagens")
        os.makedirs(caminho_imagens, exist_ok=True)

        return caminho_proc, caminho_imagens

    def _renomear_pasta_com_titulo_ia(self, titulo_sugerido: str):
        """
        Após o processamento do Gemini, incorpora o título identificado no nome da pasta física.
        """
        titulo_limpo = limpar_nome_pasta(titulo_sugerido, max_len=42)
        if not titulo_limpo:
            return

        pasta_dia = os.path.dirname(self.pasta_sessao)
        if not os.path.basename(pasta_dia).startswith("Sessão Data"):
            return

        novo_nome = f"Procedimento {self.numero_proc_atual} - {titulo_limpo} - {self.timestamp_proc_atual}"
        novo_caminho = os.path.join(pasta_dia, novo_nome)

        if novo_caminho != self.pasta_sessao and not os.path.exists(novo_caminho):
            try:
                os.rename(self.pasta_sessao, novo_caminho)
                self.pasta_sessao = novo_caminho
                self.pasta_imagens = os.path.join(novo_caminho, "imagens")
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # SUBSEÇÃO 7.2: CONFIGURAÇÃO PERSISTENTE E CONSTRUÇÃO DA INTERFACE GRÁFICA
    # --------------------------------------------------------------------------

    def _carregar_config_local(self) -> str:
        chave_recuperada = ""
        if os.path.exists(self.caminho_config):
            try:
                with open(self.caminho_config, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    if "template_prefs" in dados and isinstance(dados["template_prefs"], dict):
                        self.config_template.update(dados["template_prefs"])

                    chave_enc = dados.get("gemini_api_key_protected", "") or dados.get("gemini_api_key", "")
                    if chave_enc:
                        chave_recuperada = desproteger_api_key(chave_enc)

                    if "gemini_api_key" in dados and chave_recuperada:
                        self.api_key_atual = chave_recuperada
                        self._salvar_config_local()
            except Exception:
                pass

        if not chave_recuperada:
            chave_recuperada = GEMINI_API_KEY_DIRETA.strip() or os.environ.get("GEMINI_API_KEY", "").strip()
        return chave_recuperada

    def _salvar_config_local(self):
        chave_protegida = proteger_api_key(self.api_key_atual) if self.api_key_atual else ""
        impressao_hash = (
            hashlib.sha256(self.api_key_atual.encode("utf-8")).hexdigest()[:16]
            if self.api_key_atual else ""
        )
        dados = {
            "gemini_api_key_protected": chave_protegida,
            "key_sha256_fingerprint": impressao_hash,
            "template_prefs": self.config_template
        }
        try:
            with open(self.caminho_config, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Erro ao Salvar Config", f"Não foi possível salvar config.json:\n{e}")

    def abrir_modal_api_key(self):
        if self.gravando:
            self.alternar_gravacao()
        dialogo = ctk.CTkInputDialog(
            text="Cole abaixo a sua Gemini API Key:\n(Ela será criptografada com DPAPI/SHA-256 no arquivo config.json)",
            title="Configurar Gemini API Key (Protegida)"
        )
        nova_chave = dialogo.get_input()
        if nova_chave is not None and nova_chave.strip():
            self.api_key_atual = nova_chave.strip()
            self._salvar_config_local()
            self._atualizar_visual_botao_api()
            self.lbl_status.configure(
                text="🔒 API Key criptografada e salva em config.json!", text_color="#20c997"
            )

    def abrir_modal_config_template(self):
        if self.gravando:
            self.alternar_gravacao()
        ConfigTemplateModal(self, self.config_template, self._pos_salvar_config_template)

    def _pos_salvar_config_template(self, nova_cfg: dict):
        self.config_template.update(nova_cfg)
        self._salvar_config_local()
        self.lbl_status.configure(
            text="⚙️ Detalhes do Template salvos! Clique em 'Gerar com Gemini' para aplicar.",
            text_color="#20c997"
        )

    def _atualizar_visual_botao_api(self):
        if self.api_key_atual:
            hash_curto = hashlib.sha256(self.api_key_atual.encode("utf-8")).hexdigest()[:5]
            self.btn_api_key.configure(
                text=f"🔒 API (#{hash_curto})", fg_color="#198754", hover_color="#157347"
            )
        else:
            self.btn_api_key.configure(
                text="🔑 Config API", fg_color="#fd7e14", hover_color="#e8590c"
            )

    def _construir_interface(self):
        """Constrói o layout responsivo dividido em Barra Superior, Fila de Passos, Editor e Rodapé."""
        self.grid_columnconfigure(0, weight=4)
        self.grid_columnconfigure(1, weight=6)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        # === BARRA SUPERIOR DE CONTROLES ===
        self.frame_topo = ctk.CTkFrame(self, height=62, corner_radius=0)
        self.frame_topo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

        self.btn_gravar = ctk.CTkButton(
            self.frame_topo, text="▶ Gravar (F9)", fg_color="#28a745",
            hover_color="#218838", font=("Segoe UI", 13, "bold"), width=125,
            command=self.alternar_gravacao
        )
        self.btn_gravar.pack(side="left", padx=(12, 4), pady=12)

        self.btn_print_manual = ctk.CTkButton(
            self.frame_topo, text="📸 Print (F10)", fg_color="#0dcaf0",
            text_color="#000000", hover_color="#31d2f2", font=("Segoe UI", 12, "bold"),
            width=115, command=self.capturar_print_manual_verificacao
        )
        self.btn_print_manual.pack(side="left", padx=4, pady=12)

        self.btn_senha = ctk.CTkButton(
            self.frame_topo, text="🔓 Senha: OFF (F8)", fg_color="#495057",
            hover_color="#343a40", font=("Segoe UI", 12), width=130,
            command=self.alternar_modo_senha
        )
        self.btn_senha.pack(side="left", padx=4, pady=12)

        self.btn_biblioteca = ctk.CTkButton(
            self.frame_topo, text="📚 Biblioteca", fg_color="#6f42c1",
            hover_color="#59359a", font=("Segoe UI", 12, "bold"), width=105,
            command=self.abrir_biblioteca
        )
        self.btn_biblioteca.pack(side="left", padx=4, pady=12)

        self.chk_minimizar = ctk.CTkCheckBox(
            self.frame_topo, text="Minimizar", font=("Segoe UI", 12), width=80
        )
        self.chk_minimizar.pack(side="left", padx=6, pady=12)

        self.lbl_status = ctk.CTkLabel(
            self.frame_topo, text=f"Pasta ativa: {os.path.basename(self.pasta_sessao)}",
            font=("Segoe UI", 12, "italic"), text_color="#adb5bd"
        )
        self.lbl_status.pack(side="left", padx=6)

        self.btn_gerar_ia = ctk.CTkButton(
            self.frame_topo, text="✨ Gerar com Gemini", fg_color="#0d6efd",
            hover_color="#0b5ed7", font=("Segoe UI", 13, "bold"), width=165,
            command=self.solicitar_geracao_ia
        )
        self.btn_gerar_ia.pack(side="right", padx=(6, 12), pady=12)

        self.btn_cfg_template = ctk.CTkButton(
            self.frame_topo, text="⚙️ Editar Template", fg_color="#495057",
            hover_color="#343a40", font=("Segoe UI", 12), width=130,
            command=self.abrir_modal_config_template
        )
        self.btn_cfg_template.pack(side="right", padx=4, pady=12)

        self.cmb_template = ctk.CTkOptionMenu(
            self.frame_topo,
            values=[
                "Padrão (Atual)",
                "POP / Runbook (Infra)",
                "Guia Rápido (Helpdesk N0/N1)",
                "Troubleshooting / Incidente"
            ],
            width=180, font=("Segoe UI", 12), fg_color="#343a40", button_color="#495057"
        )
        self.cmb_template.set("Padrão (Atual)")
        self.cmb_template.pack(side="right", padx=4, pady=12)

        self.btn_api_key = ctk.CTkButton(
            self.frame_topo, text="🔑 API", font=("Segoe UI", 12, "bold"),
            width=110, command=self.abrir_modal_api_key
        )
        self.btn_api_key.pack(side="right", padx=4, pady=12)
        self._atualizar_visual_botao_api()

        # === PAINEL ESQUERDO: FILA DE PASSOS CAPTURADOS ===
        self.frame_esq = ctk.CTkFrame(self)
        self.frame_esq.grid(row=1, column=0, sticky="nsew", padx=(15, 7), pady=(15, 8))
        self.frame_esq.grid_rowconfigure(1, weight=1)
        self.frame_esq.grid_columnconfigure(0, weight=1)

        frame_header_esq = ctk.CTkFrame(self.frame_esq, fg_color="transparent")
        frame_header_esq.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 5))

        self.lbl_titulo_passos = ctk.CTkLabel(
            frame_header_esq, text="Passos Capturados (0)", font=("Segoe UI", 15, "bold")
        )
        self.lbl_titulo_passos.pack(side="left")

        ctk.CTkButton(
            frame_header_esq, text="➕ Novo Procedimento", width=135, height=28,
            fg_color="#495057", hover_color="#343a40", font=("Segoe UI", 12),
            command=self.iniciar_nova_sessao_limpa
        ).pack(side="right")

        self.scroll_passos = ctk.CTkScrollableFrame(self.frame_esq, label_text="")
        self.scroll_passos.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll_passos.grid_columnconfigure(0, weight=1)

        # === PAINEL DIREITO: EDITOR MARKDOWN AO VIVO E EXPORTAÇÃO ===
        self.frame_dir = ctk.CTkFrame(self)
        self.frame_dir.grid(row=1, column=1, sticky="nsew", padx=(8, 15), pady=(15, 8))
        self.frame_dir.grid_rowconfigure(1, weight=1)
        self.frame_dir.grid_columnconfigure(0, weight=1)

        frame_header_dir = ctk.CTkFrame(self.frame_dir, fg_color="transparent")
        frame_header_dir.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        ctk.CTkLabel(
            frame_header_dir, text="Editor Markdown (Ao Vivo)", font=("Segoe UI", 15, "bold")
        ).pack(side="left")

        ctk.CTkButton(
            frame_header_dir, text="📂 Pasta", width=85, fg_color="#6c757d",
            hover_color="#5c636a", command=self.abrir_pasta_sessao
        ).pack(side="right", padx=(5, 0))

        ctk.CTkButton(
            frame_header_dir, text="📄 Exportar PDF", width=115, fg_color="#dc3545",
            hover_color="#bb2d3b", command=self.exportar_pdf
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            frame_header_dir, text="🌐 HTML Único", width=115, fg_color="#0dcaf0",
            text_color="#000000", hover_color="#31d2f2", command=self.exportar_html_unico
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            frame_header_dir, text="💾 Salvar .MD", width=105, fg_color="#198754",
            hover_color="#157347", command=self.salvar_markdown
        ).pack(side="right", padx=5)

        self.txt_editor = ctk.CTkTextbox(
            self.frame_dir, font=("Consolas", 13), wrap="word"
        )
        self.txt_editor.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)
        self.txt_editor.insert(
            "0.0",
            "# AutoDoc IT — Gestão de Conhecimento e Procedimentos (Windows & Linux)\n\n"
            "### Organização Automática de Diretórios:\n"
            "Os seus registros são salvos automaticamente na seguinte hierarquia:\n"
            "```text\n"
            "📁 Procedimentos/\n"
            f" └── 📁 {os.path.basename(os.path.dirname(self.pasta_sessao))}/\n"
            f"      └── 📁 {os.path.basename(self.pasta_sessao)}/\n"
            "```\n\n"
            "### Limpeza Inteligente de Sessões Vazias:\n"
            "- Se você fechar o programa (ou trocar de sessão na Biblioteca) sem ter gravado nenhum passo na sessão atual, a pasta vazia é removida automaticamente.\n"
        )

        # === BARRA DE RODAPÉ INSTITUCIONAL (COPYRIGHT) ===
        self.frame_rodape = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color="#18181b")
        self.frame_rodape.grid(row=2, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

        lbl_caminho_rodape = ctk.CTkLabel(
            self.frame_rodape,
            text=f"📁 Diretório Base: {os.path.join(self.diretorio_base, 'Procedimentos')}",
            font=("Segoe UI", 11), text_color="#71717a"
        )
        lbl_caminho_rodape.pack(side="left", padx=15, pady=4)

        lbl_copyright = ctk.CTkLabel(
            self.frame_rodape,
            text="© 2026 Desenvolvido por Raffael Dutra — Todos os direitos reservados.",
            font=("Segoe UI", 12, "bold"), text_color="#a1a1aa"
        )
        lbl_copyright.pack(side="right", padx=18, pady=4)

    def _salvar_metadados_sessao(self, titulo_geral: str = "", resumo_objetivo: str = ""):
        """Salva o arquivo sessao_meta.json apenas se houver passos registrados na sessão."""
        if not self.passos:
            return

        meta_path = os.path.join(self.pasta_sessao, "sessao_meta.json")
        meta_existente = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_existente = json.load(f)
            except Exception:
                pass

        passos_serializaveis = []
        for p in self.passos:
            copia = {k: v for k, v in p.items() if k != "pil_img"}
            passos_serializaveis.append(copia)

        dados = {
            "titulo_geral": titulo_geral or meta_existente.get("titulo_geral", ""),
            "resumo_objetivo": resumo_objetivo or meta_existente.get("resumo_objetivo", ""),
            "data_formatada": meta_existente.get("data_formatada", datetime.now().strftime("%d/%m/%Y %H:%M")),
            "template": self.cmb_template.get(),
            "passos": passos_serializaveis
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def iniciar_nova_sessao_limpa(self):
        """Inicia um novo procedimento, limpando antes a pasta anterior caso estivesse vazia."""
        if self.gravando:
            self.alternar_gravacao()

        with self.lock:
            pasta_anterior = self.pasta_sessao
            tinha_passos = len(self.passos) > 0

            self.passos.clear()
            self.buffer_texto.clear()
            self.contador_arquivos = 0
            self.ultimo_clique_ts = 0.0

            if not tinha_passos:
                self._limpar_diretorio_se_vazio(pasta_anterior)

            self.pasta_sessao, self.pasta_imagens = self._criar_diretorio_procedimento_organizado()

        self.atualizar_lista_ui()
        self.txt_editor.delete("0.0", "end")
        self.txt_editor.insert(
            "0.0",
            f"# Novo Procedimento Iniciado\n\n"
            f"**Pasta:** `{os.path.basename(self.pasta_sessao)}`\n\n"
            f"Pressione **F9** para começar a gravar ou **F10** para print manual."
        )
        self.lbl_status.configure(
            text=f"✨ Criado: {os.path.basename(self.pasta_sessao)}", text_color="#20c997"
        )

    def abrir_biblioteca(self):
        if self.gravando:
            self.alternar_gravacao()
        BibliotecaModal(self, self.diretorio_base, self.carregar_sessao_existente)

    def carregar_sessao_existente(self, caminho_pasta: str):
        """Carrega um procedimento da Biblioteca, removendo antes a sessão atual se estava vazia."""
        if self.gravando:
            self.alternar_gravacao()

        with self.lock:
            pasta_anterior = self.pasta_sessao
            if pasta_anterior != caminho_pasta and not self.passos:
                self._limpar_diretorio_se_vazio(pasta_anterior)

            self.pasta_sessao = caminho_pasta
            self.pasta_imagens = os.path.join(caminho_pasta, "imagens")
            os.makedirs(self.pasta_imagens, exist_ok=True)
            self.passos.clear()

            meta_path = os.path.join(caminho_pasta, "sessao_meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        if meta.get("template") in self.cmb_template.cget("values"):
                            self.cmb_template.set(meta.get("template"))
                        for item in meta.get("passos", []):
                            caminho_img_abs = os.path.join(caminho_pasta, item.get("imagem", ""))
                            if os.path.exists(caminho_img_abs):
                                item["pil_img"] = Image.open(caminho_img_abs).convert("RGB")
                                self.passos.append(item)
                                self.contador_arquivos = max(
                                    self.contador_arquivos, item.get("id_arquivo", 0)
                                )
                except Exception:
                    pass

            md_path = os.path.join(caminho_pasta, "procedimento.md")
            if os.path.exists(md_path):
                try:
                    with open(md_path, "r", encoding="utf-8") as f:
                        self.txt_editor.delete("0.0", "end")
                        self.txt_editor.insert("0.0", f.read())
                except Exception:
                    pass

        self.atualizar_lista_ui()
        self.lbl_status.configure(
            text=f"📚 Carregado: {os.path.basename(caminho_pasta)}", text_color="#0dcaf0"
        )

    # --------------------------------------------------------------------------
    # SUBSEÇÃO 7.3: CAPTURA DE TELA, HARDWARE LISTENERS E FILTRO DUPLO CLIQUE
    # --------------------------------------------------------------------------

    def _atualizar_geometria_loop(self):
        """Monitora a posição da janela do AutoDoc IT para ignorar cliques feitos dentro dela."""
        if self.state() != "iconic":
            x = self.winfo_rootx()
            y = self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            self.rect_janela = (x, y, x + w, y + h)
        else:
            self.rect_janela = (-1, -1, -1, -1)
        self.after(200, self._atualizar_geometria_loop)

    def _clique_dentro_da_interface(self, x: int, y: int) -> bool:
        x1, y1, x2, y2 = self.rect_janela
        return (x1 <= x <= x2) and (y1 <= y <= y2)

    def alternar_gravacao(self):
        with self.lock:
            self._descarregar_buffer_teclado(tecla_finalizadora=None)
            self.gravando = not self.gravando

        if self.gravando:
            self.btn_gravar.configure(text="⏸ Pausar (F9)", fg_color="#dc3545", hover_color="#c82333")
            self.lbl_status.configure(text="🔴 GRAVANDO... (F9 pausa | F10 print manual | F8 senha)", text_color="#ff6b6b")
            if self.chk_minimizar.get() == 1:
                self.iconify()
        else:
            self.btn_gravar.configure(text="▶ Gravar (F9)", fg_color="#28a745", hover_color="#218838")
            self.lbl_status.configure(text=f"⏸ Pausado ({len(self.passos)} passos)", text_color="#adb5bd")
            self._salvar_metadados_sessao()
            if self.state() == "iconic":
                self.deiconify()

    def alternar_modo_senha(self):
        with self.lock:
            self._descarregar_buffer_teclado(tecla_finalizadora=None)
            self.modo_senha = not self.modo_senha

        if self.modo_senha:
            self.btn_senha.configure(text="🔒 Senha: ON (F8)", fg_color="#d63384", hover_color="#b02a6c")
        else:
            self.btn_senha.configure(text="🔓 Senha: OFF (F8)", fg_color="#495057", hover_color="#343a40")

    def _capturar_zoom(
        self,
        x: int,
        y: int,
        id_arquivo: int,
        modo_marcador: str = "clique",
        selo_inferior: str = ""
    ):
        """
        Realiza a captura ultrarrápida do monitor ativo via MSS e gera duas imagens:
        1. 'captura_XXX.png': Recorte de 550x550px focado na ação com marcador visual.
        2. 'captura_XXX_full.png': Tela inteira com moldura indicando a área recortada (Zoom Out).
        """
        with mss.mss() as sct:
            monitor_escolhido = sct.monitors[1]
            for m in sct.monitors[1:]:
                if (m["left"] <= x < m["left"] + m["width"]) and (m["top"] <= y < m["top"] + m["height"]):
                    monitor_escolhido = m
                    break

            sct_img = sct.grab(monitor_escolhido)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX").convert("RGBA")

        largura_tela, altura_tela = img.size
        rel_x = max(0, min(x - monitor_escolhido["left"], largura_tela - 1))
        rel_y = max(0, min(y - monitor_escolhido["top"], altura_tela - 1))

        metade = self.tamanho_zoom // 2
        esq = max(0, min(rel_x - metade, largura_tela - self.tamanho_zoom))
        topo = max(0, min(rel_y - metade, altura_tela - self.tamanho_zoom))
        dir_ = min(largura_tela, esq + self.tamanho_zoom)
        base = min(altura_tela, topo + self.tamanho_zoom)

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        if modo_marcador == "clique":
            r_ext, r_int = 26, 6
            draw.ellipse(
                (rel_x - r_ext, rel_y - r_ext, rel_x + r_ext, rel_y + r_ext),
                fill=(255, 59, 48, 75), outline=(255, 59, 48, 230), width=3
            )
            draw.ellipse(
                (rel_x - r_int, rel_y - r_int, rel_x + r_int, rel_y + r_int),
                fill=(255, 59, 48, 255)
            )
        elif modo_marcador == "digitacao":
            draw.rounded_rectangle(
                (rel_x - 45, rel_y - 18, rel_x + 45, rel_y + 18),
                radius=6, fill=(13, 110, 253, 35), outline=(13, 110, 253, 180), width=2
            )

        img_composta = Image.alpha_composite(img, overlay)

        # 1. Salva a imagem recortada (Zoom In)
        img_recortada = img_composta.crop((esq, topo, dir_, base)).convert("RGB")

        if selo_inferior:
            draw_zoom = ImageDraw.Draw(img_recortada)
            largura_selo = min(520, max(140, len(selo_inferior) * 8 + 30))
            draw_zoom.rounded_rectangle(
                (12, self.tamanho_zoom - 46, 12 + largura_selo, self.tamanho_zoom - 12),
                radius=6, fill=(15, 23, 42), outline=(13, 202, 240), width=2
            )
            draw_zoom.text((24, self.tamanho_zoom - 35), selo_inferior, fill=(255, 255, 255))

        os.makedirs(self.pasta_imagens, exist_ok=True)
        caminho_rel_zoom = os.path.join("imagens", f"captura_{id_arquivo:03d}.png")
        caminho_abs_zoom = os.path.join(self.pasta_sessao, caminho_rel_zoom)
        img_recortada.save(caminho_abs_zoom, "PNG")

        # 2. Salva a imagem de Tela Cheia (Zoom Out)
        img_full_marcada = img_composta.copy()
        draw_full = ImageDraw.Draw(img_full_marcada)
        draw_full.rectangle((esq, topo, dir_, base), outline=(13, 202, 240, 220), width=3)

        caminho_rel_full = os.path.join("imagens", f"captura_{id_arquivo:03d}_full.png")
        caminho_abs_full = os.path.join(self.pasta_sessao, caminho_rel_full)
        img_full_marcada.convert("RGB").save(caminho_abs_full, "PNG")

        return caminho_rel_zoom, img_recortada, (esq, topo)

    def capturar_print_manual_verificacao(self):
        """Atalho F10: Captura um print limpo na posição atual do mouse sem precisar clicar."""
        with self.lock:
            self._descarregar_buffer_teclado(tecla_finalizadora=None)

            x, y = obter_posicao_atual_mouse(self.ultimo_clique_xy)
            janela_nome, eh_terminal = obter_contexto_janela_ativa()

            self.contador_arquivos += 1
            caminho_img, pil_img, crop_offset = self._capturar_zoom(
                x, y, self.contador_arquivos,
                modo_marcador="nenhum",
                selo_inferior="Verificacao Manual (F10)"
            )

            novo_passo = {
                "id_arquivo": self.contador_arquivos,
                "tipo": "Verificação (F10)",
                "janela": janela_nome,
                "eh_terminal": eh_terminal,
                "comando_bruto": "",
                "detalhe": f"Captura manual de verificação/status em ({x}, {y})",
                "imagem": caminho_img,
                "pil_img": pil_img,
                "crop_offset": crop_offset
            }
            self.passos.append(novo_passo)
            self._salvar_metadados_sessao()

        self.atualizar_lista_ui()
        self.lbl_status.configure(
            text=f"📸 Print de verificação (F10) registrado no Passo {len(self.passos):02d}!",
            text_color="#0dcaf0"
        )

    def _descarregar_buffer_teclado(self, tecla_finalizadora: Optional[str] = None):
        """Agrupa todas as teclas digitadas em um único passo lógico ao pressionar Enter, Tab ou clicar."""
        if not self.buffer_texto:
            return

        texto_digitado = "".join(self.buffer_texto)
        self.buffer_texto.clear()

        self.contador_arquivos += 1
        x, y = obter_posicao_foco_digitacao(self.foco_digitacao_xy or self.ultimo_clique_xy)
        self.foco_digitacao_xy = None

        janela_nome, eh_terminal = self.janela_digitacao_atual
        if janela_nome == "Sistema Operacional":
            janela_nome, eh_terminal = obter_contexto_janela_ativa()

        selo = ""
        sufixo_enter = ""
        if tecla_finalizadora == "ENTER":
            selo = "Digitou + [Enter]"
            sufixo_enter = " + pressionou [Enter]"
        elif tecla_finalizadora == "TAB":
            selo = "Digitou + [Tab]"
            sufixo_enter = " + pressionou [Tab]"

        caminho_img, pil_img, crop_offset = self._capturar_zoom(
            x, y, self.contador_arquivos, modo_marcador="digitacao", selo_inferior=selo
        )

        valor_exibicao = "******** (Credencial Oculta)" if self.modo_senha else texto_digitado
        if eh_terminal:
            tipo_passo = "Comando CLI"
            prefixo_acao = "Executou no terminal"
        elif tecla_finalizadora == "ENTER":
            tipo_passo = "Pesquisa / Enter"
            prefixo_acao = "Digitou"
        else:
            tipo_passo = "Digitação"
            prefixo_acao = "Digitou"

        novo_passo = {
            "id_arquivo": self.contador_arquivos,
            "tipo": tipo_passo,
            "janela": janela_nome,
            "eh_terminal": eh_terminal,
            "comando_bruto": "" if self.modo_senha else (texto_digitado if eh_terminal else ""),
            "detalhe": f"{prefixo_acao}: '{valor_exibicao}'{sufixo_enter}",
            "imagem": caminho_img,
            "pil_img": pil_img,
            "crop_offset": crop_offset
        }
        self.passos.append(novo_passo)
        self._salvar_metadados_sessao()
        self.after(0, self.atualizar_lista_ui)

    def _registrar_enter_isolado(self):
        """Registra quando o usuário aperta Enter em uma caixa de busca já preenchida ou diálogo."""
        agora = time.time()
        if (agora - self.ultimo_atalho_ts) < 0.35:
            return
        self.ultimo_atalho_ts = agora

        janela_nome, eh_terminal = obter_contexto_janela_ativa()
        x, y = obter_posicao_foco_digitacao(self.ultimo_clique_xy)

        self.contador_arquivos += 1
        caminho_img, pil_img, crop_offset = self._capturar_zoom(
            x, y, self.contador_arquivos, modo_marcador="digitacao", selo_inferior="Tecla: [Enter]"
        )

        novo_passo = {
            "id_arquivo": self.contador_arquivos,
            "tipo": "Tecla Enter",
            "janela": janela_nome,
            "eh_terminal": eh_terminal,
            "comando_bruto": "",
            "detalhe": "Pressionou [Enter] para confirmar / pesquisar",
            "imagem": caminho_img,
            "pil_img": pil_img,
            "crop_offset": crop_offset
        }
        self.passos.append(novo_passo)
        self._salvar_metadados_sessao()
        self.after(0, self.atualizar_lista_ui)

    def _registrar_passo_colar_clipboard(self):
        """Captura comandos ou textos colados via Ctrl+V, Shift+Insert ou clique direito em terminal."""
        self._descarregar_buffer_teclado(tecla_finalizadora=None)
        threading.Event().wait(0.08)

        texto_colado = ler_texto_clipboard(self)
        janela_nome, eh_terminal = obter_contexto_janela_ativa()
        x, y = obter_posicao_foco_digitacao(self.ultimo_clique_xy)

        self.contador_arquivos += 1
        caminho_img, pil_img, crop_offset = self._capturar_zoom(
            x, y, self.contador_arquivos, modo_marcador="digitacao", selo_inferior="Teclas: Ctrl + V"
        )

        if self.modo_senha:
            valor_exibicao = "******** (Conteúdo Colado Oculto)"
            cmd_bruto = ""
        else:
            valor_exibicao = texto_colado if texto_colado else "(Conteúdo da Área de Transferência)"
            cmd_bruto = texto_colado if eh_terminal else ""

        tipo_passo = "Comando CLI (Colado)" if eh_terminal else "Colou (Ctrl+V)"
        novo_passo = {
            "id_arquivo": self.contador_arquivos,
            "tipo": tipo_passo,
            "janela": janela_nome,
            "eh_terminal": eh_terminal,
            "comando_bruto": cmd_bruto,
            "detalhe": f"Colou: '{valor_exibicao[:120]}'",
            "imagem": caminho_img,
            "pil_img": pil_img,
            "crop_offset": crop_offset
        }
        self.passos.append(novo_passo)
        self._salvar_metadados_sessao()
        self.after(0, self.atualizar_lista_ui)

    def _registrar_passo_atalho(self, combinacao_str: str):
        """Registra combinações de teclas modificadoras (ex: Win + R, Alt + F4)."""
        agora = time.time()
        if (agora - self.ultimo_atalho_ts) < 0.35:
            return
        self.ultimo_atalho_ts = agora

        self._descarregar_buffer_teclado(tecla_finalizadora=None)
        janela_nome, eh_terminal = obter_contexto_janela_ativa()
        x, y = obter_posicao_foco_digitacao(self.ultimo_clique_xy)

        self.contador_arquivos += 1
        caminho_img, pil_img, crop_offset = self._capturar_zoom(
            x, y, self.contador_arquivos, modo_marcador="nenhum", selo_inferior=f"Teclas: {combinacao_str}"
        )

        novo_passo = {
            "id_arquivo": self.contador_arquivos,
            "tipo": "Atalho",
            "janela": janela_nome,
            "eh_terminal": eh_terminal,
            "comando_bruto": "",
            "detalhe": f"Pressionou atalho: [{combinacao_str}]",
            "imagem": caminho_img,
            "pil_img": pil_img,
            "crop_offset": crop_offset
        }
        self.passos.append(novo_passo)
        self._salvar_metadados_sessao()
        self.after(0, self.atualizar_lista_ui)

    def _ao_clicar(self, x, y, button, pressed):
        """Callback global de clique do mouse (filtra auto-cliques e agrupa Duplo Clique)."""
        if not self.gravando or not pressed:
            return

        if self._clique_dentro_da_interface(int(x), int(y)):
            return

        with self.lock:
            tinha_texto_pendente = len(self.buffer_texto) > 0
            self._descarregar_buffer_teclado(tecla_finalizadora=None)

            agora = time.time()
            ix, iy = int(x), int(y)

            if (
                not tinha_texto_pendente
                and self.passos
                and self.ultimo_clique_xy is not None
                and self.ultimo_clique_botao == button
                and (agora - self.ultimo_clique_ts) <= 0.45
            ):
                dist = math.hypot(ix - self.ultimo_clique_xy[0], iy - self.ultimo_clique_xy[1])
                ultimo_passo = self.passos[-1]
                if dist <= 15 and ultimo_passo.get("tipo") in ("Clique", "Duplo Clique"):
                    ultimo_passo["tipo"] = "Duplo Clique"
                    nome_botao = "Botão Direito" if button == mouse.Button.right else "Botão Esquerdo"
                    ultimo_passo["detalhe"] = f"Duplo Clique ({nome_botao}) em ({ix}, {iy})"
                    self.ultimo_clique_ts = agora
                    self._salvar_metadados_sessao()
                    self.after(0, self.atualizar_lista_ui)
                    return

            self.ultimo_clique_xy = (ix, iy)
            self.ultimo_clique_ts = agora
            self.ultimo_clique_botao = button

            janela_nome, eh_terminal = obter_contexto_janela_ativa()

            if eh_terminal and button == mouse.Button.right:
                self._registrar_passo_colar_clipboard()
                return

            self.contador_arquivos += 1
            nome_botao = "Botão Direito" if button == mouse.Button.right else "Botão Esquerdo"
            caminho_img, pil_img, crop_offset = self._capturar_zoom(
                ix, iy, self.contador_arquivos, modo_marcador="clique"
            )

            novo_passo = {
                "id_arquivo": self.contador_arquivos,
                "tipo": "Clique",
                "janela": janela_nome,
                "eh_terminal": eh_terminal,
                "comando_bruto": "",
                "detalhe": f"{nome_botao} em ({ix}, {iy})",
                "imagem": caminho_img,
                "pil_img": pil_img,
                "crop_offset": crop_offset
            }
            self.passos.append(novo_passo)
            self._salvar_metadados_sessao()
            self.after(0, self.atualizar_lista_ui)

    def _identificar_modificador(self, key) -> Optional[str]:
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return "Ctrl"
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return "Alt"
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            return "Shift"
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            return "Win"
        return None

    def _extrair_nome_tecla(self, key) -> Optional[str]:
        if hasattr(key, "char") and key.char is not None:
            codigo = ord(key.char)
            if 1 <= codigo <= 26:
                return chr(codigo + 64)
            return key.char.upper()

        if hasattr(key, "vk") and key.vk is not None:
            if 65 <= key.vk <= 90 or 48 <= key.vk <= 57:
                return chr(key.vk)

        if hasattr(key, "name") and key.name:
            return key.name.upper()
        return None

    def _ao_soltar_tecla(self, key):
        mod = self._identificar_modificador(key)
        if mod and mod in self.modificadores_ativos:
            self.modificadores_ativos.discard(mod)

    def _ao_pressionar_tecla(self, key):
        if key == keyboard.Key.f9:
            self.after(0, self.alternar_gravacao)
            return

        if key == keyboard.Key.f8:
            self.after(0, self.alternar_modo_senha)
            return

        if key == keyboard.Key.f10:
            self.after(0, self.capturar_print_manual_verificacao)
            return

        mod = self._identificar_modificador(key)
        if mod:
            self.modificadores_ativos.add(mod)
            return

        if not self.gravando:
            return

        with self.lock:
            nome_tecla = self._extrair_nome_tecla(key)

            if ("Ctrl" in self.modificadores_ativos and nome_tecla == "V") or (
                "Shift" in self.modificadores_ativos and key == keyboard.Key.insert
            ):
                self._registrar_passo_colar_clipboard()
                return

            if any(m in self.modificadores_ativos for m in ("Ctrl", "Alt", "Win")):
                if nome_tecla:
                    ordem_mods = [m for m in ("Ctrl", "Win", "Alt", "Shift") if m in self.modificadores_ativos]
                    combinacao = " + ".join(ordem_mods + [nome_tecla])
                    self._registrar_passo_atalho(combinacao)
                return

            if nome_tecla and re.match(r"^F([1-7]|1[1-2])$", nome_tecla):
                self._registrar_passo_atalho(nome_tecla)
                return

            if key == keyboard.Key.enter:
                if self.buffer_texto:
                    self._descarregar_buffer_teclado(tecla_finalizadora="ENTER")
                else:
                    self._registrar_enter_isolado()
                return

            if key == keyboard.Key.tab:
                if self.buffer_texto:
                    self._descarregar_buffer_teclado(tecla_finalizadora="TAB")
                return

            if not self.buffer_texto:
                self.janela_digitacao_atual = obter_contexto_janela_ativa()

            pos_caret = obter_posicao_foco_digitacao(None)
            if pos_caret != (960, 540):
                self.foco_digitacao_xy = pos_caret

            if key == keyboard.Key.space:
                self.buffer_texto.append(" ")
            elif key == keyboard.Key.backspace:
                if self.buffer_texto:
                    self.buffer_texto.pop()
            elif hasattr(key, "char") and key.char is not None and ord(key.char) >= 32:
                self.buffer_texto.append(key.char)

    def _iniciar_listeners_globais(self):
        self.mouse_listener = mouse.Listener(on_click=self._ao_clicar)
        self.kb_listener = keyboard.Listener(
            on_press=self._ao_pressionar_tecla, on_release=self._ao_soltar_tecla
        )
        self.mouse_listener.daemon = True
        self.kb_listener.daemon = True
        self.mouse_listener.start()
        self.kb_listener.start()

    # --------------------------------------------------------------------------
    # SUBSEÇÃO 7.4: GERENCIAMENTO VISUAL DOS CARDS (REORDENAÇÃO, EDIÇÃO, EXCLUSÃO)
    # --------------------------------------------------------------------------

    def atualizar_lista_ui(self):
        for widget in self.scroll_passos.winfo_children():
            widget.destroy()

        total = len(self.passos)
        self.lbl_titulo_passos.configure(text=f"Passos Capturados ({total})")

        for idx, item in enumerate(self.passos):
            num_passo = idx + 1
            eh_term = item.get("eh_terminal", False)
            tipo_item = item.get("tipo", "Clique")
            eh_verif = tipo_item == "Verificação (F10)"
            eh_duplo = tipo_item == "Duplo Clique"

            if eh_verif:
                cor_card = "#163235"
            elif eh_term:
                cor_card = "#1e293b"
            elif eh_duplo:
                cor_card = "#3b2332"
            else:
                cor_card = "#2b2b2b"

            card = ctk.CTkFrame(self.scroll_passos, corner_radius=8, fg_color=cor_card)
            card.grid(row=idx, column=0, sticky="ew", padx=5, pady=6)
            card.grid_columnconfigure(1, weight=1)

            ctk_thumb = ctk.CTkImage(light_image=item["pil_img"], dark_image=item["pil_img"], size=(85, 85))
            lbl_img = ctk.CTkLabel(card, image=ctk_thumb, text="")
            lbl_img.grid(row=0, column=0, rowspan=3, padx=10, pady=8)

            icone_tipo = "📸 " if eh_verif else ("⌨️ " if eh_term else ("⚡ " if eh_duplo else ""))
            lbl_titulo = ctk.CTkLabel(
                card, text=f"Passo {num_passo:02d} — {icone_tipo}{tipo_item}",
                font=("Segoe UI", 13, "bold"), anchor="w"
            )
            lbl_titulo.grid(row=0, column=1, sticky="ew", padx=5, pady=(8, 0))

            janela_curta = item.get("janela", "Sistema")[:35]
            lbl_janela = ctk.CTkLabel(
                card, text=f"🪟 {janela_curta}", font=("Segoe UI", 11, "bold"),
                text_color="#38bdf8", anchor="w"
            )
            lbl_janela.grid(row=1, column=1, sticky="ew", padx=5, pady=0)

            lbl_detalhe = ctk.CTkLabel(
                card, text=item["detalhe"], font=("Segoe UI", 12),
                text_color="#adb5bd", anchor="w", wraplength=185
            )
            lbl_detalhe.grid(row=2, column=1, sticky="ew", padx=5, pady=(0, 8))

            frame_ordem = ctk.CTkFrame(card, fg_color="transparent")
            frame_ordem.grid(row=0, column=2, rowspan=3, padx=(4, 2))

            btn_subir = ctk.CTkButton(
                frame_ordem, text="▲", width=28, height=28, fg_color="#495057",
                hover_color="#343a40", font=("Segoe UI", 11, "bold"),
                state="normal" if idx > 0 else "disabled",
                command=lambda i=idx: self.mover_passo(i, -1)
            )
            btn_subir.pack(pady=(0, 3))

            btn_descer = ctk.CTkButton(
                frame_ordem, text="▼", width=28, height=28, fg_color="#495057",
                hover_color="#343a40", font=("Segoe UI", 11, "bold"),
                state="normal" if idx < (total - 1) else "disabled",
                command=lambda i=idx: self.mover_passo(i, 1)
            )
            btn_descer.pack(pady=(3, 0))

            btn_blur = ctk.CTkButton(
                card, text="🖌️", width=34, height=36, fg_color="#0d6efd",
                hover_color="#0b5ed7", font=("Segoe UI", 14),
                command=lambda i=idx: self.abrir_estudio_imagem(i)
            )
            btn_blur.grid(row=0, column=3, rowspan=3, padx=3)

            btn_del = ctk.CTkButton(
                card, text="🗑", width=34, height=36, fg_color="#dc3545",
                hover_color="#b02a37", font=("Segoe UI", 14),
                command=lambda i=idx: self.excluir_passo(i)
            )
            btn_del.grid(row=0, column=4, rowspan=3, padx=(3, 8))

    def mover_passo(self, indice: int, direcao: int):
        novo_indice = indice + direcao
        with self.lock:
            if 0 <= indice < len(self.passos) and 0 <= novo_indice < len(self.passos):
                self.passos[indice], self.passos[novo_indice] = (
                    self.passos[novo_indice],
                    self.passos[indice],
                )
        self._salvar_metadados_sessao()
        self.atualizar_lista_ui()
        self.lbl_status.configure(
            text=f"↕️ Passo movido da posição {indice + 1:02d} para {novo_indice + 1:02d}.",
            text_color="#0dcaf0"
        )

    def abrir_estudio_imagem(self, indice: int):
        if self.gravando:
            self.alternar_gravacao()

        if 0 <= indice < len(self.passos):
            item = self.passos[indice]
            EditorImagemModal(
                self, item_passo=item, pasta_sessao=self.pasta_sessao,
                callback_atualizar=lambda: self._pos_salvar_estudio(indice + 1)
            )

    def _pos_salvar_estudio(self, numero_passo: int):
        self.atualizar_lista_ui()
        self.lbl_status.configure(
            text=f"🎨 Anotações/Blur salvos no Passo {numero_passo:02d} (Zoom e Tela Cheia sincronizados)!",
            text_color="#20c997"
        )

    def excluir_passo(self, indice: int):
        with self.lock:
            if 0 <= indice < len(self.passos):
                removido = self.passos.pop(indice)
                self.lbl_status.configure(text=f"Passo removido ({removido['detalhe']})")
        self._salvar_metadados_sessao()
        self.atualizar_lista_ui()

    # --------------------------------------------------------------------------
    # SUBSEÇÃO 7.5: INTEGRAÇÃO COM GOOGLE GEMINI API E CONSTRUÇÃO DO MARKDOWN
    # --------------------------------------------------------------------------

    def solicitar_geracao_ia(self):
        if self.gravando:
            self.alternar_gravacao()

        if not self.passos:
            messagebox.showwarning("Aviso", "Grave pelo menos um passo antes de gerar a documentação.")
            return

        if not self.api_key_atual:
            self.abrir_modal_api_key()
            if not self.api_key_atual:
                return

        self.btn_gerar_ia.configure(state="disabled", text="⏳ Processando...")
        self.lbl_status.configure(
            text=f"Processando {len(self.passos)} passos com o Gemini 2.5 Flash...",
            text_color="#ffc107"
        )

        # Abre a janela modal de progresso em tempo real
        self.modal_progresso = ProgressoGeracaoModal(
            self,
            total_passos=len(self.passos),
            nome_template=self.cmb_template.get()
        )

        threading.Thread(target=self._thread_chamar_gemini, daemon=True).start()

    def _obter_instrucao_template(self, nome_template: str) -> str:
        extra_user = self.config_template.get("instrucao_extra_ia", "").strip()
        base = ""
        if nome_template == "POP / Runbook (Infra)":
            base = (
                "Adote tom formal de Procedimento Operacional Padrão (POP / Runbook) voltado para "
                "Engenharia de Redes, Segurança e Infraestrutura de TI. Detalhe parâmetros técnicos, "
                "liste pré-requisitos rigorosos, checklist de validação pós-mudança e elabore um plano "
                "de Rollback claro caso a operação apresente falha."
            )
        elif nome_template == "Guia Rápido (Helpdesk N0/N1)":
            base = (
                "Adote tom didático, amigável e extremamente simples, voltado para autoatendimento "
                "(Helpdesk Nível 0 / Nível 1). Evite jargões complexos e explique exatamente onde o "
                "usuário deve olhar e clicar."
            )
        elif nome_template == "Troubleshooting / Incidente":
            base = (
                "Estruture a explicação com foco em Diagnóstico e Resolução de Incidente (Troubleshooting). "
                "Destaque o que cada comando ou tela está verificando para isolar a causa raiz e aplicar a correção."
            )
        else:
            base = "Gere uma documentação passo a passo limpa, direta e objetiva."

        return f"{base}\nInstruções adicionais do autor: {extra_user}" if extra_user else base

    def _thread_chamar_gemini(self):
        modal = getattr(self, "modal_progresso", None)

        def ui_prog(valor: float, etapa: str = None, detalhe: str = None, log: str = None):
            """Helper seguro para atualizar a janela modal a partir da thread secundária."""
            def _update():
                if modal and modal.winfo_exists():
                    modal.atualizar_progresso(valor, etapa, detalhe)
                    if log:
                        modal.adicionar_log(log)
            self.after(0, _update)

        try:
            template_escolhido = self.cmb_template.get()
            instrucao_estilo = self._obter_instrucao_template(template_escolhido)
            total_passos = len(self.passos)

            # ETAPA 1: Preparação das imagens e prompts (0% a 20%)
            ui_prog(
                0.05,
                etapa="📦 Etapa 1/4: Preparando capturas de tela e metadados...",
                detalhe=f"Empacotando {total_passos} imagens para envio...",
                log="Inicializando cliente Google GenAI..."
            )

            client = genai.Client(api_key=self.api_key_atual)
            conteudos = [
                "Você é um Especialista em Documentação Técnica de TI e Infraestrutura.\n"
                f"{instrucao_estilo}\n\n"
                f"REGRA OBRIGATÓRIA DE INTEGRIDADE: Foram capturados exatamente {total_passos} passos "
                f"(numerados de 1 a {total_passos}). Você DEVE retornar exatamente {total_passos} objetos "
                "na lista 'passos', mantendo a correspondência 1-para-1 exata com cada 'numero_passo'. "
                "JAMAIS pule, omita ou agrupe dois passos em um só, mesmo que duas imagens pareçam semelhantes.\n"
                "Nas imagens de clique, o alvo vermelho indica onde o usuário clicou. "
                "Nos passos 'Pesquisa / Enter' ou 'Tecla Enter', destaque que o usuário pressionou Enter para submeter."
            ]

            for idx, item in enumerate(self.passos):
                if modal and modal.cancelado:
                    raise InterruptedError("Operação cancelada pelo usuário.")

                num_passo = idx + 1
                contexto_passo = (
                    f"=== PASSO {num_passo} DE {total_passos} ===\n"
                    f"Janela Ativa: '{item.get('janela', 'Sistema')}' | "
                    f"Terminal/CLI: {'Sim' if item.get('eh_terminal') else 'Não'} | "
                    f"Tipo de Ação: {item['tipo']} | Detalhe Registrado: {item['detalhe']}"
                )
                conteudos.append(contexto_passo)
                conteudos.append(item["pil_img"])

                prog_empacotamento = 0.05 + (0.15 * (num_passo / total_passos))
                ui_prog(
                    prog_empacotamento,
                    detalhe=f"Preparando imagem do Passo {num_passo} de {total_passos} ({item['tipo']})...",
                    log=f"✔ Passo {num_passo:02d}/{total_passos:02d} anexado ({item['tipo']} em '{item.get('janela', 'Sistema')[:28]}')"
                )

            # ETAPA 2: Conexão e envio para a API do Gemini (20% a 30%)
            if modal and modal.cancelado:
                raise InterruptedError("Operação cancelada pelo usuário.")

            ui_prog(
                0.25,
                etapa="☁️ Etapa 2/4: Enviando imagens para o Gemini 2.5 Flash...",
                detalhe="Aguardando início da análise visual pela IA (isso pode levar alguns segundos)...",
                log="Enviando pacote multimodal para a nuvem do Google Gemini..."
            )

            resposta_stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=conteudos,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DocumentoProcedimento,
                    temperature=0.15,
                ),
            )

            # ETAPA 3: Recebimento em Streaming em Tempo Real (30% a 88%)
            texto_json_acumulado = ""
            ultimo_passo_detectado = 0
            estimativa_chars_total = max(800, total_passos * 380)

            ui_prog(
                0.30,
                etapa="🧠 Etapa 3/4: Gemini analisando telas e redigindo passos...",
                detalhe="Conectado! Recebendo estrutura da documentação em tempo real...",
                log="Conexão estabelecida! Recebendo pacotes de texto (Streaming)..."
            )

            for chunk in resposta_stream:
                if modal and modal.cancelado:
                    raise InterruptedError("Operação cancelada pelo usuário.")

                if chunk.text:
                    texto_json_acumulado += chunk.text

                    # Conta quantos passos já foram estruturados no JSON parcial
                    passos_prontos = len(re.findall(r'"numero_passo"\s*:', texto_json_acumulado))
                    chars_recebidos = len(texto_json_acumulado)

                    # Calcula o avanço da barra entre 30% e 88%
                    fator_passos = passos_prontos / total_passos
                    fator_chars = min(0.95, chars_recebidos / estimativa_chars_total)
                    progresso_stream = 0.30 + (0.58 * max(fator_passos, fator_chars))

                    msg_log_passo = None
                    if passos_prontos > ultimo_passo_detectado:
                        ultimo_passo_detectado = passos_prontos
                        msg_log_passo = f"✍️ IA redigiu o Passo {passos_prontos:02d} de {total_passos:02d}..."

                    ui_prog(
                        progresso_stream,
                        etapa=f"🧠 Etapa 3/4: Redigindo documentação ({min(passos_prontos, total_passos)}/{total_passos} passos)...",
                        detalhe=f"Recebidos {chars_recebidos} caracteres da IA em tempo real...",
                        log=msg_log_passo
                    )

            # ETAPA 4: Validação e Montagem do Documento (88% a 100%)
            ui_prog(
                0.92,
                etapa="📝 Etapa 4/4: Formatando documento Markdown e salvando...",
                detalhe="Validando estrutura de dados e organizando diretórios...",
                log="Resposta completa recebida! Validando schema JSON..."
            )

            try:
                doc: DocumentoProcedimento = DocumentoProcedimento.model_validate_json(texto_json_acumulado)
            except AttributeError:
                doc: DocumentoProcedimento = DocumentoProcedimento.parse_raw(texto_json_acumulado)

            self._renomear_pasta_com_titulo_ia(doc.titulo_geral)
            markdown_gerado = self._montar_texto_markdown(doc, template_escolhido)
            self._salvar_metadados_sessao(doc.titulo_geral, doc.resumo_objetivo)

            self.after(0, lambda: self._concluir_geracao_ui(markdown_gerado, None))

        except InterruptedError as cancel_err:
            self.after(0, lambda: self._concluir_geracao_ui(None, str(cancel_err), cancelado=True))
        except Exception as erro:
            self.after(0, lambda: self._concluir_geracao_ui(None, str(erro), cancelado=False))

    def _montar_texto_markdown(self, doc: DocumentoProcedimento, template: str) -> str:
        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
        autor = self.config_template.get("autor_padrao", "Raffael Dutra")
        org = self.config_template.get("org_padrao", "TI / Infraestrutura")
        mostrar_janela = self.config_template.get("incluir_janela_passo", True)
        mostrar_nota = self.config_template.get("incluir_nota_ia", True)
        rodape_custom = self.config_template.get("rodape_customizado", "")

        linhas = [f"# {doc.titulo_geral}\n"]

        if template == "POP / Runbook (Infra)":
            linhas.extend([
                "| Organização / Setor | Autor / Responsável | Data de Emissão | Tipo |",
                "| :--- | :--- | :--- | :--- |",
                f"| {org} | {autor} | {data_atual} | **POP / Runbook Técnico** |\n",
                f"**Objetivo Operacional:** {doc.resumo_objetivo}\n",
                "---\n",
                "## 1. Pré-requisitos e Acessos Necessários\n"
            ])
            for req in (doc.pre_requisitos or ["Acesso administrativo ao equipamento/servidor"]):
                linhas.append(f"- [ ] {req}")
            linhas.append("\n---\n## 2. Procedimento de Execução\n")

        elif template == "Guia Rápido (Helpdesk N0/N1)":
            linhas.extend([
                f"> **Para que serve este guia?** {doc.resumo_objetivo}  ",
                f"> **Elaborado por:** {autor} ({org})\n",
                "---\n",
                "## Passo a Passo Ilustrado\n"
            ])

        elif template == "Troubleshooting / Incidente":
            linhas.extend([
                f"**Escopo do Diagnóstico / Incidente:** {doc.resumo_objetivo}  ",
                f"**Responsável:** {autor} — {org} | **Data:** {data_atual}\n",
                "---\n",
                "## 1. Verificações Iniciais\n"
            ])
            for req in (doc.pre_requisitos or ["Verificar conectividade básica"]):
                linhas.append(f"- {req}")
            linhas.append("\n---\n## 2. Passos de Diagnóstico e Solução\n")

        else:
            linhas.extend([
                f"**Objetivo:** {doc.resumo_objetivo}  ",
                f"**Autor / Setor:** {autor} ({org}) | **Data:** {data_atual}\n",
                "---\n",
                "## Pré-requisitos e Informações do Ambiente\n",
                "- **Servidor / Equipamento:** `Preencher IP ou Hostname`\n"
                "- **Permissão necessária:** `Administrador / Root`\n",
                "---\n",
                "## Passo a Passo\n"
            ])

        mapa_ia = {p.numero_passo: p for p in doc.passos}

        for idx, orig in enumerate(self.passos):
            num_passo = idx + 1
            p_ia = mapa_ia.get(num_passo)
            if p_ia is None and idx < len(doc.passos):
                p_ia = doc.passos[idx]

            titulo_passo = p_ia.titulo if p_ia else f"{orig['tipo']} em {orig.get('janela', 'Sistema')}"
            desc_passo = p_ia.descricao if p_ia else orig["detalhe"]
            obs_passo = p_ia.observacao if p_ia else ""
            cmd_ia = p_ia.comando_cli.strip() if (p_ia and p_ia.comando_cli) else ""

            caminho_md = orig.get("imagem", "").replace("\\", "/")
            janela_alvo = orig.get("janela", "")

            linhas.append(f"### Passo {num_passo}: {titulo_passo}\n")
            if mostrar_janela and janela_alvo and janela_alvo != "Sistema Operacional":
                linhas.append(f"* **Janela / Aplicação:** `{janela_alvo}`\n")

            linhas.append(f"{desc_passo}\n")

            cmd_final = cmd_ia or orig.get("comando_bruto", "").strip()
            if cmd_final:
                linhas.append("```bash")
                linhas.append(cmd_final)
                linhas.append("```\n")

            if mostrar_nota and obs_passo:
                linhas.append(f"> **Nota Técnica:** {obs_passo}\n")

            linhas.append(f"![Passo {num_passo}]({caminho_md})\n")
            linhas.append("---\n")

        if template in ("POP / Runbook (Infra)", "Troubleshooting / Incidente"):
            linhas.append("## 3. Checklist de Validação Pós-Procedimento\n")
            for val in (doc.validacao_pos or ["Verificar se o serviço/configuração está ativo e operacional."]):
                linhas.append(f"- [ ] {val}")
            linhas.append("\n---\n")

            if template == "POP / Runbook (Infra)" and doc.procedimento_rollback:
                linhas.append("## 4. Plano de Rollback (Reversão em Caso de Falha)\n")
                linhas.append(f"{doc.procedimento_rollback}\n---\n")

        if rodape_custom:
            linhas.append(f"*{rodape_custom}*\n")

        return "\n".join(linhas)

    def _concluir_geracao_ui(self, texto_md: str, erro: str, cancelado: bool = False):
        self.btn_gerar_ia.configure(state="normal", text="✨ Gerar com Gemini")
        modal = getattr(self, "modal_progresso", None)

        if cancelado:
            self.lbl_status.configure(text="⚠️ Geração cancelada pelo usuário.", text_color="#ffc107")
            return

        if erro:
            self.lbl_status.configure(text="❌ Erro ao chamar a Gemini API.", text_color="#dc3545")
            if modal and modal.winfo_exists():
                modal.marcar_erro(erro)
            else:
                messagebox.showerror(
                    "Erro na API",
                    f"Falha ao processar com o Gemini:\n{erro}\n\n"
                    "Dica: Verifique se a chave configurada no botão '🔒 API' está correta."
                )
            return

        self.txt_editor.delete("0.0", "end")
        self.txt_editor.insert("0.0", texto_md)

        caminho_padrao = os.path.join(self.pasta_sessao, "procedimento.md")
        with open(caminho_padrao, "w", encoding="utf-8") as f:
            f.write(texto_md)

        nome_pasta_final = os.path.basename(self.pasta_sessao)
        self.lbl_status.configure(
            text=f"✅ Salvo em: {nome_pasta_final}",
            text_color="#20c997"
        )

        if modal and modal.winfo_exists():
            modal.marcar_sucesso(f"Salvo em: {nome_pasta_final}")

    # --------------------------------------------------------------------------
    # SUBSEÇÃO 7.6: MOTORES DE EXPORTAÇÃO (.MD, .HTML INTERATIVO E .PDF)
    # --------------------------------------------------------------------------

    def _gerar_html_documento(self, modo_saida: str = "html_interativo") -> str:
        texto_md = self.txt_editor.get("0.0", "end")

        def substituir_imagem_markdown(match):
            alt_text = match.group(1)
            caminho_rel_zoom = match.group(2).strip()
            caminho_abs_zoom = os.path.abspath(os.path.join(self.pasta_sessao, caminho_rel_zoom))

            if not os.path.exists(caminho_abs_zoom):
                return match.group(0)

            if modo_saida == "pdf":
                caminho_pdf_norm = caminho_abs_zoom.replace("\\", "/")
                return (
                    f'<div class="pdf-img-box">'
                    f'<img src="{caminho_pdf_norm}" width="420" height="420" alt="{alt_text}" />'
                    f'</div>'
                )

            with open(caminho_abs_zoom, "rb") as f_zoom:
                b64_zoom = base64.b64encode(f_zoom.read()).decode("utf-8")
            uri_zoom = f"data:image/png;base64,{b64_zoom}"

            base_sem_ext, ext = os.path.splitext(caminho_abs_zoom)
            caminho_abs_full = f"{base_sem_ext}_full{ext}"

            if os.path.exists(caminho_abs_full):
                with open(caminho_abs_full, "rb") as f_full:
                    b64_full = base64.b64encode(f_full.read()).decode("utf-8")
                uri_full = f"data:image/png;base64,{b64_full}"

                return (
                    f'<div class="zoom-container" onclick="alternarZoom(this)" title="Clique para alternar entre Zoom Focado e Tela Cheia">'
                    f'<div class="zoom-badge">🔍 Ver Tela Cheia (Zoom Out)</div>'
                    f'<img class="step-img" src="{uri_zoom}" data-zoom="{uri_zoom}" data-full="{uri_full}" data-mode="zoom" alt="{alt_text}" />'
                    f'</div>'
                )

            return f'<img src="{uri_zoom}" width="460" alt="{alt_text}" />'

        md_processado = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", substituir_imagem_markdown, texto_md)
        corpo_html = markdown.markdown(md_processado, extensions=["extra", "tables", "fenced_code"])

        if modo_saida == "pdf":
            return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 1.6cm;
        }}
        body {{
            font-family: Helvetica, Arial, sans-serif;
            color: #1f2937;
            font-size: 11pt;
            line-height: 1.45;
        }}
        h1 {{
            color: #0f172a;
            font-size: 20pt;
            border-bottom: 1px solid #94a3b8;
            padding-bottom: 6px;
        }}
        h2 {{
            color: #1e40af;
            font-size: 14pt;
            margin-top: 16px;
        }}
        h3 {{
            color: #334155;
            font-size: 12pt;
            margin-top: 14px;
            keep-with-next: true;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        th, td {{
            border: 1px solid #cbd5e1;
            padding: 6px;
            font-size: 9.5pt;
        }}
        th {{
            background-color: #f1f5f9;
        }}
        pre {{
            background-color: #f1f5f9;
            border: 1px solid #cbd5e1;
            padding: 8px;
            font-family: Courier, monospace;
            font-size: 9.5pt;
        }}
        blockquote {{
            background-color: #f8fafc;
            border-left: 3px solid #3b82f6;
            padding: 6px 10px;
            margin: 8px 0;
        }}
        .pdf-img-box {{
            margin: 10px 0 14px 0;
            text-align: left;
        }}
        hr {{
            border: 0;
            border-top: 1px solid #cbd5e1;
            margin: 14px 0;
        }}
        .footer-copy {{
            margin-top: 25px;
            font-size: 9pt;
            color: #64748b;
            text-align: center;
        }}
    </style>
</head>
<body>
{corpo_html}
<div class="footer-copy">© 2026 Desenvolvido por Raffael Dutra — AutoDoc IT</div>
</body>
</html>"""

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Procedimento Técnico — AutoDoc IT</title>
    <style>
        body {{
            font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
            color: #1f2937;
            line-height: 1.6;
            max-width: 920px;
            margin: 0 auto;
            padding: 25px;
            background-color: #f8fafc;
        }}
        .doc-wrapper {{
            background-color: #ffffff;
            padding: 35px 45px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            border: 1px solid #e2e8f0;
        }}
        h1 {{
            color: #0f172a;
            border-bottom: 2px solid #cbd5e1;
            padding-bottom: 10px;
            font-size: 26px;
            margin-top: 0;
        }}
        h2 {{
            color: #1e40af;
            margin-top: 28px;
            font-size: 19px;
        }}
        h3 {{
            color: #334155;
            margin-top: 24px;
            font-size: 16px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 13px;
        }}
        th, td {{
            border: 1px solid #cbd5e1;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background-color: #f1f5f9;
            color: #0f172a;
        }}
        blockquote {{
            background-color: #f1f5f9;
            border-left: 4px solid #3b82f6;
            padding: 10px 16px;
            margin: 14px 0;
            color: #334155;
            border-radius: 0 6px 6px 0;
        }}
        pre {{
            background-color: #0f172a;
            color: #f8fafc;
            padding: 12px 16px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: Consolas, Courier, monospace;
            font-size: 13px;
            margin: 12px 0;
        }}
        code {{
            background-color: #e2e8f0;
            color: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: Consolas, Courier, monospace;
            font-size: 13px;
        }}
        pre code {{
            background-color: transparent;
            color: inherit;
            padding: 0;
        }}
        img {{
            display: block;
            max-width: 480px;
            width: 100%;
            height: auto;
            margin: 14px 0;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
        }}
        .zoom-container {{
            position: relative;
            display: inline-block;
            margin: 14px 0;
            cursor: zoom-out;
            max-width: 100%;
        }}
        .zoom-container.expanded {{
            cursor: zoom-in;
            display: block;
        }}
        .zoom-container .step-img {{
            margin: 0;
            max-width: 480px;
            transition: max-width 0.25s ease, box-shadow 0.25s ease;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .zoom-container.expanded .step-img {{
            max-width: 100%;
            border-color: #0dcaf0;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        }}
        .zoom-badge {{
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: rgba(15, 23, 42, 0.82);
            color: #ffffff;
            padding: 5px 11px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            pointer-events: none;
            transition: background-color 0.2s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        .zoom-container.expanded .zoom-badge {{
            background-color: rgba(13, 110, 253, 0.9);
        }}
        hr {{
            border: 0;
            border-top: 1px solid #e2e8f0;
            margin: 26px 0;
        }}
        .footer-copy {{
            margin-top: 30px;
            text-align: center;
            font-size: 12px;
            color: #64748b;
        }}
    </style>
</head>
<body>
<div class="doc-wrapper">
{corpo_html}
<div class="footer-copy">© 2026 Desenvolvido por Raffael Dutra — Todos os direitos reservados.</div>
</div>
<script>
function alternarZoom(container) {{
    const img = container.querySelector('.step-img');
    const badge = container.querySelector('.zoom-badge');
    const modoAtual = img.getAttribute('data-mode');

    if (modoAtual === 'zoom') {{
        img.src = img.getAttribute('data-full');
        img.setAttribute('data-mode', 'full');
        container.classList.add('expanded');
        badge.innerHTML = '🔎 Voltar ao Foco (Zoom In)';
    }} else {{
        img.src = img.getAttribute('data-zoom');
        img.setAttribute('data-mode', 'zoom');
        container.classList.remove('expanded');
        badge.innerHTML = '🔍 Ver Tela Cheia (Zoom Out)';
    }}
}}
</script>
</body>
</html>"""

    def _resolver_caminho_pdf(self, uri: str, rel: str) -> str:
        if os.path.exists(uri):
            return uri
        caminho_tentativa = os.path.abspath(os.path.join(self.pasta_sessao, uri))
        if os.path.exists(caminho_tentativa):
            return caminho_tentativa
        return uri

    def salvar_markdown(self):
        conteudo = self.txt_editor.get("0.0", "end")
        caminho_padrao = os.path.join(self.pasta_sessao, "procedimento.md")
        with open(caminho_padrao, "w", encoding="utf-8") as f:
            f.write(conteudo)

        caminho = filedialog.asksaveasfilename(
            initialdir=self.pasta_sessao,
            initialfile="procedimento.md",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")]
        )
        if caminho:
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(conteudo)
            self.lbl_status.configure(text=f"💾 Markdown salvo: {os.path.basename(caminho)}", text_color="#20c997")

    def exportar_html_unico(self):
        caminho = filedialog.asksaveasfilename(
            initialdir=self.pasta_sessao,
            initialfile="procedimento_interativo.html",
            defaultextension=".html",
            filetypes=[("Página Web Interativa", "*.html")]
        )
        if not caminho:
            return

        try:
            html_completo = self._gerar_html_documento(modo_saida="html_interativo")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(html_completo)
            self.lbl_status.configure(
                text=f"🌐 HTML interativo exportado: {os.path.basename(caminho)}", text_color="#0dcaf0"
            )
        except Exception as e:
            messagebox.showerror("Erro ao Exportar HTML", f"Ocorreu um erro:\n{e}")

    def exportar_pdf(self):
        caminho = filedialog.asksaveasfilename(
            initialdir=self.pasta_sessao,
            initialfile="procedimento.pdf",
            defaultextension=".pdf",
            filetypes=[("Documento PDF", "*.pdf")]
        )
        if not caminho:
            return

        try:
            self.lbl_status.configure(text="⏳ Renderizando PDF com imagens...", text_color="#ffc107")
            self.update_idletasks()

            html_para_pdf = self._gerar_html_documento(modo_saida="pdf")
            with open(caminho, "wb") as pdf_file:
                status_pisa = pisa.CreatePDF(
                    src=html_para_pdf,
                    dest=pdf_file,
                    encoding="utf-8",
                    link_callback=self._resolver_caminho_pdf
                )

            if status_pisa.err:
                messagebox.showerror("Erro no PDF", "Houve uma falha na renderização do PDF.")
            else:
                self.lbl_status.configure(
                    text=f"📄 PDF gerado com imagens: {os.path.basename(caminho)}", text_color="#20c997"
                )
        except Exception as e:
            messagebox.showerror("Erro ao Exportar PDF", f"Ocorreu um erro:\n{e}")

    def abrir_pasta_sessao(self):
        os.makedirs(self.pasta_sessao, exist_ok=True)
        sistema = platform.system()
        if sistema == "Windows":
            os.startfile(self.pasta_sessao)
        elif sistema == "Darwin":
            subprocess.Popen(["open", self.pasta_sessao])
        else:
            subprocess.Popen(["xdg-open", self.pasta_sessao])


# ==============================================================================
# SEÇÃO 8: PONTO DE ENTRADA DA APLICAÇÃO (ENTRYPOINT)
# ==============================================================================

if __name__ == "__main__":
    app = AutoDocApp()
    app.mainloop()