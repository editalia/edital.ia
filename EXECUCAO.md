# Edital.IA — Guia de Execução

Este documento cobre **instalação**, **execução manual**, **agendamento
automático** (cron) e **testes** em Windows, Linux e macOS.

Para entender o que o projeto faz e como cada arquivo funciona, leia o
[README.md](README.md).

---

## 📋 Requisitos

| Item | Versão / Detalhe |
|---|---|
| Python | 3.11 ou superior |
| Pip | versão recente |
| Conta Ollama Cloud | obrigatória — usamos `qwen3-coder:480b-cloud` (free tier) |
| Espaço em disco | ~2 GB (ChromaDB + sentence-transformers baixa o modelo de embedding) |
| Internet | obrigatória nas etapas de crawl e extração |

> **Por que Ollama Cloud e não local?** O modelo `qwen3-coder:480b` é
> grande demais pra rodar em hardware comum. O free tier do Ollama Cloud
> resolve. Os embeddings (`paraphrase-multilingual-MiniLM-L12-v2`) **são
> locais** via sentence-transformers — o ChromaDB nunca faz chamada de
> rede.

---

## ⚙️ Instalação

### 1. Clone e entre na pasta

```bash
git clone <url-do-repo>
cd Edital.IA/versao_0.1
```

### 2. Crie e ative o virtualenv

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

> Na primeira vez, o `sentence-transformers` vai baixar o modelo de
> embedding (~400 MB). É normal e acontece **uma única vez**.

### 4. Configure o `.env`

Crie um arquivo `.env` na raiz com:

```env
MODEL=qwen3-coder:480b-cloud
OLLAMA_HOST=https://ollama.com
OLLAMA_API_KEY=sua-chave-aqui
```

A chave da API é gerada em https://ollama.com (login → Settings → API Keys).

---

## ▶️ Execução manual

### Rodar o pipeline completo

Crawler → conversor → validador → vector store → extrator:

```bash
python pipeline.py
```

Saída esperada (resumida):
```
[INFO] >>> [1/5] Crawler
[INFO] >>> [2/5] Conversor PDF -> Markdown
[INFO] >>> [3/5] Validador
[INFO] >>> [4/5] Vector store (chunking + embedding)
[INFO] >>> [5/5] Extrator (pré-extração para o front)
[INFO] ==================== PIPELINE FINALIZADO em 145.2s ====================
```

Após rodar, os JSONs em `state/` estão populados e o front pode ser aberto.

### Rodar etapas isoladas

Cada arquivo do pipeline funciona standalone:

```bash
python crawler.py
python pymu_conversor_markdown.py
python validador.py
python vector_store.py
python extrator_rag.py
```

### Abrir a interface web

```bash
streamlit run app.py
```

Abre em http://localhost:8501.

### Debug do RAG

Para inspecionar manualmente o que o RAG está recuperando em um edital
específico (chunks, distâncias, prompt final, resposta da LLM):

```bash
python diagnose_rag.py
```

Edite a constante `ARQUIVO_TESTE` no topo do script pra apontar pro
edital que você quer debugar.

---

## ⏰ Agendamento automático (cron)

O pipeline foi pensado pra rodar **1×/dia às 08:00**. Os logs vão pra
`state/pipeline_logs/AAAA-MM-DD_HH.log`.

> Os scripts de cron foram desenvolvidos primariamente para **Windows**
> (sistema usado em desenvolvimento). Linux e macOS estão documentados e
> com scripts prontos, mas **não foram testados em ambiente real** — use
> como referência.

---

### 🪟 Windows (oficial)

Usa **Task Scheduler** via PowerShell.

**Instalar:**
```powershell
.\scripts\install_cron.ps1
```

**Rodar AGORA (manual):**
```powershell
Start-ScheduledTask -TaskName 'EditalIA-Pipeline'
```

**Verificar status:**
```powershell
Get-ScheduledTaskInfo -TaskName 'EditalIA-Pipeline'
```

**Remover:**
```powershell
.\scripts\uninstall_cron.ps1
```

**Configurações da tarefa** (ver `scripts/install_cron.ps1`):
- Roda diariamente às 08:00
- `StartWhenAvailable`: se a máquina estava off às 08:00, roda na próxima
  oportunidade
- `DontStopIfGoingOnBatteries` + `AllowStartIfOnBatteries`: não para por
  bateria
- `ExecutionTimeLimit`: 1h
- Logon `Interactive` + `RunLevel Limited`: roda como o usuário logado
  (sem precisar senha)

> **Atenção**: se o computador está dormindo (sleep) no horário, a tarefa
> não dispara. Para acordar a máquina, adicione `-WakeToRun` ao
> `New-ScheduledTaskSettingsSet` no `install_cron.ps1`.

---

### 🐧 Linux (crontab)

**Pré-requisito**: dar permissão de execução aos scripts.

```bash
chmod +x scripts/run_pipeline.sh
chmod +x scripts/install_cron_linux.sh
chmod +x scripts/uninstall_cron_linux.sh
```

**Instalar:**
```bash
./scripts/install_cron_linux.sh
```

O script:
1. Adiciona uma linha `0 8 * * * /path/absoluto/scripts/run_pipeline.sh`
   ao `crontab -e` do usuário atual
2. Verifica que `run_pipeline.sh` tem permissão de execução
3. Imprime o crontab atualizado

**Rodar AGORA (manual):**
```bash
./scripts/run_pipeline.sh
```

**Ver tarefas agendadas:**
```bash
crontab -l
```

**Remover:**
```bash
./scripts/uninstall_cron_linux.sh
```

**Como funciona o `run_pipeline.sh`**:
- Resolve o caminho do projeto a partir da sua própria localização
- Ativa o venv (`source .venv/bin/activate`)
- Roda `python pipeline.py` redirecionando stdout+stderr pra um log
  timestamped em `state/pipeline_logs/`
- Retorna o exit code do pipeline

> **Alternativa moderna (systemd timer)**: mais robusto que crontab
> (melhor logging via `journalctl`, retry automático). Não incluído aqui
> pra manter simples — se você quer migrar, crie
> `~/.config/systemd/user/editalia-pipeline.{service,timer}` apontando
> pra `scripts/run_pipeline.sh` com `OnCalendar=*-*-* 08:00:00`.

---

### 🍎 macOS (launchd)

macOS usa **launchd** (nativo Apple, mais confiável que cron neste OS).

**Pré-requisito**: dar permissão de execução.

```bash
chmod +x scripts/run_pipeline.sh
chmod +x scripts/install_cron_macos.sh
chmod +x scripts/uninstall_cron_macos.sh
```

**Instalar:**
```bash
./scripts/install_cron_macos.sh
```

O script:
1. Copia o template `scripts/com.editalia.pipeline.plist` para
   `~/Library/LaunchAgents/com.editalia.pipeline.plist` **substituindo**
   os placeholders pelo caminho absoluto do projeto
2. Carrega o agente com `launchctl bootstrap gui/$UID ...`

**Rodar AGORA (manual):**
```bash
launchctl kickstart -k gui/$UID/com.editalia.pipeline
```

ou diretamente:
```bash
./scripts/run_pipeline.sh
```

**Ver status:**
```bash
launchctl print gui/$UID/com.editalia.pipeline
```

**Remover:**
```bash
./scripts/uninstall_cron_macos.sh
```

> **Crontab também funciona no macOS** se você preferir — basta usar os
> scripts Linux (`install_cron_linux.sh`). Mas o Apple recomenda launchd
> desde o macOS 10.4, e é o que faz a máquina acordar do sleep para
> rodar a tarefa.

---

## 📜 Logs

Todos os agendadores escrevem em `state/pipeline_logs/AAAA-MM-DD_HH.log`.

Para ver o último log:

**Windows:**
```powershell
Get-Content (Get-ChildItem state\pipeline_logs\*.log | Sort LastWriteTime -Desc | Select -First 1)
```

**Linux / macOS:**
```bash
tail -f state/pipeline_logs/$(ls -t state/pipeline_logs | head -1)
```

---

## 🧪 Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Para rodar só os unitários (sem integração):
```bash
pytest tests/unit
```

Para rodar com mais detalhe:
```bash
pytest -vv
```

---

## 🩺 Troubleshooting

### `Connection refused` ao chamar a LLM
Verifique o `.env`: `OLLAMA_HOST=https://ollama.com` e `OLLAMA_API_KEY`
preenchidos. Para usar Ollama **local**, mude pra
`OLLAMA_HOST=http://localhost:11434` e o modelo correspondente.

### Crawler retornando 0 PDFs
O portal IFBA muda o HTML ocasionalmente. Verifique:
- Acesso direto a https://portal.ifba.edu.br/prpgi/editais/ no navegador
- `state/urls_visitadas.json` — se tudo já está visitado, está correto

### `UnicodeDecodeError` no log do Windows
Confirme que `run_pipeline.ps1` está com `$env:PYTHONIOENCODING = "utf-8"`
e que o Python é chamado com `-X utf8`.

### ChromaDB corrompido
Apague a pasta `chroma_db/` e rode `python vector_store.py` novamente. O
índice é determinístico (`{nome}_chunk_{i}`), então tudo é recriado.

### Tarefa do Windows com `NumberOfMissedRuns > 0`
Significa que o PC estava off/sleeping no horário agendado.
`StartWhenAvailable` faz ela rodar assim que possível. Se quiser
**acordar** a máquina, adicione `-WakeToRun` no
`New-ScheduledTaskSettingsSet`.

### Streamlit não atualiza após rodar o pipeline
O Streamlit cacheia os JSONs. Pressione `R` na interface ou reinicie
(`Ctrl+C` e `streamlit run app.py` novamente).
