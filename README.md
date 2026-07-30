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
git clone https://github.com/fenyag7/revitapidocs-mcp.git
cd revitapidocs-mcp

# sparse-клон блога — только текст (~45 МБ), без картинок/PDF/zip (~1.6 ГБ)
git clone --depth 1 --filter=blob:none --sparse https://github.com/jeremytammik/tbc.git
git -C tbc sparse-checkout set --no-cone "/a/*.md" "/a/*.htm" "/a/*.html"
```

Самопроверка (три ассерта: поиск класса, получение страницы, поиск по блогу):

```bash
uv run --system-certs --script server.py --check
```

По умолчанию блог ищется в `./tbc/a` рядом со скриптом. Другой путь — через переменную окружения `TBC_PATH`.

### Корпоративный прокси / перехват TLS

Если на машине стоит корпоративный HTTPS-прокси (перевыпускающий сертификаты), `server.py` уже учитывает это через `truststore` (доверяет системному хранилищу сертификатов Windows) — ничего дополнительно настраивать не нужно.

Флаг `--system-certs` у `uv` — для другого: сам `uv` при установке зависимостей ходит на `pypi.org` собственным TLS-клиентом, минуя `truststore` из скрипта. `uv` кеширует окружение по абсолютному пути скрипта, так что при первом запуске с нового пути (после клонирования репозитория или переноса файлов) он заново резолвит зависимости с PyPI — и без `--system-certs` упрётся в тот же перехват сертификатов с ошибкой `UnknownIssuer`. Поэтому флаг стоит держать в команде запуска постоянно, а не добавлять только при ошибке.

## Регистрация в Claude Code (CLI и десктоп-чат)

```bash
claude mcp add revit-docs --scope user -- uv run --system-certs --script "<путь-до-репозитория>\server.py"
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
      "command": "<путь-до-uv.exe>",
      "args": [
        "run",
        "--system-certs",
        "--script",
        "<путь-до-репозитория>\\server.py"
      ]
    }
  }
}
```

Оба пути — абсолютные, с двойными обратными слешами (или прямыми слешами — JSON понимает оба варианта). `command` лучше указывать полным путём до `uv.exe` (например, `C:\\Users\\<юзер>\\.local\\bin\\uv.exe`), а не рассчитывать на `PATH` — процесс приложения не всегда наследует пользовательский `PATH` так же, как интерактивный терминал. Остальные ключи в файле (`preferences` и т.д.) не трогать, просто добавить `mcpServers` рядом.

**После правки — полный перезапуск приложения**, не просто новая сессия чата: конфиг читается один раз при старте.

## Обновление блога

```bash
git -C tbc pull
```
