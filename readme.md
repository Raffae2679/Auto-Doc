# 🖥️ AutoDoc IT — Gravador Inteligente de Procedimentos e Documentação

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Plataforma-Windows%20%7C%20Linux-0078D6?style=for-the-badge&logo=windows)
![AI](https://img.shields.io/badge/IA-Google%20Gemini%202.5%20Flash-8E75B2?style=for-the-badge&logo=google)
![License](https://img.shields.io/badge/Autor-Raffael%20Dutra-198754?style=for-the-badge)

O **AutoDoc IT** é uma ferramenta desktop de gestão do conhecimento e mapeamento de processos voltada para equipes de **Tecnologia da Informação, Redes, Segurança e Infraestrutura**. 

Diferente de extensões restritas ao navegador, o **AutoDoc IT** opera em nível de sistema operacional, permitindo documentar procedimentos em sessões SSH (PuTTY, MobaXterm), consoles de virtualização, gerenciadores de firewall, servidores de arquivos e terminais de linha de comando (CLI), gerando tutoriais técnicos completos automaticamente com o auxílio da visão computacional do **Google Gemini 2.5 Flash**.

---

## ✨ Principais Funcionalidades

* **🎯 Captura Inteligente de Cliques e Duplo Clique:** Registra o ponto exato da interação antes da transição de tela, diferenciando cliques simples de duplos cliques automaticamente (sem duplicar imagens).
* **⌨️ Rastreamento de Foco de Digitação (Caret Tracking):** Quando o usuário digita em um campo ou barra de pesquisa, o recorte da imagem foca exatamente no cursor de texto ativo, independentemente de onde o ponteiro do mouse estiver.
* **💻 Modo Terminal / CLI Inteligente:** Reconhece automaticamente janelas de console (`cmd`, `PowerShell`, `PuTTY`, `SSH`, `WinBox`, `Bash`) e converte comandos digitados ou colados em blocos de código copiáveis (` ```bash `) no documento final.
* **📋 Captura de Área de Transferência (`Ctrl+V`) e Atalhos:** Registra comandos colados no terminal (incluindo clique com botão direito no PuTTY) e combinações de teclas modificadoras (`Win + R`, `Alt + F4`, etc.).
* **🎨 Estúdio Integrado de Anotação e Censura (`🖌️`):** Permite aplicar **Desfoque/Pixelização (Blur)** em IPs e senhas, além de desenhar **Setas**, **Retângulos de Destaque** e **Etiquetas de Texto** sincronizados tanto na imagem com zoom quanto na imagem de tela cheia.
* **🔒 Segurança de Credenciais:**
  * **Modo Senha (`F8`):** Oculta automaticamente qualquer senha digitada ou colada durante a gravação (`********`).
  * **API Key Criptografada:** A chave da Gemini API é protegida localmente no `config.json` utilizando a **Windows Data Protection API (DPAPI)** combinada com derivação **PBKDF2-HMAC-SHA256** vinculada à máquina.
* **📑 Templates Corporativos Customizáveis:** Alterne entre *Padrão*, *POP / Runbook (Infraestrutura)* (com checklist de validação e plano de Rollback), *Guia Rápido (Helpdesk N0/N1)* e *Troubleshooting*.
* **🌐 Exportação Multi-Formato:**
  * **Markdown (`.md`)** editável ao vivo na interface.
  * **HTML Único Interativo (`.html`)** com imagens embutidas em Base64 e botão de **Zoom Out / Tela Cheia** em cada passo.
  * **Documento PDF (`.pdf`)** diagramado para folha A4.
* **📚 Biblioteca Local e Limpeza Automática:** Buscador integrado para reabrir procedimentos antigos e rotina inteligente que remove diretórios vazios ao fechar o programa sem gravar.

---

## 📂 Estrutura de Diretórios Gerada

Os procedimentos registrados são organizados automaticamente por data e renomeados com o título identificado pela IA:

```text
📁 AutoDoc_IT/
 ├── 📄 auto_doc_gui.py
 ├── 🔒 config.json (Gerado automaticamente com criptografia DPAPI/SHA-256)
 └── 📁 Procedimentos/
      └── 📁 Sessão Data 28-10-2026/
           ├── 📁 Procedimento 1 - Atualizacao Firewall Palo Alto - 28-10-2026 21h49m10s/
           │    ├── 🖼️ imagens/ (Contém os recortes com zoom e as versões _full.png)
           │    ├── 📄 procedimento.md
           │    ├── 🌐 procedimento_interativo.html
           │    ├── 📕 procedimento.pdf
           │    └── 🗂️ sessao_meta.json
           └── 📁 Procedimento 2 - Criacao de VM Servidor - 28-10-2026 22h15m00s/