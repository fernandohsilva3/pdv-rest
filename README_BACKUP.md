
# Backup Automático

Este script faz backup do banco de dados SQLite diariamente.

- Script: `backup.py`
- Banco padrão: `pdv.db`
- Diretório de backups: `backups/`

### Linux/macOS (cron)
Execute `crontab -e` e adicione:
0 2 * * * python3 /caminho/para/server_fastapi/backup.py

### Windows (Agendador de Tarefas)
1. Abra Agendador de Tarefas.
2. Criar nova tarefa diária às 2:00.
3. Ação: iniciar um programa -> `python`.
4. Argumentos: `C:\caminho\server_fastapi\backup.py`
5. Iniciar em: `C:\caminho\server_fastapi`
