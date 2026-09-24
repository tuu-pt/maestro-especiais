# Maestro Especiais

Agente de IA da TUU – Building Design Management para montar, redigir e validar o processo de projeto de instalações elétricas: MDJ, CTE, MQT/LPU, ficha eletrotécnica, identificação do projeto e termo de responsabilidade.

- Especificação (fonte de verdade): [docs/SPEC.md](docs/SPEC.md)
- Mock-up: [docs/mockup/maestro-especiais.html](docs/mockup/maestro-especiais.html)
- Regras de trabalho e decisões: [CLAUDE.md](CLAUDE.md)

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `frontend/` | React + TypeScript + Vite (ecrãs A–H) |
| `backend/` | API FastAPI e workers |
| `tools/` | Utilitários locais, incluindo o anonimizador (`tools/anonymize.py`) |
| `infra/` | Configuração dos serviços do Docker Compose |
| `docs/` | Especificação e mock-up |
| `data/fixtures/` | Projetos de referência R1 e R2 **anonimizados** (versionados) |
| `data/private/` | Originais com dados pessoais e tabela de correspondências (**nunca** versionados) |

## Requisitos

- Python 3.12, Node 20.19+ (recomendado 24), Docker Desktop, GNU make (no Windows: `winget install ezwinports.make`).

## Arranque

```bash
make setup     # ambiente Python (.venv), dependências do frontend e Chromium do Playwright
make env       # cria o .env local com segredos aleatórios de desenvolvimento
make up        # docker compose up -d --wait
make test      # pytest + vitest
```

- API: http://localhost:8000/api/health
- Frontend: http://localhost:5173

## Anonimização dos projetos de referência

Os originais ficam em `data/private/R1` e `data/private/R2` e só são processados localmente:

```bash
make anonymize   # data/private/R1, R2 → data/fixtures/R1, R2
make pii-check   # confirma que data/fixtures/ não tem padrões de dados pessoais
```

A tabela de correspondências e o relatório detalhado ficam em `data/private/`. Ver a secção 12.2 da SPEC.
