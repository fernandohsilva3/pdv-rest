# Servidor (PC) — PDV Restaurante (Atualizado: Mesas + Relatórios)

## Requisitos
- Python 3.10+
- Pip

## Instalação
```bash
cd server_fastapi
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Executar
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Acesse o Backoffice: `http://localhost:8000/`

## Endpoints principais (resumo)
- `GET /products` — lista produtos.
- `POST /products` — cria produto `{ "name": "Pizza", "price": 35.0 }`.
- `GET /tables` — lista mesas.
- `POST /tables` — cria mesa `{ "name": "Mesa 1" }`.
- `POST /order` — cria pedido (agora grava no banco) `{ "table_id": 1, "items": [{"product_id":1,"quantity":2}] }`.
- `GET /orders?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD` — relatório.