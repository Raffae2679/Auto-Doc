<img width="1891" height="959" alt="auto doc video" src="https://github.com/user-attachments/assets/fdeebcb2-c763-47e8-b793-01777a85917e" />
# 🖥️ AutoDoc IT — Gravador Inteligente de Procedimentos e Documentação

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Plataforma-Windows%20%7C%20Linux-0078D6?style=for-the-badge&logo=windows)
![AI](https://img.shields.io/badge/IA-Google%20Gemini%202.5%20Flash-8E75B2?style=for-the-badge&logo=google)
![License](https://img.shields.io/badge/Autor-Raffael%20Dutra-198754?style=for-the-badge)

O **AutoDoc IT** é uma ferramenta desktop de gestão do conhecimento e mapeamento de processos voltada para equipes de **Tecnologia da Informação, Redes, Segurança e Infraestrutura**. 

Diferente de extensões restritas ao navegador, o **AutoDoc IT** opera em nível de sistema operacional, permitindo documentar procedimentos em sessões SSH (PuTTY, MobaXterm), consoles de virtualização, gerenciadores de firewall, servidores de arquivos e terminais de linha de comando (CLI), gerando tutoriais técnicos completos automaticamente com o auxílio da visão computacional do **Google Gemini 2.5 Flash**.

---

## 🎬 Demonstração em Vídeo

Veja na prática como o **AutoDoc IT** captura um fluxo operacional completo e gera a documentação estruturada em segundos:


<div align="center">
  <!-- Substitua o link abaixo pelo seu vídeo .mp4 arrastado no GitHub ou link do YouTube -->
  <a href="https://github.com/user-attachments/assets/915dd71e-8b0a-4192-99ea-6bb7b50793eb" target="_blank">
    <img src="docs/assets/auto doc video.gif" alt="Assista à Demonstração do AutoDoc IT" width="800"/>
  </a>
</div>

---


## 📸 Galeria de Imagens (Screenshots)

| 🖥️ Interface Principal e Editor ao Vivo | 🎨 Estúdio de Anotação e Censura (Blur) |
| :---: | :---: |
| <img src="docs/assets/auto doc interface.png" width="600"/> | <img src="docs/assets/auto doc interface2.png" width="400"/> |
| *Fila de passos capturados à esquerda e editor Markdown à direita.* | *Aplicação de desfoque em dados sensíveis, setas e caixas de destaque.* |

| 📚 Biblioteca de Procedimentos | 🌐 Relatório HTML Interativo (Zoom In/Out) |
| :---: | :---: |
| <img src="docs/assets/auto doc interface3.png" width="400"/> | <img src="docs/assets/auto doc relatorio.png" width="400"/> |
| *Busca rápida por título, data, comando ou palavra-chave.* | *Visualização web com alternância entre foco do clique e tela cheia.* |

---

## ✨ Principais Funcionalidades

* **🎯 Captura Inteligente de Cliques e Duplo Clique:** Registra o ponto exato da interação antes da transição de tela, diferenciando cliques simples de duplos cliques automaticamente (sem duplicar imagens).
* **⌨️ Rastreamento de Foco de Digitação (Caret Tracking):** Quando o usuário digita em um campo ou barra de pesquisa, o recorte da imagem foca exatamente no cursor de texto ativo, independentemente de onde o ponteiro do mouse estiver.
* **💻 Modo Terminal / CLI Inteligente:** Reconhece automaticamente janelas de console (`cmd`, `PowerShell`, `PuTTY`, `SSH`, `WinBox`, `Bash`) e converte comandos digitados ou colados em blocos de código copiáveis (`` ```bash ``) no documento final.
* **📋 Captura de Área de Transferência (`Ctrl+V`) e Atalhos:** Registra comandos colados no terminal (incluindo clique com botão direito no PuTTY) e combinações de teclas modificadoras (`Win + R`, `Alt + F4`, etc.).
* **🎨 Estúdio Integrado de Anotação e Censura (`🖌️`):** Permite aplicar **Desfoque/Pixelização (Blur)** em IPs e senhas, além de desenhar **Setas**, **Retângulos de Destaque** e **Etiquetas de Texto** sincronizados tanto na imagem com zoom quanto na imagem de tela cheia.
* **🔒 Segurança de Credenciais:**
  * **Modo Senha (`F8`):** Oculta automaticamente qualquer senha digitada ou colada durante a gravação (`********`).
  * **API Key Criptografada:** A chave da Gemini API é protegida localmente no `config.json` utilizando a **Windows Data Protection API (DPAPI)** no Windows e derivação **PBKDF2-HMAC-SHA256** no Linux, vinculada exclusivamente à máquina do usuário.
* **📑 Templates Corporativos Customizáveis:** Alterne entre *Padrão*, *POP / Runbook (Infraestrutura)* (com checklist de validação e plano de Rollback), *Guia Rápido (Helpdesk N0/N1)* e *Troubleshooting*.
* **🌐 Exportação Multi-Formato:**
  * **Markdown (`.md`)** editável ao vivo na interface.
  * **HTML Único Interativo (`.html`)** com imagens embutidas em Base64 e botão de **Zoom Out / Tela Cheia** em cada passo.
  * **Documento PDF (`.pdf`)** diagramado para folha A4.
* **📚 Biblioteca Local e Limpeza Automática:** Buscador integrado para reabrir procedimentos antigos e rotina inteligente que remove diretórios vazios ao fechar o programa sem gravar.

---

## 🚀 Como Executar o Projeto

Você pode rodar o **AutoDoc IT** baixando o executável pronto na aba [**Releases**](../../releases) ou executando diretamente pelo código-fonte em Python.

### Pré-requisitos
* **Python 3.10** ou superior instalado.
* Uma chave de API do Google Gemini (obtenha gratuitamente no [Google AI Studio](https://aistudio.google.com/)).
* **Apenas no Linux (Ubuntu/Debian/Mint):** Instale os pacotes gráficos de suporte ao Tkinter e captura de janela:
  ```bash
  sudo apt update
  sudo apt install python3-pip python3-tk python3-venv xdotool scrot -y
  ```

### 1. Clonar o Repositório
```bash
git clone https://github.com/Raffae2679/Auto-Doc.git
cd Auto-Doc
```

### 2. Criar e Ativar o Ambiente Virtual (`venv`)

* **No Windows (CMD ou PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```

* **No Linux (Terminal Bash):**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Instalar as Dependências (`requirements.txt`)
Com o ambiente virtual ativado, instale todas as bibliotecas necessárias:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Executar a Aplicação
```bash
python auto_doc.py
```
> **Nota:** Na primeira execução, clique no botão **`🔑 Config API`** no canto superior direito da interface e cole a sua chave do Google Gemini. Ela será criptografada e salva automaticamente no arquivo local `config.json`.

---

## ⌨️ Atalhos Globais de Gravação

Durante o uso do aplicativo, você pode controlar toda a operação através dos atalhos globais de teclado:

| Tecla | Ação | Descrição |
| :---: | :--- | :--- |
| **`F9`** | **Iniciar / Pausar Gravação** | Começa a monitorar cliques e digitações ou pausa a captura atual. |
| **`F10`** | **Print Manual de Verificação** | Captura imediatamente a tela na posição atual do mouse sem precisar clicar. |
| **`F8`** | **Alternar Modo Senha (ON/OFF)** | Quando ativado, substitui qualquer texto digitado ou colado por `********`. |

---

## 📄 Exemplo de Relatório Gerado pelo AutoDoc IT

Abaixo está um exemplo real de documentação gerada automaticamente pelo **AutoDoc IT** utilizando o template **POP / Runbook (Infra)**:

> 🔗 **Exemplos completos para download/visualização:**
> * [🌐 Baixar Exemplo em HTML Interativo (`procedimento_interativo.html`)](https://htmlpreview.github.io/?https://github.com/Raffae2679/Auto-Doc/blob/main/docs/exemplos/procedimento_interativo.html)


---

## 📂 Estrutura de Diretórios Gerada

Os procedimentos registrados são organizados automaticamente por data e renomeados com o título identificado pela IA:

```text
📁 Auto-Doc/
 ├── 📄 auto_doc.py
 ├── 📄 requirements.txt
 ├── 🔒 config.json (Gerado localmente com criptografia DPAPI/SHA-256 — ignorado no Git)
 └── 📁 Procedimentos/
      └── 📁 Sessão Data 29-10-2026/
           ├── 📁 Procedimento 1 - Atualizacao Firewall Palo Alto - 29-10-2026 21h49m10s/
           │    ├── 🖼️ imagens/ (Contém os recortes com zoom e as versões _full.png)
           │    ├── 📄 procedimento.md
           │    ├── 🌐 procedimento_interativo.html
           │    ├── 📕 procedimento.pdf
           │    └── 🗂️ sessao_meta.json
           └── 📁 Procedimento 2 - Criacao de VM Servidor - 29-10-2026 22h15m00s/
```

---

## 👨‍💻 Autor

Desenvolvido por **Raffael Dutra** — © 2026 Todos os direitos reservados.
