# revit-docs MCP

Локальный MCP-сервер для поиска по Revit API и блогу [The Building Coder](https://thebuildingcoder.typepad.com/), без ключей и без эмбеддингов. Три инструмента:

| Инструмент | Делает |
|---|---|
| `search_api(query, year, limit)` | поиск класса/метода/свойства Revit API |
| `get_doc(guid, year)` | текст страницы документации по её `guid` |
| `search_blog(pattern, limit, context)` | regex-поиск по локальной копии блога TBC |

Подробности решения — почему без OpenAI и почему не форк готового `Rvt_Docs_MCP` — см. историю разработки.

## Установка

Нужны [uv](https://docs.astral.sh/uv/) (запускает `server.py` как self-contained скрипт, зависимости в шапке файла) и `git`.

```bash
git clone <URL> revitapidocs-mcp
cd revitapidocs-mcp

# sparse-клон блога — только текст (~45 МБ), без картинок/PDF/zip (~1.6 ГБ)
git clone --depth 1 --filter=blob:none --sparse https://github.com/jeremytammik/tbc.git
git -C tbc sparse-checkout set --no-cone "/a/*.md" "/a/*.htm" "/a/*.html"
```

Самопроверка (три ассерта: поиск класса, получение страницы, поиск по блогу):

```bash
uv run --script server.py --check
```

По умолчанию блог ищется в `./tbc/a` рядом со скриптом. Другой путь — через переменную окружения `TBC_PATH`.

### Корпоративный прокси / перехват TLS

Если на машине стоит корпоративный HTTPS-прокси (перевыпускающий сертификаты), `server.py` уже учитывает это через `truststore` (доверяет системному хранилищу сертификатов Windows) — ничего дополнительно настраивать не нужно. Но у `uv` при первой установке зависимостей может не быть доступа к `pypi.org` из-под того же прокси — тогда однократно:

```bash
uv run --system-certs --script server.py --check
```

## Регистрация в Claude Code (CLI и десктоп-чат)

```bash
claude mcp add revit-docs --scope user -- uv run --script "<путь-до-репозитория>\server.py"
```

Проверка: `claude mcp list` → `revit-docs — Connected`. Работает сразу и в терминале, и в этом же приложении (единый конфиг `~/.claude.json`).

## Регистрация в `claude_desktop_config.json` (панель Settings → Developer → Local MCP servers)

Это **отдельный** реестр серверов, независимый от `claude mcp add` — приложение читает его только при старте, и только он отображается в GUI. Если нужна видимость сервера именно в этой панели, его нужно прописать отдельно.

Файл на Windows:
```
%APPDATA%\Claude\claude_desktop_config.json
```
(для MSIX-сборки приложения это hardlink на `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json` — редактировать можно любой из двух путей, это один и тот же файл).

Добавить в корень JSON ключ `mcpServers` (если его ещё нет) с блоком сервера:

```json
{
  "mcpServers": {
    "revit-docs": {
      "command": "uv",
      "args": [
        "run",
        "--script",
        "<путь-до-репозитория>\\server.py"
      ]
    }
  }
}
```

Путь — абсолютный, с двойными обратными слешами (или прямыми слешами — JSON понимает оба варианта). Остальные ключи в файле (`preferences` и т.д.) не трогать, просто добавить `mcpServers` рядом.

**После правки — полный перезапуск приложения**, не просто новая сессия чата: конфиг читается один раз при старте.

## Обновление блога

```bash
git -C tbc pull
```
